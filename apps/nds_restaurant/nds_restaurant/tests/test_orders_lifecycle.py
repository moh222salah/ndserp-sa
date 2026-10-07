# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P2a: Orders page API and invoice lifecycle (isolated NDSUT fixtures only)."""

import json
import unittest

import frappe

from nds_restaurant.api.pos import (
	cancel_order,
	create_or_update_order,
	get_invoice,
	get_orders,
	get_pos_context,
	mark_invoice_printed,
	submit_payment,
)
from nds_restaurant.install import ensure_pos_operator_permissions
from nds_restaurant.tests.test_helpers import (
	add_user_to_pos_profile,
	begin_test_pos_cashier_session,
	cleanup_invoice_and_kots,
	code,
	end_test_pos_cashier_session,
	ensure_test_branch,
	ensure_test_menu,
	ensure_test_nds_only_cashier,
	ensure_test_pos_captain,
	ensure_test_pos_manager,
	ensure_test_pos_profile,
	ensure_test_production_unit,
	ensure_test_restaurant,
	ensure_test_room,
	ensure_test_table,
	new_test_run_id,
	register_standard_isolated_fixture_cleanup,
	switch_test_pos_operator_session,
)


def _has_invoice_field(fieldname):
	return frappe.get_meta("POS Invoice").has_field(fieldname)


