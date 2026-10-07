# Copyright (c) 2026, NDS and contributors
# License: MIT

import unittest

import frappe

from nds_restaurant.install import ensure_pos_operator_permissions
from nds_restaurant.role_permissions import (
	ensure_pos_invoice_operator_permissions,
	snapshot_custom_docperm,
)
from nds_restaurant.tests.test_helpers import ensure_test_pos_captain, ensure_test_pos_manager


class TestPosOperatorPermissions(unittest.TestCase):
	"""Ensure POS permission setup never strips standard ERPNext role access."""

	@classmethod
	def setUpClass(cls):
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Account"):
			cls.skip_site = True
			return
		cls.skip_site = False
		cls.doctype = "Account"
		cls.standard_role = "Accounts User"
		if not frappe.db.exists("Role", cls.standard_role):
			cls.standard_role = None

	def setUp(self):
		if getattr(self.__class__, "skip_site", True):
			self.skipTest("Frappe site / Account doctype not available")
		frappe.set_user("Administrator")

	def test_standard_role_permissions_preserved_and_idempotent(self):
		if not self.standard_role:
			self.skipTest("Accounts User role not present")

		before = snapshot_custom_docperm(self.doctype, self.standard_role)
		ensure_pos_operator_permissions()
		after_first = snapshot_custom_docperm(self.doctype, self.standard_role)
		ensure_pos_operator_permissions()
		after_second = snapshot_custom_docperm(self.doctype, self.standard_role)

		self.assertEqual(after_first, after_second, "Second run must not change standard role perms")

		if before:
			for field in ("read", "write", "create", "select"):
				if int(before.get(field) or 0):
					self.assertGreaterEqual(
						int((after_second or {}).get(field) or 0),
						int(before.get(field) or 0),
						msg=f"{self.standard_role} lost {field} on {self.doctype}",
					)

	def test_captain_has_read_and_select_on_account(self):
		ensure_test_pos_captain()
		ensure_pos_operator_permissions()

		captain = ensure_test_pos_captain()
		self.assertTrue(frappe.has_permission(self.doctype, "read", user=captain))
		self.assertTrue(frappe.has_permission(self.doctype, "select", user=captain))

		row = snapshot_custom_docperm(self.doctype, "NDS Captain")
		self.assertTrue(int((row or {}).get("read") or 0))
		self.assertTrue(int((row or {}).get("select") or 0))
		self.assertEqual(int((row or {}).get("export") or 0), 0)

	def test_manager_has_account_read_and_pos_invoice_permissions(self):
		ensure_test_pos_manager()
		ensure_pos_operator_permissions()

		manager = ensure_test_pos_manager()
		self.assertTrue(frappe.has_permission("Account", "read", user=manager))
		self.assertTrue(frappe.has_permission("Account", "select", user=manager))

		account_row = snapshot_custom_docperm("Account", "NDS Manager")
		self.assertTrue(int((account_row or {}).get("read") or 0))
		self.assertTrue(int((account_row or {}).get("select") or 0))
		self.assertEqual(int((account_row or {}).get("export") or 0), 0)

		inv_row = snapshot_custom_docperm("POS Invoice", "NDS Manager")
		self.assertTrue(int((inv_row or {}).get("read") or 0))
		self.assertTrue(int((inv_row or {}).get("write") or 0))
		self.assertTrue(int((inv_row or {}).get("create") or 0))
		self.assertTrue(int((inv_row or {}).get("submit") or 0))
		self.assertTrue(int((inv_row or {}).get("cancel") or 0))
		self.assertTrue(int((inv_row or {}).get("print") or 0))
		self.assertEqual(int((inv_row or {}).get("export") or 0), 0)

	def test_cashier_has_pos_invoice_submit_permission(self):
		ensure_pos_operator_permissions()
		row = snapshot_custom_docperm("POS Invoice", "NDS Cashier")
		self.assertTrue(int((row or {}).get("read") or 0))
		self.assertTrue(int((row or {}).get("write") or 0))
		self.assertTrue(int((row or {}).get("create") or 0))
		self.assertTrue(int((row or {}).get("submit") or 0))

	def test_pos_invoice_export_zero_on_newly_created_operator_row(self):
		filters = {
			"parent": "POS Invoice",
			"role": "NDS Captain",
			"permlevel": 0,
			"if_owner": 0,
		}
		existing = frappe.db.get_value("Custom DocPerm", filters, "name")
		if existing:
			frappe.delete_doc("Custom DocPerm", existing, force=True, ignore_permissions=True)

		ensure_pos_invoice_operator_permissions()
		row = snapshot_custom_docperm("POS Invoice", "NDS Captain")
		self.assertIsNotNone(row)
		self.assertEqual(int(row.get("export") or 0), 0)
		self.assertTrue(int(row.get("read") or 0))
