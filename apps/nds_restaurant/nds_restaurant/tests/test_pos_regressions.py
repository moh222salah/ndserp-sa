# Copyright (c) 2026, NDS and contributors
# License: MIT

import unittest
from unittest.mock import patch

import frappe

from nds_restaurant.api.kot import on_pos_invoice_trash
from nds_restaurant.api.naming import set_pos_invoice_naming
from nds_restaurant.api.pos import (
	_normalize_table_row,
	_reconcile_stale_table_occupancy,
	_resolve_invoice_for_new_table_order,
	create_or_update_order,
	submit_payment,
)
from nds_restaurant.api.reports import get_daily_pnl
from nds_restaurant.install import ensure_pos_operator_permissions
from nds_restaurant.tests.test_helpers import (
	begin_test_pos_cashier_session,
	code,
	cleanup_invoice_and_kots,
	ensure_test_branch,
	ensure_test_menu,
	ensure_test_nds_only_cashier,
	ensure_test_pos_captain,
	ensure_test_pos_manager,
	ensure_test_pos_profile,
	ensure_test_restaurant,
	ensure_test_room,
	ensure_test_table,
	end_test_pos_cashier_session,
	new_test_run_id,
	register_standard_isolated_fixture_cleanup,
	switch_test_pos_operator_session,
)


class TestPosNamingRegression(unittest.TestCase):
	def test_pos_invoice_series_applies_for_acc_psinv_default(self):
		doc = frappe._dict(
			{
				"doctype": "POS Invoice",
				"pos_profile": "TEST-PROFILE",
				"naming_series": "ACC-PSINV-.YYYY.-",
				"custom_nds_order_type": "Dine In",
			}
		)

		profile = frappe._dict(
			{
				"custom_use_invoice_series_prefix": 1,
				"custom_restaurant": "REST-1",
			}
		)
		restaurant = frappe._dict({"invoice_series_prefix": "R1"})

		with patch(
			"nds_restaurant.api.naming.frappe.get_meta",
			return_value=type("M", (), {"has_field": lambda self, f: True})(),
		):
			with patch(
				"nds_restaurant.api.naming.frappe.get_cached_doc",
				side_effect=lambda dt, name: profile if dt == "POS Profile" else restaurant,
			):
				set_pos_invoice_naming(doc)

		self.assertEqual(doc.naming_series, "R1-.YY.-.#####")


class TestPosTableRegression(unittest.TestCase):
	def test_normalize_table_row_frees_stale_submitted_invoice(self):
		table_name = "T-STALE"
		invoice_name = "INV-PAID-1"
		with patch(
			"nds_restaurant.api.pos.frappe.db.get_value",
			side_effect=lambda *a, **k: 1 if a[0] == "POS Invoice" else None,
		):
			row = frappe._dict(
				{"name": table_name, "occupied": 1, "current_invoice": invoice_name}
			)
			out = _normalize_table_row(row)
		self.assertEqual(out.occupied, 0)
		self.assertIsNone(out.current_invoice)


class TestPosCaptainPermissions(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.menu_name = None
		cls.restaurant_name = None
		cls.table_name = None
		cls.room_name = None
		register_standard_isolated_fixture_cleanup(cls)

		frappe.set_user("Administrator")
		ensure_pos_operator_permissions()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		item_code = code(cls.run_id, "cap-item")
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

		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(item_code, 50)],
			menu_name=code(cls.run_id, "cap-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
			order_type_menus=[("Take Away", cls.menu_name)],
		)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		cls.item_code = item_code

	def setUp(self):
		if not getattr(self, "pos_profile", None):
			self.skipTest("No POS Profile")
		self.captain = ensure_test_pos_captain()
		begin_test_pos_cashier_session(self.pos_profile, user=self.captain, register_cleanup=self.addCleanup)
		self.created_invoices = []

	def tearDown(self):
		end_test_pos_cashier_session()
		for inv in self.created_invoices:
			cleanup_invoice_and_kots(inv)

	def test_captain_can_create_takeaway_order_without_account_perm_error(self):
		result = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 50}],
			order_type="Take Away",
			generate_kot=0,
		)
		self.assertIn("invoice", result)
		self.created_invoices.append(result["invoice"])


class TestStaleTableReconcile(unittest.TestCase):
	def test_reconcile_persists_free_for_submitted_invoice(self):
		table = "T-RECON"
		invoice = "INV-SUBMITTED"

		def fake_get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "NDS Table" and fieldname == "current_invoice":
				return invoice
			if doctype == "POS Invoice" and fieldname == "docstatus":
				return 1
			return None

		with patch("nds_restaurant.api.pos.frappe.db.exists", return_value=True):
			with patch("nds_restaurant.api.pos.frappe.db.get_value", side_effect=fake_get_value):
				with patch("nds_restaurant.api.pos._free_nds_table_for_invoice") as free_mock:
					_reconcile_stale_table_occupancy(table)
		free_mock.assert_called_once_with(invoice, table=table)


