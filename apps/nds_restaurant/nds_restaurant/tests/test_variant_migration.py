"""
Unit tests for P3-T2: variant/add-on migration patch.
Tests migration logic and idempotency.
"""

import frappe
import unittest
from nds_restaurant.patches.v1_1.migrate_menu_variants_addons import execute, _parse_codes
from nds_restaurant.tests.test_helpers import (
	code,
	delete_items,
	delete_menus,
	ensure_test_branch,
	ignore_menu_variant_validation,
	new_test_run_id,
	set_menu_item_variants_text,
)


class TestVariantMigration(unittest.TestCase):
	"""Test variant migration patch."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.branch = None
		cls.menu_name = None
		cls.menu2_name = None
		cls.item_codes = []

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		delete_menus([cls.menu2_name, cls.menu_name])
		delete_items(cls.item_codes)

	def setUp(self):
		frappe.set_user("Administrator")
		if not self.branch:
			type(self).branch = ensure_test_branch(self.run_id)

		self.parent_item = self._create_item("parent")
		self.variant1 = self._create_item("var1")
		self.variant2 = self._create_item("var2")
		self.addon1 = self._create_item("addon1")
		self.addon2 = self._create_item("addon2")

		if not self.menu_name:
			self.menu_name = code(self.run_id, "menu")
			frappe.get_doc(
				{
					"doctype": "NDS Menu",
					"name": self.menu_name,
					"branch": self.branch,
					"enabled": 1,
					"items": [
						{
							"item": self.parent_item.name,
							"rate": 100,
							"variants": "{}, {}".format(self.variant1.name, self.variant2.name),
							"addons": "{}, {}".format(self.addon1.name, self.addon2.name),
						}
					],
				}
			).insert(ignore_permissions=True)
			type(self).menu_name = self.menu_name

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

	def test_parse_codes(self):
		"""Test the code parsing helper."""
		self.assertEqual(_parse_codes("A, B, C"), ["A", "B", "C"])
		self.assertEqual(_parse_codes("A,B,C"), ["A", "B", "C"])
		self.assertEqual(_parse_codes("  A  ,  B  "), ["A", "B"])
		self.assertEqual(_parse_codes(""), [])
		self.assertEqual(_parse_codes(None), [])

	def test_migration_populates_child_tables(self):
		"""Test that migration moves text to child tables."""
		execute()

		variant_codes = set(
			frappe.db.sql_list(
				"""
				SELECT item FROM `tabNDS POS Item Variant`
				WHERE parent = %s AND parenttype = 'Item'
				""",
				(self.parent_item.name,),
			)
		)
		self.assertIn(self.variant1.name, variant_codes)
		self.assertIn(self.variant2.name, variant_codes)

		addon_codes = set(
			frappe.db.sql_list(
				"""
				SELECT item FROM `tabNDS Item Add On`
				WHERE parent = %s AND parenttype = 'Item'
				""",
				(self.parent_item.name,),
			)
		)
		self.assertIn(self.addon1.name, addon_codes)
		self.assertIn(self.addon2.name, addon_codes)

	def test_migration_idempotency(self):
		"""Test that running migration twice doesn't duplicate rows."""
		execute()
		execute()

		variant_codes = frappe.db.sql_list(
			"""
			SELECT item FROM `tabNDS POS Item Variant`
			WHERE parent = %s AND parenttype = 'Item'
			""",
			(self.parent_item.name,),
		)
		self.assertEqual(len(variant_codes), len(set(variant_codes)), "Variants duplicated")

		addon_codes = frappe.db.sql_list(
			"""
			SELECT item FROM `tabNDS Item Add On`
			WHERE parent = %s AND parenttype = 'Item'
			""",
			(self.parent_item.name,),
		)
		self.assertEqual(len(addon_codes), len(set(addon_codes)), "Add-ons duplicated")

	def test_migration_skips_unknown_codes(self):
		"""Test that unknown item codes are skipped."""
		set_menu_item_variants_text(
			self.menu,
			0,
			"{}, UNKNOWN-CODE".format(self.variant1.name),
		)

		execute()

		variant_codes = set(
			frappe.db.sql_list(
				"""
				SELECT item FROM `tabNDS POS Item Variant`
				WHERE parent = %s AND parenttype = 'Item'
				""",
				(self.parent_item.name,),
			)
		)
		self.assertIn(self.variant1.name, variant_codes)
		self.assertNotIn("UNKNOWN-CODE", variant_codes)

	def test_migration_unions_across_menus(self):
		"""Test that codes from multiple menus are unioned."""
		variant3 = self._create_item("var3")
		menu2_name = code(self.run_id, "menu2")
		type(self).menu2_name = menu2_name
		with ignore_menu_variant_validation():
			frappe.get_doc(
				{
					"doctype": "NDS Menu",
					"name": menu2_name,
					"branch": self.branch,
					"enabled": 1,
					"items": [
						{
							"item": self.parent_item.name,
							"rate": 100,
							"variants": variant3.name,
						},
						{"item": variant3.name, "rate": 100},
						{"item": self.variant1.name, "rate": 90},
						{"item": self.variant2.name, "rate": 90},
					],
				}
			).insert(ignore_permissions=True)

		execute()

		variant_codes = set(
			frappe.db.sql_list(
				"""
				SELECT item FROM `tabNDS POS Item Variant`
				WHERE parent = %s AND parenttype = 'Item'
				""",
				(self.parent_item.name,),
			)
		)
		self.assertIn(self.variant1.name, variant_codes)
		self.assertIn(self.variant2.name, variant_codes)
		self.assertIn(variant3.name, variant_codes)
