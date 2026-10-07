"""
Unit tests for P3-T6: KOT diff key change.
Tests that KOT diff now uses (item_code, notes, addon_group_id) as key.
"""

import frappe
import unittest
from nds_restaurant.api.kot import kot_execute
from nds_restaurant.tests.test_helpers import (
	code,
	cleanup_invoice_and_kots,
	delete_if_exists,
	delete_items,
	ensure_pos_opening_entry,
	get_pos_profile_with_restaurant,
	new_test_run_id,
)


class TestKOTDiff(unittest.TestCase):
	"""Test KOT diff with composite key."""

	_table_snapshot_fields = ("occupied", "current_invoice", "latest_invoice_time")

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.production_unit_name = None

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		delete_if_exists("NDS Production Unit", cls.production_unit_name)
		delete_items(cls.item_codes)

	def setUp(self):
		frappe.set_user("Administrator")
		self.created_invoices = []

		self.item = self._create_item("item")
		self.addon = self._create_item("addon")

		self.pos_profile = get_pos_profile_with_restaurant()
		if not self.pos_profile:
			self.skipTest("No POS Profile with Restaurant linked")

		self.opening_entry = ensure_pos_opening_entry(self.pos_profile)
		self.production_unit = self._get_test_production_unit()
		self.table = self._get_test_table()
		self._table_snapshot = frappe.db.get_value(
			"NDS Table",
			self.table,
			self._table_snapshot_fields,
			as_dict=True,
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		for invoice_name in list(self.created_invoices):
			cleanup_invoice_and_kots(invoice_name)
		if self.table and self._table_snapshot:
			frappe.db.set_value("NDS Table", self.table, self._table_snapshot)

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

	def _get_test_production_unit(self):
		unit_name = code(self.run_id, "kitchen")
		if not frappe.db.exists("NDS Production Unit", unit_name):
			warehouse = frappe.db.get_value("POS Profile", self.pos_profile, "warehouse")
			frappe.get_doc(
				{
					"doctype": "NDS Production Unit",
					"name": unit_name,
					"pos_profile": self.pos_profile,
					"warehouse": warehouse,
					"item_groups": [{"item_group": "Products"}],
				}
			).insert(ignore_permissions=True)
			type(self).production_unit_name = unit_name
		return unit_name

	def _get_test_table(self):
		table_name = frappe.db.get_value("NDS Table", {}, "name")
		if not table_name:
			self.skipTest("No test table available")
		return table_name

	def _create_test_invoice(self, items):
		"""Helper to create a test POS Invoice."""
		doc = frappe.get_doc(
			{
				"doctype": "POS Invoice",
				"pos_profile": self.pos_profile,
				"company": frappe.db.get_value("POS Profile", self.pos_profile, "company"),
				"customer": frappe.db.get_value("Customer", {}, "name"),
				"custom_nds_table": self.table,
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