class TestOrdersLifecycle(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.pos_profile = None
		register_standard_isolated_fixture_cleanup(cls)

		frappe.set_user("Administrator")
		ensure_pos_operator_permissions()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		item_code = code(cls.run_id, "ord-item")
		cls.item_codes.append(item_code)
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
		cls.item_code = item_code

		cls.menu_name = ensure_test_menu(
			cls.run_id, cls.branch, [(item_code, 40)], menu_name=code(cls.run_id, "ord-menu")
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id, cls.branch, cls.company, active_menu=cls.menu_name
		)
		cls.room_name = ensure_test_room(cls.run_id, cls.branch)
		cls.table_name = ensure_test_table(cls.run_id, cls.restaurant_name, cls.branch, cls.room_name)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		cls.warehouse = frappe.db.get_value("POS Profile", cls.pos_profile, "warehouse")
		cls.production_unit_name = ensure_test_production_unit(cls.run_id, cls.pos_profile, cls.warehouse)
		profile_meta = frappe.get_meta("POS Profile")
		values = {}
		if profile_meta.has_field("custom_paid_limit"):
			values["custom_paid_limit"] = 20
		if profile_meta.has_field("custom_view_all_status"):
			values["custom_view_all_status"] = 0
		if values:
			frappe.db.set_value("POS Profile", cls.pos_profile, values)
			frappe.clear_document_cache("POS Profile", cls.pos_profile)

	def setUp(self):
		if not self.pos_profile:
			self.skipTest("No POS Profile")
		if not _has_invoice_field("custom_invoice_printed"):
			self.skipTest("custom_invoice_printed not migrated")
		self.created_invoices = []
		self._reset_table()

	def tearDown(self):
		end_test_pos_cashier_session()
		for inv in self.created_invoices:
			cleanup_invoice_and_kots(inv)
		self._reset_table()

	def _reset_table(self):
		frappe.db.set_value("NDS Table", self.table_name, {"occupied": 0, "current_invoice": None})

	def _as_cashier(self):
		cashier = ensure_test_nds_only_cashier()
		switch_test_pos_operator_session(self.pos_profile, cashier, register_cleanup=self.addCleanup)
		return cashier

	def _order(self, table=None, qty=1, generate_kot=0):
		res = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": qty, "rate": 40}],
			table=table,
			order_type="Dine In" if table else "Take Away",
			generate_kot=generate_kot,
		)
		if res["invoice"] not in self.created_invoices:
			self.created_invoices.append(res["invoice"])
		return res

	def _pay(self, invoice):
		doc = frappe.get_doc("POS Invoice", invoice)
		return submit_payment(
			invoice,
			json.dumps([{"mode_of_payment": "Cash", "amount": doc.rounded_total or doc.grand_total}]),
		)

	def _names(self, status, **filters):
		return [r["name"] for r in get_orders(self.pos_profile, status=status, **filters)]

	def test_unbilled_and_draft_tabs(self):
		self._as_cashier()
		table_order = self._order(table=self.table_name)["invoice"]
		takeaway = self._order()["invoice"]

		self.assertIn(table_order, self._names("Unbilled"))
		self.assertNotIn(takeaway, self._names("Unbilled"))
		self.assertIn(takeaway, self._names("Draft"))
		self.assertNotIn(table_order, self._names("Draft"))

		mark_invoice_printed(table_order)
		self.assertIn(table_order, self._names("Draft"))
		self.assertNotIn(table_order, self._names("Unbilled"))

		row = next(r for r in get_orders(self.pos_profile, status="Draft") if r["name"] == table_order)
		self.assertEqual(row["table"], self.table_name)
		self.assertEqual(row["order_status"], "Draft")

	def test_tab_permissions_follow_profile_flags(self):
		self._as_cashier()
		with self.assertRaises(frappe.PermissionError):
			get_orders(self.pos_profile, status="Paid")
		with self.assertRaises(frappe.ValidationError):
			get_orders(self.pos_profile, status="Bogus")

		ctx_tabs = get_pos_context(self.pos_profile)["settings"]["tabs"]
		self.assertIn("Recently Paid", ctx_tabs)
		self.assertNotIn("Paid", ctx_tabs)

		frappe.set_user("Administrator")
		if frappe.get_meta("POS Profile").has_field("custom_paid_limit"):
			frappe.db.set_value("POS Profile", self.pos_profile, "custom_paid_limit", 0)
			frappe.clear_document_cache("POS Profile", self.pos_profile)
			try:
				with self.assertRaises(frappe.PermissionError):
					get_orders(self.pos_profile, status="Recently Paid")
			finally:
				frappe.db.set_value("POS Profile", self.pos_profile, "custom_paid_limit", 20)
				frappe.clear_document_cache("POS Profile", self.pos_profile)

	def test_filters_by_table_captain_and_search(self):
		cashier = self._as_cashier()
		table_order = self._order(table=self.table_name)["invoice"]
		takeaway = self._order()["invoice"]

		by_table = self._names("Unbilled", table=self.table_name)
		self.assertEqual(by_table, [table_order])
		self.assertIn(takeaway, self._names("Draft", captain=cashier))
		self.assertEqual(self._names("Draft", captain="nobody@example.com"), [])
		self.assertEqual(self._names("Draft", search=takeaway), [takeaway])

		if _has_invoice_field("custom_captain"):
			self.assertEqual(frappe.db.get_value("POS Invoice", takeaway, "custom_captain"), cashier)

	def test_profile_access_is_enforced(self):
		self._as_cashier()
		self._order()
		frappe.set_user("Administrator")
		outsider = ensure_test_pos_captain()
		profile = frappe.get_doc("POS Profile", self.pos_profile)
		profile.set(
			"applicable_for_users",
			[r for r in profile.applicable_for_users if r.user != outsider],
		)
		profile.save(ignore_permissions=True)
		self.assertTrue(profile.applicable_for_users)
		frappe.set_user(outsider)
		with self.assertRaises(frappe.PermissionError):
			get_orders(self.pos_profile, status="Draft")
		with self.assertRaises(frappe.PermissionError):
			get_invoice(self.created_invoices[0])

	def test_print_before_pay_for_dine_in_table(self):
		self._as_cashier()
		inv = self._order(table=self.table_name)["invoice"]
		with self.assertRaises(frappe.ValidationError) as cm:
			self._pay(inv)
		self.assertIn("print invoice before making payment", str(cm.exception).lower())

		mark_invoice_printed(inv)
		result = self._pay(inv)
		self.assertEqual(result["invoice"], inv)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "docstatus"), 1)
		self.assertFalse(frappe.db.get_value("NDS Table", self.table_name, "current_invoice"))
		if _has_invoice_field("custom_cashier"):
			self.assertEqual(
				frappe.db.get_value("POS Invoice", inv, "custom_cashier"), frappe.session.user
			)
		self.assertIn(inv, self._names("Recently Paid"))

		with self.assertRaises(frappe.ValidationError):
			self._pay(inv)

	def test_take_away_payment_does_not_need_print(self):
		self._as_cashier()
		inv = self._order()["invoice"]
		self.assertEqual(self._pay(inv)["invoice"], inv)

	def test_printed_flag_resets_only_when_items_change(self):
		self._as_cashier()
		first = self._order(table=self.table_name)
		inv = first["invoice"]
		mark_invoice_printed(inv)

		same = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 40}],
			table=self.table_name,
			order_type="Dine In",
			invoice=inv,
			generate_kot=0,
		)
		self.assertEqual(same["invoice_printed"], 1)

		changed = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 2, "rate": 40}],
			table=self.table_name,
			order_type="Dine In",
			invoice=inv,
			generate_kot=0,
		)
		self.assertEqual(changed["invoice_printed"], 0)
		self.assertIn(inv, self._names("Unbilled"))

	def test_get_invoice_payload(self):
		cashier = self._as_cashier()
		inv = self._order(table=self.table_name, qty=2, generate_kot=1)["invoice"]
		data = get_invoice(inv)
		self.assertEqual(data["table"], self.table_name)
		self.assertEqual(data["order_status"], "Unbilled")
		self.assertEqual(data["captain"], cashier)
		self.assertEqual(len(data["items"]), 1)
		self.assertEqual(data["items"][0]["amount"], 80)
		self.assertTrue(data["kots"])
		self.assertEqual(data["can_edit"], 1)
		self.assertEqual(data["can_pay"], 1)
		# KOT already sent: only a manager can void it
		self.assertEqual(data["can_cancel"], 0)

	def test_void_draft_without_kot_by_owner(self):
		self._as_cashier()
		inv = self._order(table=self.table_name)["invoice"]
		res = cancel_order(inv, reason="customer left")
		self.assertEqual(res["action"], "voided")
		self.assertFalse(frappe.db.exists("POS Invoice", inv))
		row = frappe.db.get_value("NDS Table", self.table_name, ["occupied", "current_invoice"], as_dict=True)
		self.assertFalse(row.occupied)
		self.assertFalse(row.current_invoice)

	def test_void_sent_order_needs_manager_and_notifies_kitchen(self):
		self._as_cashier()
		inv = self._order(table=self.table_name, generate_kot=1)["invoice"]
		self.assertTrue(frappe.db.exists("NDS KOT", {"pos_invoice": inv, "kot_type": "New Order"}))

		with self.assertRaises(frappe.PermissionError):
			cancel_order(inv)

		frappe.set_user("Administrator")
		manager = ensure_test_pos_manager()
		frappe.set_user(manager)
		res = cancel_order(inv, reason="wrong table")
		self.assertEqual(res["action"], "voided")
		self.assertTrue(res["kots"])
		self.assertFalse(frappe.db.exists("POS Invoice", inv))
		cancelled = frappe.get_all(
			"NDS KOT",
			filters={"pos_invoice": inv, "kot_type": "Cancelled", "docstatus": 1},
			fields=["name", "comments"],
		)
		self.assertEqual(len(cancelled), 1)
		self.assertIn("wrong table", cancelled[0].comments or "")
		self.assertFalse(frappe.db.get_value("NDS Table", self.table_name, "occupied"))

	def test_cancel_paid_invoice_manager_only(self):
		self._as_cashier()
		inv = self._order(generate_kot=1)["invoice"]
		self._pay(inv)

		with self.assertRaises(frappe.PermissionError):
			cancel_order(inv)

		frappe.set_user("Administrator")
		manager = ensure_test_pos_manager()
		add_user_to_pos_profile(self.pos_profile, manager)
		frappe.set_user(manager)
		res = cancel_order(inv, reason="refund")
		self.assertEqual(res["action"], "cancelled")
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "docstatus"), 2)
		self.assertFalse(frappe.db.exists("NDS KOT", {"pos_invoice": inv, "docstatus": 1}))

	def test_captain_cannot_pay_or_void_others_sent_order(self):
		self._as_cashier()
		inv = self._order(table=self.table_name, generate_kot=1)["invoice"]
		frappe.set_user("Administrator")
		captain = ensure_test_pos_captain()
		add_user_to_pos_profile(self.pos_profile, captain)
		frappe.set_user(captain)
		data = get_invoice(inv)
		self.assertEqual(data["can_edit"], 0)
		self.assertEqual(data["can_cancel"], 0)
		with self.assertRaises(frappe.PermissionError):
			cancel_order(inv)