class TestPosOpenOrderRegression(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.menu_name = None
		cls.restaurant_name = None
		cls.table_name = None
		cls.room_name = None
		register_standard_isolated_fixture_cleanup(cls)

		frappe.set_user("Administrator")
		ensure_pos_operator_permissions()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		item_code = code(cls.run_id, "tbl-item")
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

		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(item_code, 50)],
			menu_name=code(cls.run_id, "tbl-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
		)
		cls.room_name = ensure_test_room(cls.run_id, cls.branch)
		cls.table_name = ensure_test_table(cls.run_id, cls.restaurant_name, cls.branch, cls.room_name)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		cls.item_code = item_code

	def setUp(self):
		if not self.pos_profile:
			self.skipTest("No POS Profile")
		self.created_invoices = []
		frappe.db.set_value(
			"NDS Table",
			self.table_name,
			{"occupied": 0, "current_invoice": None},
		)

	def tearDown(self):
		end_test_pos_cashier_session()
		for inv in self.created_invoices:
			cleanup_invoice_and_kots(inv)
		frappe.db.set_value(
			"NDS Table",
			self.table_name,
			{"occupied": 0, "current_invoice": None},
		)

	def test_second_draft_on_occupied_table_refused_for_captain(self):
		captain = ensure_test_pos_captain()
		switch_test_pos_operator_session(
			self.pos_profile, captain, register_cleanup=self.addCleanup
		)

		first = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 50}],
			table=self.table_name,
			order_type="Dine In",
			generate_kot=0,
		)
		self.created_invoices.append(first["invoice"])

		with self.assertRaises(frappe.ValidationError) as cm:
			_resolve_invoice_for_new_table_order(self.table_name)
		self.assertIn("reopen it", str(cm.exception).lower())

	def test_manager_takeover_updates_same_invoice(self):
		manager = ensure_test_pos_manager()
		switch_test_pos_operator_session(
			self.pos_profile, manager, register_cleanup=self.addCleanup
		)

		first = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 50}],
			table=self.table_name,
			order_type="Dine In",
			generate_kot=0,
		)
		self.created_invoices.append(first["invoice"])

		second = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 2, "rate": 50}],
			table=self.table_name,
			order_type="Dine In",
			generate_kot=0,
		)
		self.assertEqual(second["invoice"], first["invoice"])


class TestKotTrashRegression(unittest.TestCase):
	def test_trash_only_frees_table_when_invoice_matches(self):
		table = "T-KOT-TRASH"
		with patch("nds_restaurant.api.pos._free_nds_table_for_invoice") as free_mock:
			doc = frappe._dict(
				{
					"name": "INV-A",
					"custom_nds_table": table,
					"meta": frappe._dict(has_field=lambda f: False),
				}
			)
			on_pos_invoice_trash(doc)
			free_mock.assert_called_once_with("INV-A", doc=doc)


class TestNdsCashierPayment(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		register_standard_isolated_fixture_cleanup(cls)
		frappe.set_user("Administrator")
		ensure_pos_operator_permissions()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return
		cls.branch = ensure_test_branch(cls.run_id)
		item_code = code(cls.run_id, "pay-item")
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
		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(item_code, 25)],
			menu_name=code(cls.run_id, "pay-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
			order_type_menus=[("Take Away", cls.menu_name)],
		)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		cls.item_code = item_code

	def setUp(self):
		if not getattr(self, "pos_profile", None):
			self.skipTest("No POS Profile")
		self.cashier = ensure_test_nds_only_cashier()
		begin_test_pos_cashier_session(self.pos_profile, user=self.cashier, register_cleanup=self.addCleanup)
		self.created_invoices = []

	def tearDown(self):
		end_test_pos_cashier_session()
		for inv in self.created_invoices:
			cleanup_invoice_and_kots(inv)

	def test_cashier_can_submit_payment(self):
		import json

		order = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 25}],
			order_type="Take Away",
			generate_kot=0,
		)
		invoice = order["invoice"]
		self.created_invoices.append(invoice)
		doc = frappe.get_doc("POS Invoice", invoice)
		amount = doc.rounded_total or doc.grand_total
		result = submit_payment(
			invoice,
			json.dumps([{"mode_of_payment": "Cash", "amount": amount}]),
		)
		self.assertEqual(result.get("invoice"), invoice)
		self.assertEqual(frappe.db.get_value("POS Invoice", invoice, "docstatus"), 1)


class TestDailyPnLAccessRegression(unittest.TestCase):
	def test_captain_cannot_view_daily_pnl(self):
		captain = ensure_test_pos_captain()
		frappe.set_user(captain)
		branch = frappe.db.get_value("Branch", {}, "name")
		if not branch:
			self.skipTest("No branch")
		with self.assertRaises(frappe.PermissionError):
			get_daily_pnl(branch)
		frappe.set_user("Administrator")
