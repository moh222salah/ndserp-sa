"""
Unit tests for P3-T7: server-side stock validation.
Tests that orders cannot exceed availability.
"""

import frappe
import unittest
from nds_restaurant.api.pos import create_or_update_order
from nds_restaurant.tests.test_helpers import (
	code,
	cleanup_invoice_and_kots,
	delete_if_exists,
	delete_items,
	ensure_bin_qty,
	ensure_pos_opening_entry,
	get_pos_profile_with_restaurant,
	new_test_run_id,
)


class TestStockValidation(unittest.TestCase):
	"""Test server-side stock blocking."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.recipe_name = None
		cls.recipe_item = None
		cls.stock_item = None

		frappe.set_user("Administrator")
		cls.pos_profile = get_pos_profile_with_restaurant()
		if not cls.pos_profile:
			return
		cls.warehouse = frappe.db.get_value("POS Profile", cls.pos_profile, "warehouse")
		cls._build_recipe_fixture()
		cls._build_stock_fixture()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		if cls.recipe_name:
			delete_if_exists("NDS Recipe", cls.recipe_name)
		delete_items(cls.item_codes)

	@classmethod
	def _build_recipe_fixture(cls):
		ingredient_code = code(cls.run_id, "ing")
		recipe_item_code = code(cls.run_id, "recipe")
		cls.item_codes.extend([ingredient_code, recipe_item_code])

		if not frappe.db.exists("Item", ingredient_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": ingredient_code,
					"item_name": ingredient_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 1,
				}
			).insert(ignore_permissions=True)
		ensure_bin_qty(ingredient_code, cls.warehouse, 6)

		if not frappe.db.exists("Item", recipe_item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": recipe_item_code,
					"item_name": recipe_item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("NDS Recipe", {"item": recipe_item_code}):
			recipe = frappe.get_doc(
				{
					"doctype": "NDS Recipe",
					"item": recipe_item_code,
					"enabled": 1,
					"ingredients": [{"ingredient": ingredient_code, "qty": 2}],
				}
			).insert(ignore_permissions=True)
			cls.recipe_name = recipe.name

		cls.recipe_item = frappe.get_doc("Item", recipe_item_code)

	@classmethod
	def _build_stock_fixture(cls):
		stock_item_code = code(cls.run_id, "direct")
		cls.item_codes.append(stock_item_code)
		if not frappe.db.exists("Item", stock_item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": stock_item_code,
					"item_name": stock_item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 1,
				}
			).insert(ignore_permissions=True)
		ensure_bin_qty(stock_item_code, cls.warehouse, 5)
		cls.stock_item = frappe.get_doc("Item", stock_item_code)

	def setUp(self):
		frappe.set_user("Administrator")
		self.created_invoices = []
		if not self.pos_profile:
			self.skipTest("No POS Profile with Restaurant linked")
		ensure_pos_opening_entry(self.pos_profile)

	def tearDown(self):
		for invoice_name in self.created_invoices:
			cleanup_invoice_and_kots(invoice_name)

	def test_stock_validation_blocks_excess_recipe_item(self):
		items = [{"item_code": self.recipe_item.name, "qty": 4, "rate": 100}]

		with self.assertRaises(frappe.ValidationError) as cm:
			create_or_update_order(
				pos_profile=self.pos_profile,
				items=items,
				order_type="Take Away",
				generate_kot=0,
			)

		self.assertIn("portions", str(cm.exception).lower())
		self.assertIn("available", str(cm.exception).lower())

	def test_stock_validation_blocks_excess_stock_item(self):
		items = [{"item_code": self.stock_item.name, "qty": 6, "rate": 50}]

		with self.assertRaises(frappe.ValidationError) as cm:
			create_or_update_order(
				pos_profile=self.pos_profile,
				items=items,
				order_type="Take Away",
				generate_kot=0,
			)

		self.assertIn("portions", str(cm.exception).lower())
		self.assertIn("available", str(cm.exception).lower())

	def test_stock_validation_allows_within_limit(self):
		items = [{"item_code": self.recipe_item.name, "qty": 2, "rate": 100}]

		result = create_or_update_order(
			pos_profile=self.pos_profile,
			items=items,
			order_type="Take Away",
			generate_kot=0,
		)

		self.assertIn("invoice", result)
		self.created_invoices.append(result["invoice"])

	def test_stock_validation_checks_incremental_qty(self):
		result1 = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.recipe_item.name, "qty": 2, "rate": 100}],
			order_type="Take Away",
			generate_kot=0,
		)
		invoice_name = result1["invoice"]
		self.created_invoices.append(invoice_name)

		with self.assertRaises(frappe.ValidationError) as cm:
			create_or_update_order(
				pos_profile=self.pos_profile,
				items=[{"item_code": self.recipe_item.name, "qty": 4, "rate": 100}],
				invoice=invoice_name,
				order_type="Take Away",
				generate_kot=0,
			)

		self.assertIn("available", str(cm.exception).lower())
