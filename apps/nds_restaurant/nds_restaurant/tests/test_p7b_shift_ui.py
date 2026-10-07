# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P7b: open and close a POS shift from the POS (create_opening, get_closing_preview, close_shift).

ERPNext's consolidation is mocked: under tests it would otherwise merge every unconsolidated POS
Invoice on the site when a closing has none of its own. Isolated NDSUT fixtures only.
"""

import json
from unittest import mock

import frappe
from frappe.utils import flt

from nds_restaurant.api import shift
from nds_restaurant.api.pos import get_pos_context
from nds_restaurant.tests.test_p7a_shifts import P7Base

PCE_MODULE = "erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry"


def _fake_consolidate(pos_invoices=None, closing_entry=None):
	# what ERPNext's merge job does to the closing once the Sales Invoice exists
	closing_entry.set_status(update=True, status="Submitted")
	closing_entry.update_opening_entry()


class TestP7bShiftFromPos(P7Base):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.closings = []
		self.manager_openings = []
		self._main_flags = {
			r.name: r.get("custom_main_cashier")
			for r in frappe.get_doc("POS Profile", self.pos_profile).applicable_for_users
		}
		self._roles = {u: set(frappe.get_roles(u)) for u in (self.manager, self.cashier)}
		self.mop = self._opening_mop()

	def tearDown(self):
		frappe.set_user("Administrator")
		# every closing on the NDSUT profile, including one left by a close that failed half-way
		for name in set(self.closings) | set(frappe.get_all("POS Closing Entry", filters={"pos_profile": self.pos_profile}, pluck="name")):
			self._drop_closing(name)
		self.manager_openings = list(
			set(self.manager_openings)
			| set(
				frappe.get_all(
					"POS Opening Entry",
					filters={"pos_profile": self.pos_profile, "user": ["!=", self.cashier], "docstatus": ["<", 2]},
					pluck="name",
				)
			)
		)
		if frappe.db.get_value("POS Opening Entry", self.opening, "docstatus") == 1:
			frappe.db.set_value("POS Opening Entry", self.opening, {"status": "Open", "pos_closing_entry": None})
		if frappe.get_meta("POS Profile User").has_field("custom_main_cashier"):
			for row_name, value in self._main_flags.items():
				frappe.db.set_value("POS Profile User", row_name, "custom_main_cashier", value or 0)
		for email, roles in self._roles.items():
			user = frappe.get_doc("User", email)
			extra = [r for r in user.roles if r.role not in roles]
			if extra:
				for r in extra:
					user.remove(r)
				user.save(ignore_permissions=True)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		super().tearDown()  # removes the test invoices first (ERPNext won't cancel an opening that has some)
		frappe.set_user("Administrator")
		for name in self.manager_openings:
			self._drop_opening(name)

	def _drop_opening(self, name):
		if not frappe.db.exists("POS Opening Entry", name):
			return
		frappe.db.set_value("POS Opening Entry", name, {"status": "Open", "pos_closing_entry": None})
		try:
			doc = frappe.get_doc("POS Opening Entry", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("POS Opening Entry", name, force=True, ignore_permissions=True)
		except Exception:
			frappe.db.delete("POS Opening Entry Detail", {"parent": name, "parenttype": "POS Opening Entry"})
			frappe.db.delete("POS Opening Entry", {"name": name})

	# helpers -------------------------------------------------------------
	def _drop_closing(self, name):
		if not frappe.db.exists("POS Closing Entry", name):
			return
		meta = frappe.get_meta("POS Closing Entry")
		for df in meta.get_table_fields():
			frappe.db.delete(df.options, {"parent": name, "parenttype": "POS Closing Entry"})
		frappe.db.delete("POS Closing Entry", {"name": name})

	def _set_main(self, user):
		frappe.set_user("Administrator")
		if not frappe.get_meta("POS Profile User").has_field("custom_main_cashier"):
			self.skipTest("custom_main_cashier not migrated")
		for row in frappe.get_doc("POS Profile", self.pos_profile).applicable_for_users:
			frappe.db.set_value("POS Profile User", row.name, "custom_main_cashier", 1 if row.user == user else 0)
		frappe.clear_document_cache("POS Profile", self.pos_profile)

	def _grant_accounts_user(self, email=None):
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", email or self.manager)
		if "Accounts User" not in [r.role for r in user.roles]:
			user.append("roles", {"role": "Accounts User"})
			user.save(ignore_permissions=True)

	def _free_profile(self):
		"""ERPNext v16 allows one open opening per profile: cancel the NDSUT cashier's (cleanup deletes it)."""
		frappe.set_user("Administrator")
		doc = frappe.get_doc("POS Opening Entry", self.opening)
		if doc.docstatus == 1 and doc.status == "Open":
			doc.cancel()

	def _open_as_manager(self, amount=200):
		self._free_profile()
		self._as(self.manager)
		res = shift.create_opening(self.pos_profile, json.dumps([{"mode_of_payment": self.mop, "opening_amount": amount}]))
		self.manager_openings.append(res["name"])
		return res["name"]

	def _close(self, user, amounts):
		self._as(user)
		with mock.patch(f"{PCE_MODULE}.consolidate_pos_invoices", side_effect=_fake_consolidate) as merged:
			res = shift.close_shift(self.pos_profile, json.dumps(amounts))
		frappe.set_user("Administrator")
		if res["doctype"] == "POS Closing Entry":
			self.closings.append(res["name"])
		else:
			self.sub_closings.append(res["name"])
		return res, merged

	# tests ---------------------------------------------------------------
	def test_open_from_pos(self):
		self._free_profile()
		self._as(self.manager)
		ctx = get_pos_context(self.pos_profile)
		self.assertIsNone(ctx["opening"])
		self.assertIsNone(ctx["profile_opening"])
		name = self._open_as_manager(200)
		frappe.set_user("Administrator")
		doc = frappe.get_doc("POS Opening Entry", name)
		self.assertEqual((doc.docstatus, doc.status, doc.user), (1, "Open", self.manager))
		self.assertEqual([(r.mode_of_payment, flt(r.opening_amount)) for r in doc.balance_details if r.mode_of_payment == self.mop], [(self.mop, 200)])
		self._as(self.manager)
		self.assertEqual(get_pos_context(self.pos_profile)["opening"]["name"], name)
		with self.assertRaisesRegex(frappe.ValidationError, "already have an open POS shift"):
			shift.create_opening(self.pos_profile, "[]")
		self._as(self.captain_a)
		with self.assertRaises(frappe.PermissionError):
			shift.create_opening(self.pos_profile, "[]")
		self._as(self.no_role)
		with self.assertRaises(frappe.PermissionError):
			shift.get_closing_preview(self.pos_profile)

	def test_close_from_pos_submits_pos_closing_entry(self):
		self._grant_accounts_user()
		opening = self._open_as_manager(200)
		self._as(self.manager)
		inv = self._order(table=self.t1)["invoice"]
		self._pay_as(self.manager, inv, mop=self.mop)
		total = flt(frappe.db.get_value("POS Invoice", inv, "rounded_total") or frappe.db.get_value("POS Invoice", inv, "grand_total"))
		self._as(self.manager)
		preview = shift.get_closing_preview(self.pos_profile)
		self.assertEqual(preview["kind"], "POS Closing Entry")
		self.assertEqual(preview["invoice_count"], 1)
		row = [r for r in preview["payments"] if r["mode_of_payment"] == self.mop][0]
		self.assertEqual(flt(row["expected_amount"]), 200 + total)
		res, merged = self._close(self.manager, {self.mop: 200 + total - 5})
		self.assertEqual(res["doctype"], "POS Closing Entry")
		pce = frappe.get_doc("POS Closing Entry", res["name"])
		self.assertEqual((pce.docstatus, pce.user, pce.pos_opening_entry), (1, self.manager, opening))
		self.assertEqual([r.pos_invoice for r in pce.pos_invoices], [inv])
		rec = [r for r in pce.payment_reconciliation if r.mode_of_payment == self.mop][0]
		self.assertEqual((flt(rec.opening_amount), flt(rec.expected_amount), flt(rec.difference)), (200, 200 + total, -5))
		self.assertTrue(merged.called)
		self.assertEqual(frappe.db.get_value("POS Opening Entry", opening, "status"), "Closed")
		self._as(self.manager)
		self.assertIsNone(get_pos_context(self.pos_profile)["opening"])

	def test_close_needs_sales_invoice_rights_when_invoices_exist(self):
		opening = self._open_as_manager(0)
		self._as(self.manager)
		inv = self._order(table=self.t1)["invoice"]
		self._pay_as(self.manager, inv, mop=self.mop)
		self._as(self.manager)
		before = frappe.db.count("POS Closing Entry")
		with self.assertRaisesRegex(frappe.PermissionError, "Sales Invoice"):
			self._close(self.manager, {})
		self.assertEqual(frappe.db.count("POS Closing Entry"), before)
		self.assertEqual(frappe.db.get_value("POS Opening Entry", opening, "status"), "Open")

	def test_drafts_block_closing(self):
		self._open_as_manager(0)
		self._as(self.manager)
		draft = self._order(table=self.t1)["invoice"]
		self.assertIn(draft, shift.get_closing_preview(self.pos_profile)["drafts"])
		with self.assertRaisesRegex(frappe.ValidationError, "Submit/Delete Draft Invoices"):
			shift.close_shift(self.pos_profile, "{}")

	def test_sub_cashier_closes_with_sub_pos_closing_and_main_waits(self):
		# the NDSUT cashier holds the (only) opening and is the main cashier; the manager is a sub.
		# The main cashier closes with Accounts User rights (ERPNext reads and merges the invoices).
		self._set_main(self.cashier)
		self._grant_accounts_user(self.cashier)
		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		self._pay_as(self.manager, inv, mop=self.mop)
		total = flt(frappe.db.get_value("POS Invoice", inv, "rounded_total") or frappe.db.get_value("POS Invoice", inv, "grand_total"))
		# the main cashier can't close while the sub has unclosed payments
		with self.assertRaisesRegex(frappe.ValidationError, "must submit Sub POS Closing"):
			self._close(self.cashier, {})
		self._as(self.manager)
		ctx = get_pos_context(self.pos_profile)
		self.assertIsNone(ctx["opening"])
		self.assertEqual((ctx["profile_opening"], ctx["shift_kind"]), (self.opening, "Sub POS Closing"))
		preview = shift.get_closing_preview(self.pos_profile)
		self.assertEqual((preview["kind"], preview["opening"], preview["invoice_count"]), ("Sub POS Closing", self.opening, 1))
		row = [r for r in preview["payments"] if r["mode_of_payment"] == self.mop][0]
		# the main cashier's float isn't the sub's
		self.assertEqual((flt(row["opening_amount"]), flt(row["expected_amount"])), (0, total))
		res, _merged = self._close(self.manager, {self.mop: total - 1})
		self.assertEqual(res["doctype"], "Sub POS Closing")
		sub = frappe.get_doc("Sub POS Closing", res["name"])
		self.assertEqual((sub.docstatus, sub.pos_opening_entry, sub.user), (1, self.opening, self.manager))
		self.assertEqual([r.pos_invoice for r in sub.pos_transactions], [inv])
		rec = [r for r in sub.payment_reconciliation if r.mode_of_payment == self.mop][0]
		self.assertEqual(flt(rec.difference), -1)
		# the main shift stays open for everyone
		self._as(self.cashier)
		self.assertEqual(get_pos_context(self.pos_profile)["opening"]["name"], self.opening)
		# a second Sub POS Closing by the manager starts after the first
		self._as(self.manager)
		self.assertEqual(shift.get_closing_preview(self.pos_profile)["invoice_count"], 0)
		# now the main cashier closes
		res, merged = self._close(self.cashier, {})
		self.assertEqual(res["doctype"], "POS Closing Entry")
		self.assertEqual(frappe.db.get_value("POS Closing Entry", res["name"], "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("POS Opening Entry", self.opening, "status"), "Closed")
