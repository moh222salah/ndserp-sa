"""
Unit tests for P3-T3: menu and item validation.
Tests that variants and add-ons must be in the menu.
"""

import frappe
import unittest
from nds_restaurant.tests.test_helpers import (
	code,
	delete_items,
	delete_menus,
	ensure_test_branch,
	ignore_item_menu_link_validation,
	new_test_run_id,
)


class TestMenuValidation(unittest.TestCase):
	"""Test menu validation for variants and add-ons."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.branch = ensure_test_branch(cls.run_id)
		cls.menu_name = code(cls.run_id, "menu")
		cls.item_codes = []

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		delete_menus([cls.menu_name])
		delete_items(cls.item_codes)

	def setUp(self):
		frappe.set_user("Administrator")

		self.parent_item = self._create_item("parent")
		self.variant_in_menu = self._create_item("var-in")
		self.variant_not_in_menu = self._create_item("var-out")
		self.addon_in_menu = self._create_item("addon-in")
		self.addon_not_in_menu = self._create_item("addon-out")

		if not frappe.db.exists("NDS Menu", self.menu_name):
			frappe.get_doc(
				{
					"doctype": "NDS Menu",
					"name": self.menu_name,
					"branch": self.branch,
					"enabled": 1,
					"items": [
						{"item": self.parent_item.name, "rate": 100},
						{"item": self.variant_in_menu.name, "rate": 90},
						{"item": self.addon_in_menu.name, "rate": 20},
						{
							"item": self.variant_not_in_menu.name,
							"rate": 90,
							"disabled": 1,
						},
						{
							"item": self.addon_not_in_menu.name,
							"rate": 20,
							"disabled": 1,
						},
					],
				}
			).insert(ignore_permissions=True)

		self.menu = frappe.get_doc("NDS Menu", self.menu_name)

	def _create_item(self, suffix):
		item_code = code(self.run_id, suffix)
		type(self).item_codes.append(item_code)
		if frappe.db.exists("Item", item_code):
			return frappe.get_doc("Item", item_code)

		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)

	def _set_parent_variants_addons(self, variants, addons):
		parent = frappe.get_doc("Item", self.parent_item.name)
		parent.set("custom_pos_item_variants", [{"item": v} for v in variants])
		parent.set("custom_pos_add_on_items", [{"item": a} for a in addons])
		with ignore_item_menu_link_validation():
			parent.save(ignore_permissions=True)

	def test_menu_validate_rejects_variant_not_in_menu(self):
		"""Test that menu validation rejects variants not in menu."""
		self._set_parent_variants_addons(
			[self.variant_in_menu.name, self.variant_not_in_menu.name],
			[self.addon_in_menu.name],
		)

		self.menu.reload()
		with self.assertRaises(frappe.ValidationError) as cm:
			self.menu.validate()

		self.assertIn(self.variant_not_in_menu.name, str(cm.exception))
		self.assertIn("not in menu", str(cm.exception).lower())

	def test_menu_validate_rejects_addon_not_in_menu(self):
		"""Test that menu validation rejects add-ons not in menu."""
		self._set_parent_variants_addons(
			[self.variant_in_menu.name],
			[self.addon_in_menu.name, self.addon_not_in_menu.name],
		)

		self.menu.reload()
		with self.assertRaises(frappe.ValidationError) as cm:
			self.menu.validate()

		self.assertIn(self.addon_not_in_menu.name, str(cm.exception))
		self.assertIn("not in menu", str(cm.exception).lower())

	def test_menu_validate_allows_all_in_menu(self):
		"""Test that validation passes when all variants/addons are in menu."""
		self._set_parent_variants_addons(
			[self.variant_in_menu.name],
			[self.addon_in_menu.name],
		)

		self.menu.reload()
		self.menu.validate()

	def test_item_validate_rejects_self_as_variant(self):
		"""Test that an item cannot be its own variant."""
		item_code = code(self.run_id, "self-var")
		type(self).item_codes.append(item_code)
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)
		item.append("custom_pos_item_variants", {"item": item.name})

		with self.assertRaises(frappe.ValidationError) as cm:
			item.save(ignore_permissions=True)

		self.assertIn("cannot be its own variant", str(cm.exception).lower())

	def test_item_validate_checks_menus(self):
		"""Test that item validation checks all menus containing the item."""
		var_out2 = self._create_item("var-out2")
		self.menu.append(
			"items",
			{"item": var_out2.name, "rate": 90, "disabled": 1},
		)
		self.menu.save(ignore_permissions=True)

		self._set_parent_variants_addons(
			[self.variant_in_menu.name, var_out2.name],
			[self.addon_in_menu.name],
		)

		parent = frappe.get_doc("Item", self.parent_item.name)
		with self.assertRaises(frappe.ValidationError) as cm:
			parent.save(ignore_permissions=True)

		self.assertIn("not in menu", str(cm.exception).lower())
