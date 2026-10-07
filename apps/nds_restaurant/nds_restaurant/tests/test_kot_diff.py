"""
Unit tests for P3-T6: KOT diff key change.
Tests that KOT diff now uses (item_code, notes, addon_group_id) as key.
"""

import frappe
import unittest
from nds_restaurant.api.kot import kot_execute
from nds_restaurant.tests.test_helpers import (
	begin_test_pos_cashier_session,
	code,
	cleanup_invoice_and_kots,
	end_test_pos_cashier_session,
	ensure_test_branch,
	ensure_test_menu,
	ensure_test_pos_profile,
	ensure_test_production_unit,
	ensure_test_restaurant,
	ensure_test_room,
	ensure_test_table,
	new_test_run_id,
	register_standard_isolated_fixture_cleanup,
)


class TestKOTDiff(unittest.TestCase):
	"""Test KOT diff with composite key."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.menu_name = None
		cls.restaurant_name = None
		cls.room_name = None
		cls.table_name = None
		cls.production_unit_name = None
		cls.pos_profile = None
		register_standard_isolated_fixture_cleanup(cls)

		frappe.set_user("Administrator")
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			raise unittest.SkipTest("No Company in site")

		cls.branch = ensure_test_branch(cls.run_id)
		cls.item = cls._create_item("item")
		cls.addon = cls._create_item("addon")
		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item.name, 100), (cls.addon.name, 25)],
			menu_name=code(cls.run_id, "kot-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
		)
		cls.room_name = ensure_test_room(cls.run_id, cls.branch)
		cls.table_name = ensure_test_table(
			cls.run_id, cls.restaurant_name, cls.branch, cls.room_name
		)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		if not cls.pos_profile:
			raise unittest.SkipTest("No template POS Profile to clone")

		warehouse = frappe.db.get_value("POS Profile", cls.pos_profile, "warehouse")
		cls.production_unit_name = ensure_test_production_unit(
			cls.run_id, cls.pos_profile, warehouse
		)

	def setUp(self):
		frappe.set_user("Administrator")
		self.created_invoices = []
		if not self.pos_profile:
			self.skipTest("No test POS Profile")
		self.opening_entry = begin_test_pos_cashier_session(
			self.pos_profile, register_cleanup=self.addCleanup
		)

	def tearDown(self):
		end_test_pos_cashier_session()
		for invoice_name in list(self.created_invoices):
			cleanup_invoice_and_kots(invoice_name)

	@classmethod
	def _create_item(cls, suffix):
		item_code = code(cls.run_id, suffix)
		cls.item_codes.append(item_code)
		if frappe.db.exists("Item", item_code):
			return frappe.get_doc("Item", item_code)

		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)

	def _create_test_invoice(self, items):
		"""Helper to create a test POS Invoice."""
		doc = frappe.get_doc(
			{
				"doctype": "POS Invoice",
				"pos_profile": self.pos_profile,
				"company": frappe.db.get_value("POS Profile", self.pos_profile, "company"),
				"customer": frappe.db.get_value("Customer", {}, "name"),
				"custom_nds_table": self.table_name,
				"items": items,
			}
		)
		if frappe.get_meta("POS Invoice").has_field("pos_opening_entry"):
			doc.pos_opening_entry = self.opening_entry
		doc.set_missing_values()
		doc.save(ignore_permissions=True)
		self.created_invoices.append(doc.name)
		return doc

	def test_kot_diff_treats_different_notes_as_separate(self):
		"""Test that items with different notes create separate KOT lines."""
		invoice = self._create_test_invoice(
			[
				{
					"item_code": self.item.name,
					"qty": 1,
					"rate": 100,
					"custom_nds_notes": "No onions",
				},
				{
					"item_code": self.item.name,
					"qty": 1,
					"rate": 100,
					"custom_nds_notes": "Extra spicy",
				},
			]
		)

		kots = kot_execute(invoice.name)
		self.assertTrue(kots)

		kot = frappe.get_doc("NDS KOT", kots[0])
		self.assertEqual(len(kot.items), 2)

		notes = {row.comments for row in kot.items}
		self.assertIn("No onions", notes)
		self.assertIn("Extra spicy", notes)

	def test_kot_diff_treats_addons_separately(self):
		"""Test that add-ons are tracked separately from parent."""
		line_id = "test-line-123"

		invoice = self._create_test_invoice(
			[
				{
					"item_code": self.item.name,
					"qty": 2,
					"rate": 100,
					"custom_nds_notes": "",
				},
				{
					"item_code": self.addon.name,
					"qty": 2,
					"rate": 25,
					"custom_is_addon": 1,
					"custom_addon_group_id": line_id,
				},
			]
		)

		kots = kot_execute(invoice.name)
		kot = frappe.get_doc("NDS KOT", kots[0])
		self.assertEqual(len(kot.items), 2)

		addon_row = next((r for r in kot.items if r.item == self.addon.name), None)
		self.assertIsNotNone(addon_row)
		self.assertEqual(addon_row.is_addon, 1)
		self.assertEqual(addon_row.addon_group_id, line_id)

	def test_kot_diff_modified_with_notes_change(self):
		"""Test that changing notes produces a Modified KOT with old and new lines."""
		invoice = self._create_test_invoice(
			[
				{
					"item_code": self.item.name,
					"qty": 1,
					"rate": 100,
					"custom_nds_notes": "Original notes",
				}
			]
		)

		kot_execute(invoice.name)

		invoice.reload()
		invoice.items[0].custom_nds_notes = "Changed notes"
		invoice.save(ignore_permissions=True)

		kots2 = kot_execute(invoice.name)
		kot2 = frappe.get_doc("NDS KOT", kots2[0])
		self.assertEqual(kot2.kot_type, "Modified")
		self.assertEqual(len(kot2.items), 2)
		comments = {row.comments for row in kot2.items}
		self.assertIn("Original notes", comments)
		self.assertIn("Changed notes", comments)

	def test_modified_kot_no_ghost_zero_qty_lines_on_later_edit(self):
		"""Qty-0 removed lines from a Modified KOT must not reappear on the next diff."""
		invoice = self._create_test_invoice(
			[
				{
					"item_code": self.item.name,
					"qty": 1,
					"rate": 100,
					"custom_nds_notes": "Original notes",
				}
			]
		)

		kot_execute(invoice.name)

		invoice.reload()
		invoice.items[0].custom_nds_notes = "Changed notes"
		invoice.save(ignore_permissions=True)
		kot_execute(invoice.name)

		invoice.reload()
		invoice.append(
			"items",
			{
				"item_code": self.addon.name,
				"qty": 1,
				"rate": 25,
			},
		)
		invoice.save(ignore_permissions=True)

		kots3 = kot_execute(invoice.name)
		kot3 = frappe.get_doc("NDS KOT", kots3[0])
		self.assertEqual(kot3.kot_type, "Modified")
		comments = {row.comments for row in kot3.items}
		self.assertNotIn("Original notes", comments)

	def test_kot_cancelled_qty_calculated(self):
		"""Test that cancelled_qty is set correctly on cancel KOTs."""
		invoice = self._create_test_invoice(
			[
				{
					"item_code": self.item.name,
					"qty": 3,
					"rate": 100,
				}
			]
		)

		kot_execute(invoice.name)

		invoice.reload()
		invoice.items[0].qty = 1
		invoice.save(ignore_permissions=True)

		kots2 = kot_execute(invoice.name)
		kot2 = frappe.get_doc("NDS KOT", kots2[0])
		self.assertEqual(kot2.kot_type, "Partially Cancelled")
		self.assertEqual(kot2.items[0].cancelled_qty, 2)
