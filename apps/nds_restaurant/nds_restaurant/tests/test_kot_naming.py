# Copyright (c) 2026, NDS and contributors
# License: MIT

import unittest

import frappe

from nds_restaurant.kot_naming import CNCL_KOT_SERIES, cancellation_kot_naming_series, get_kot_naming_series_options
from nds_restaurant.install import ensure_cncl_kot_naming_series_option


class TestKotNamingSeries(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._ps_name = None
		self._original_value = None

	def tearDown(self):
		if self._ps_name and frappe.db.exists("Property Setter", self._ps_name):
			if self._original_value is not None:
				frappe.db.set_value("Property Setter", self._ps_name, "value", self._original_value)
			else:
				frappe.delete_doc("Property Setter", self._ps_name, force=True, ignore_permissions=True)

	def _ensure_property_setter_options(self, options_text):
		existing = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": "NDS KOT",
				"field_name": "naming_series",
				"property": "options",
			},
			"name",
		)
		if existing:
			self._ps_name = existing
			self._original_value = frappe.db.get_value("Property Setter", existing, "value")
			frappe.db.set_value("Property Setter", existing, "value", options_text)
			return

		doc = frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": "NDS KOT",
				"field_name": "naming_series",
				"property": "options",
				"property_type": "Text",
				"value": options_text,
			}
		).insert(ignore_permissions=True)
		self._ps_name = doc.name
		self._original_value = None

	def test_cancellation_series_uses_property_setter_options(self):
		self._ensure_property_setter_options("KOT-.#####\nCNCL-KOT-.#####")
		frappe.clear_cache(doctype="NDS KOT")
		self.assertEqual(cancellation_kot_naming_series("KOT-.#####"), CNCL_KOT_SERIES)

	def test_after_migrate_appends_cncl_to_existing_property_setter(self):
		self._ensure_property_setter_options("KOT-.#####")
		frappe.clear_cache(doctype="NDS KOT")
		ensure_cncl_kot_naming_series_option()
		ensure_cncl_kot_naming_series_option()
		options = get_kot_naming_series_options()
		self.assertIn(CNCL_KOT_SERIES, options)
		self.assertIn("KOT-.#####", options)
