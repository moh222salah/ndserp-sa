"""Tests for the NDS Custom Reports suppression policy."""

import frappe
from frappe.tests.utils import FrappeTestCase

from ndserp.setup.custom_report_policy import (
    filter_custom_report_sections,
    reject_nonstandard_report,
)


class TestCustomReportPolicy(FrappeTestCase):
    def test_english_custom_reports_section_is_removed(self):
        sections = [
            {"label": "Custom Documents", "links": [{"label": "NDS Customer"}]},
            {"label": "Custom Reports", "links": [{"label": "My Query Report"}]},
            {"label": "Sales Reports", "links": [{"label": "Sales Register"}]},
        ]

        self.assertEqual(
            filter_custom_report_sections(sections),
            [sections[0], sections[2]],
        )

    def test_arabic_custom_reports_section_is_removed(self):
        sections = [
            {"label": "المستندات المخصصة", "links": []},
            {"label": "تقارير مخصصة", "links": [{"label": "تقرير مخصص"}]},
        ]

        self.assertEqual(filter_custom_report_sections(sections), [sections[0]])

    def test_other_sections_and_empty_input_are_preserved(self):
        sections = [{"label": "Financial Reports", "links": []}]
        self.assertEqual(filter_custom_report_sections(sections), sections)
        self.assertEqual(filter_custom_report_sections(None), [])

    def test_nonstandard_report_creation_is_rejected(self):
        doc = frappe._dict({"is_standard": "No"})
        with self.assertRaises(frappe.ValidationError):
            reject_nonstandard_report(doc)

    def test_standard_report_is_allowed(self):
        reject_nonstandard_report(frappe._dict({"is_standard": "Yes"}))

    def test_migration_bypasses_user_creation_guard(self):
        old_value = getattr(frappe.flags, "in_migrate", False)
        try:
            frappe.flags.in_migrate = True
            reject_nonstandard_report(frappe._dict({"is_standard": "No"}))
        finally:
            frappe.flags.in_migrate = old_value
