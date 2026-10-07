# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P7a: cashier field, daily order number (+ optional daily reset), previous-day-closed rule and
Sub POS Closing payment reconciliation. Isolated NDSUT fixtures only."""

import json
from unittest import mock

import frappe
from frappe.utils import add_days, add_to_date, flt, now_datetime, today

from nds_restaurant.api import kot as kot_api
from nds_restaurant.api import shift
from nds_restaurant.api.multi_cashier import validate_pos_opening
from nds_restaurant.api.pos import get_invoice, get_orders, mark_invoice_printed, submit_payment
from nds_restaurant.tests.test_p4_roles import P4Base


class P7Base(P4Base):
	def setUp(self):
		super().setUp()
		if not frappe.db.table_exists("NDS Order Counter"):
			self.skipTest("NDS Order Counter not migrated")
		self._flags = frappe.db.get_value(
			"POS Profile",
			self.pos_profile,
			["custom_daily_pos_close", "custom_reset_order_number_daily"],
			as_dict=True,
		)
		self._clear_counters()
		self.opening = frappe.db.get_value(
			"POS Opening Entry",
			{"user": self.cashier, "pos_profile": self.pos_profile, "status": "Open", "docstatus": 1},
			"name",
		)
		self._opening_start = frappe.db.get_value("POS Opening Entry", self.opening, "period_start_date")
		self.sub_closings = []

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self.sub_closings:
			if frappe.db.exists("Sub POS Closing", name):
				doc = frappe.get_doc("Sub POS Closing", name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("Sub POS Closing", name, force=True, ignore_permissions=True)
		frappe.db.set_value("POS Opening Entry", self.opening, "period_start_date", self._opening_start)
		frappe.db.set_value("POS Profile", self.pos_profile, dict(self._flags))
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		self._clear_counters()
		super().tearDown()

	def _clear_counters(self):
		frappe.db.delete("NDS Order Counter", {"pos_profile": self.pos_profile})

	def _flag(self, field, value):
		frappe.db.set_value("POS Profile", self.pos_profile, field, value)
		frappe.clear_document_cache("POS Profile", self.pos_profile)

	def _opening_mop(self):
		return frappe.get_all(
			"POS Opening Entry Detail", filters={"parent": self.opening}, pluck="mode_of_payment", order_by="idx"
		)[0]

	def _pay_as(self, user, invoice, mop=None):
		frappe.set_user("Administrator")
		mop = mop or self._opening_mop()
		self._as(user)
		mark_invoice_printed(invoice)
		doc = frappe.get_doc("POS Invoice", invoice)
		submit_payment(invoice, json.dumps([{"mode_of_payment": mop, "amount": doc.rounded_total or doc.grand_total}]))
		return mop


class TestP7Cashier(P7Base):
	def test_creator_then_payer_is_the_cashier(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_cashier"), self.captain_a)
		self._pay_as(self.cashier, inv)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_cashier"), self.cashier)

	def test_backfill_patch_sets_owner(self):
		from nds_restaurant.patches.v1_2 import backfill_pos_invoice_cashier

		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		frappe.db.set_value("POS Invoice", inv, "custom_cashier", None)
		backfill_pos_invoice_cashier.execute()
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_cashier"), self.captain_a)


class TestP7OrderNumber(P7Base):
	def test_numbers_keep_increasing_without_reset(self):
		self._flag("custom_reset_order_number_daily", 0)
		self._as(self.captain_a)
		a = self._order(table=self.t1, generate_kot=1)["invoice"]
		b = self._order(table=self.t2)["invoice"]
		na = frappe.db.get_value("POS Invoice", a, "custom_daily_order_no")
		nb = frappe.db.get_value("POS Invoice", b, "custom_daily_order_no")
		self.assertEqual((na, nb), (1, 2))
		self.assertTrue(frappe.db.exists("NDS Order Counter", f"{self.pos_profile}-1900-01-01"))
		# editing an order keeps its number
		self._order(table=self.t1, invoice=a, items=[{"item_code": self.item_a, "qty": 2}])
		self.assertEqual(frappe.db.get_value("POS Invoice", a, "custom_daily_order_no"), 1)
		# KOT, order detail and Orders search carry it
		frappe.set_user("Administrator")
		kot = frappe.get_all("NDS KOT", filters={"pos_invoice": a, "docstatus": 1}, pluck="name", order_by="creation")[0]
		self.assertEqual(frappe.db.get_value("NDS KOT", kot, "daily_order_no"), 1)
		self._as(self.captain_a)
		self.assertEqual(get_invoice(a)["daily_order_no"], 1)
		# b is an unprinted table order, so it sits in Unbilled
		found = get_orders(self.pos_profile, status="Unbilled", search="#2")
		rows = found["orders"] if isinstance(found, dict) else found
		self.assertIn(b, [r["name"] for r in rows])
		self.assertEqual([r["daily_order_no"] for r in rows if r["name"] == b], [2])

	def test_daily_reset_starts_at_one_each_day(self):
		self._flag("custom_reset_order_number_daily", 1)
		self.assertEqual([shift.next_order_no(self.pos_profile) for _ in range(3)], [1, 2, 3])
		self.assertTrue(frappe.db.exists("NDS Order Counter", f"{self.pos_profile}-{today()}"))
		tomorrow = add_days(today(), 1)
		with mock.patch.object(shift, "today", return_value=tomorrow):
			self.assertEqual(shift.next_order_no(self.pos_profile), 1)
		self.assertEqual(shift.next_order_no(self.pos_profile), 4)

	def test_receipt_shows_order_number_and_cashier(self):
		self._flag("custom_reset_order_number_daily", 0)
		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		self._pay_as(self.cashier, inv)
		frappe.set_user("Administrator")
		values = frappe.db.get_value("POS Invoice", inv, ["custom_daily_order_no", "custom_cashier", "docstatus"], as_dict=True)
		html = frappe.get_print("POS Invoice", inv, print_format="NDS Receipt", no_letterhead=1)
		self.assertIn("Order #1", html, values)
		full = frappe.db.get_value("User", self.cashier, "full_name") or self.cashier
		self.assertIn(full, html)

	def test_noop_without_counter_table(self):
		with mock.patch.object(shift.frappe.db, "table_exists", return_value=False):
			self.assertIsNone(shift.next_order_no(self.pos_profile))


class TestP7DailyClose(P7Base):
	def _new_opening(self, user):
		return frappe.get_doc(
			{
				"doctype": "POS Opening Entry",
				"pos_profile": self.pos_profile,
				"user": user,
				"company": self.company,
				"period_start_date": now_datetime(),
				"posting_date": today(),
				"balance_details": [],
			}
		)

	def test_previous_day_must_be_closed(self):
		yesterday = add_to_date(now_datetime(), days=-1)
		frappe.db.set_value("POS Opening Entry", self.opening, "period_start_date", yesterday)
		# flag off: a new opening isn't blocked by us (ERPNext v16 itself refuses POS Invoices on an
		# opening from another day, "Outdated POS Opening Entry", whatever the flag)
		self._flag("custom_daily_pos_close", 0)
		validate_pos_opening(self._new_opening(self.manager))
		# flag on: a new opening and new orders are blocked until yesterday is closed
		frappe.set_user("Administrator")
		self._flag("custom_daily_pos_close", 1)
		with self.assertRaisesRegex(frappe.ValidationError, "Previous day POS not closed"):
			validate_pos_opening(self._new_opening(self.manager))
		self._as(self.cashier)
		with self.assertRaisesRegex(frappe.ValidationError, "Previous day POS not closed"):
			self._order(table=self.t2)
		# an opening from today is fine
		frappe.set_user("Administrator")
		frappe.db.set_value("POS Opening Entry", self.opening, "period_start_date", now_datetime())
		validate_pos_opening(self._new_opening(self.manager))
		self._as(self.cashier)
		self._order(table=self.t2)


class TestP7SubClosingReconciliation(P7Base):
	def test_cashier_invoices_and_payment_reconciliation(self):
		frappe.set_user("Administrator")
		mop = self._opening_mop()
		frappe.db.sql(
			"UPDATE `tabPOS Opening Entry Detail` SET opening_amount=100 WHERE parent=%s AND mode_of_payment=%s",
			(self.opening, mop),
		)
		self._as(self.captain_a)
		paid_by_cashier = self._order(table=self.t1)["invoice"]
		paid_by_manager = self._order(table=self.t2)["invoice"]
		self._pay_as(self.cashier, paid_by_cashier, mop)
		self._pay_as(self.manager, paid_by_manager, mop)
		total = flt(frappe.db.get_value("POS Invoice", paid_by_cashier, "rounded_total")) or flt(
			frappe.db.get_value("POS Invoice", paid_by_cashier, "grand_total")
		)

		frappe.set_user("Administrator")
		doc = frappe.get_doc({"doctype": "Sub POS Closing", "pos_opening_entry": self.opening})
		doc.insert(ignore_permissions=True)
		self.sub_closings.append(doc.name)
		invoices = [r.pos_invoice for r in doc.pos_transactions]
		self.assertIn(paid_by_cashier, invoices)
		self.assertNotIn(paid_by_manager, invoices)
		row = [r for r in doc.payment_reconciliation if r.mode_of_payment == mop][0]
		self.assertEqual(flt(row.opening_amount), 100)
		self.assertEqual(flt(row.expected_amount), 100 + total)
		self.assertEqual(flt(row.difference), 0)

		row.closing_amount = 100 + total - 5
		doc.save(ignore_permissions=True)
		row = [r for r in doc.payment_reconciliation if r.mode_of_payment == mop][0]
		self.assertEqual(flt(row.closing_amount), 100 + total - 5)
		self.assertEqual(flt(row.difference), -5)

	def test_drafts_block_the_closing(self):
		self._as(self.cashier)
		self._order(table=self.t1)
		frappe.set_user("Administrator")
		with self.assertRaisesRegex(frappe.ValidationError, "Submit/Delete Draft Invoices"):
			frappe.get_doc({"doctype": "Sub POS Closing", "pos_opening_entry": self.opening}).insert(
				ignore_permissions=True
			)
