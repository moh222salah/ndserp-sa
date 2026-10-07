# Copyright (c) 2026, NDS and contributors
# License: MIT

import unittest

import frappe

from nds_restaurant.api.pos import (
	_coalesce_order_type,
	_coalesce_table,
	_set_nds_table_occupied,
	_sync_nds_table_after_order_save,
)


class TestPosInputCoalescing(unittest.TestCase):
	def test_coalesce_table_prefers_explicit_argument(self):
		form = {"custom_nds_table": "T-ALT", "restaurant_table": "T-REST"}
		self.assertEqual(_coalesce_table("T-MAIN", form=form), "T-MAIN")

	def test_coalesce_table_reads_alternate_keys(self):
		form = {"restaurant_table": "T-REST"}
		self.assertEqual(_coalesce_table(None, form=form), "T-REST")
		form = {"custom_nds_table": "T-NDS", "table": "T-PLAIN"}
		self.assertEqual(_coalesce_table(None, form=form), "T-PLAIN")

	def test_coalesce_order_type_prefers_explicit_argument(self):
		form = {"custom_nds_order_type": "Take Away"}
		self.assertEqual(_coalesce_order_type("Dine In", form=form), "Dine In")

	def test_coalesce_order_type_reads_alternate_keys(self):
		form = {"custom_nds_order_type": "Take Away"}
		self.assertEqual(_coalesce_order_type(None, form=form), "Take Away")
		form = {"order_type": "Dine In", "custom_nds_order_type": "Take Away"}
		self.assertEqual(_coalesce_order_type(None, form=form), "Dine In")


class TestPosTableSync(unittest.TestCase):
	_table_snapshot_fields = ("occupied", "current_invoice", "latest_invoice_time")

	def setUp(self):
		frappe.set_user("Administrator")
		self._table = frappe.db.get_value("NDS Table", {}, "name")
		if not self._table:
			return
		self._table_snapshot = frappe.db.get_value(
			"NDS Table",
			self._table,
			self._table_snapshot_fields,
			as_dict=True,
		)

	def tearDown(self):
		if not getattr(self, "_table", None) or not getattr(self, "_table_snapshot", None):
			return
		frappe.db.set_value("NDS Table", self._table, self._table_snapshot)

	def test_take_away_frees_previous_table(self):
		if not self._table:
			self.skipTest("No NDS Table available")

		frappe.db.set_value(
			"NDS Table",
			self._table,
			{"occupied": 1, "current_invoice": "POS-TEST-OLD"},
		)

		_sync_nds_table_after_order_save(
			order_type="Take Away",
			table=None,
			previous_table=self._table,
			invoice_name="POS-TEST-NEW",
		)

		row = frappe.db.get_value(
			"NDS Table",
			self._table,
			["occupied", "current_invoice"],
			as_dict=True,
		)
		self.assertEqual(row.occupied, 0)
		self.assertIsNone(row.current_invoice)

	def test_dine_in_marks_table_occupied(self):
		if not self._table:
			self.skipTest("No NDS Table available")

		invoice = "POS-TABLE-OCCUPY-TEST"
		_set_nds_table_occupied(self._table, invoice, occupied=True)

		row = frappe.db.get_value(
			"NDS Table",
			self._table,
			["occupied", "current_invoice"],
			as_dict=True,
		)
		self.assertEqual(row.occupied, 1)
		self.assertEqual(row.current_invoice, invoice)

		_set_nds_table_occupied(self._table, None, occupied=False)
		row = frappe.db.get_value(
			"NDS Table",
			self._table,
			["occupied", "current_invoice"],
			as_dict=True,
		)
		self.assertEqual(row.occupied, 0)
		self.assertIsNone(row.current_invoice)

	def test_dine_in_without_table_frees_previous_table(self):
		if not self._table:
			self.skipTest("No NDS Table available")

		frappe.db.set_value(
			"NDS Table",
			self._table,
			{"occupied": 1, "current_invoice": "POS-TEST-OLD"},
		)

		_sync_nds_table_after_order_save(
			order_type="Dine In",
			table=None,
			previous_table=self._table,
			invoice_name="POS-TEST-NEW",
		)

		row = frappe.db.get_value(
			"NDS Table",
			self._table,
			["occupied", "current_invoice"],
			as_dict=True,
		)
		self.assertEqual(row.occupied, 0)
		self.assertIsNone(row.current_invoice)