class TestMenuGridVisibility(unittest.TestCase):
	def test_variant_label_strips_parent_name(self):
		from nds_restaurant.api.pos import _variant_label

		self.assertEqual(_variant_label("E2E Shawarma", "NDSUT-none-x", "E2E Shawarma-Meat"), "Meat")
		self.assertEqual(_variant_label("Tea", "NDSUT-none-y", "Coffee"), "Coffee")

	def test_children_hidden_and_base_not_sellable(self):
		from unittest.mock import patch

		from nds_restaurant.api.pos import _mark_menu_grid_visibility

		items = [
			{"item": "BASE", "variants": [{"item": "V1"}], "addons": [{"item": "ADD"}], "show_standalone": 0},
			{"item": "V1", "variants": [], "addons": [], "show_standalone": 0},
			{"item": "ADD", "variants": [], "addons": [], "show_standalone": 1},
			{"item": "PLAIN", "variants": [], "addons": [], "show_standalone": 0},
			{"item": "TPL", "variants": [], "addons": [], "has_variants": 1},
		]
		meta = frappe._dict(has_field=lambda f: f == "show_standalone")
		with patch("nds_restaurant.api.pos.frappe.get_meta", return_value=meta):
			_mark_menu_grid_visibility(items)
		by = {i["item"]: i for i in items}
		self.assertEqual(by["V1"]["grid_hidden"], 1)
		self.assertEqual(by["ADD"]["grid_hidden"], 0)
		self.assertEqual(by["PLAIN"]["grid_hidden"], 0)
		self.assertEqual(by["BASE"]["base_sellable"], 0)
		self.assertEqual(by["PLAIN"]["base_sellable"], 1)
		self.assertEqual(by["TPL"]["base_sellable"], 0)

	def test_unmigrated_site_keeps_old_behaviour(self):
		from unittest.mock import patch

		from nds_restaurant.api.pos import _mark_menu_grid_visibility

		items = [
			{"item": "BASE", "variants": [{"item": "V1"}], "addons": []},
			{"item": "V1", "variants": [], "addons": []},
		]
		meta = frappe._dict(has_field=lambda f: False)
		with patch("nds_restaurant.api.pos.frappe.get_meta", return_value=meta):
			_mark_menu_grid_visibility(items)
		self.assertEqual(items[1]["grid_hidden"], 0)
		self.assertEqual(items[0]["base_sellable"], 1)
