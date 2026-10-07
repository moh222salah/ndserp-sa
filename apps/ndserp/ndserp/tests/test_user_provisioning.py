"""Tests for module-manager User provisioning rules."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ndserp.setup import user_provisioning as up


class TestUserProvisioning(FrappeTestCase):
	def test_gate_map_covers_all_modules(self):
		expected_profiles = {
			"Sales User NDS",
			"Accounts User NDS",
			"Stock User NDS",
			"Purchase User NDS",
			"Assets User NDS",
			"HR User NDS",
			"POS User NDS",
		}
		self.assertEqual(set(up.MANAGER_GATE_TO_USER_PROFILE.values()), expected_profiles)

	def test_forbidden_roles_include_system_manager(self):
		self.assertIn("System Manager", up.FORBIDDEN_ROLES)
		self.assertNotIn(up.MODULE_MANAGER_ROLE, up.FORBIDDEN_ROLES)

	def test_get_allowed_user_profile_single_gate(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = ["NDS Module Manager", "المبيعات NDS ERP", "Sales Manager"]
			self.assertEqual(up.get_allowed_user_profile("mgr@example.com"), "Sales User NDS")

	def test_get_allowed_user_profile_rejects_multiple_gates(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"حسابات NDS ERP",
			]
			with self.assertRaises(frappe.PermissionError):
				up.get_allowed_user_profile("mgr@example.com")

	def test_get_allowed_user_profile_rejects_zero_gates(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = ["NDS Module Manager", "Sales Manager"]
			with self.assertRaises(frappe.PermissionError):
				up.get_allowed_user_profile("mgr@example.com")

	def test_validate_skips_system_manager(self):
		doc = frappe._dict(
			name="someone@example.com",
			role_profiles=[],
			roles=[],
			role_profile_name="Accounts User NDS",
		)
		with (
			patch("ndserp.setup.user_provisioning.frappe.session") as session,
			patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles,
		):
			session.user = "admin@example.com"
			get_roles.return_value = ["System Manager"]
			# Must not raise even with a "wrong" profile for a sales manager.
			up.validate_user(doc)

	def test_validate_requires_mapped_user_profile(self):
		doc = frappe._dict(
			name="newuser@example.com",
			role_profiles=[frappe._dict(role_profile="Accounts User NDS")],
			roles=[frappe._dict(role="Accounts User"), frappe._dict(role="حسابات NDS ERP")],
			role_profile_name="Accounts User NDS",
			get=lambda key, default=None: getattr(doc, key, default),
		)
		with (
			patch("ndserp.setup.user_provisioning.frappe.session") as session,
			patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles,
		):
			session.user = "sales.mgr@example.com"
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			with self.assertRaises(frappe.PermissionError):
				up.validate_user(doc)

	def test_validate_blocks_system_manager_on_target(self):
		doc = frappe._dict(
			name="newuser@example.com",
			role_profiles=[frappe._dict(role_profile="Sales User NDS")],
			roles=[
				frappe._dict(role="Sales User"),
				frappe._dict(role="المبيعات NDS ERP"),
				frappe._dict(role="System Manager"),
			],
			role_profile_name="Sales User NDS",
			get=lambda key, default=None: getattr(doc, key, default),
		)
		with (
			patch("ndserp.setup.user_provisioning.frappe.session") as session,
			patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles,
			patch("ndserp.setup.user_provisioning.frappe.db") as db,
			patch("ndserp.setup.user_provisioning.frappe.get_cached_doc") as get_cached_doc,
		):
			session.user = "sales.mgr@example.com"
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			db.exists.return_value = True
			get_cached_doc.return_value = frappe._dict(
				roles=[
					frappe._dict(role="Sales User"),
					frappe._dict(role="Stock User"),
					frappe._dict(role="المبيعات NDS ERP"),
				]
			)
			with self.assertRaises(frappe.PermissionError):
				up.validate_user(doc)

	def test_permission_query_scopes_manager_to_sales_users(self):
		with (
			patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles,
			patch("ndserp.setup.user_provisioning.frappe.db.escape", side_effect=lambda v: f"'{v}'"),
		):
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			sql = up.get_permission_query_conditions("sales_manager_test@nds.com")
			self.assertIn("sales_manager_test@nds.com", sql)
			self.assertIn("Sales User NDS", sql)
			self.assertIn("Sales Manager NDS", sql)
			self.assertIn("tabUser Role Profile", sql)

	def test_allowed_profiles_include_manager_and_user(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			self.assertEqual(
				up.get_allowed_role_profiles("sales_manager_test@nds.com"),
				{"Sales User NDS", "Sales Manager NDS"},
			)

	def test_has_permission_allows_create_on_new_user(self):
		doc = frappe.new_doc("User")
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			self.assertTrue(up.has_permission(doc, "create", user="sales_manager_test@nds.com"))
			self.assertTrue(up.has_permission(doc, "write", user="sales_manager_test@nds.com"))

	def test_permission_query_empty_for_system_manager(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = ["System Manager"]
			self.assertEqual(up.get_permission_query_conditions("admin@example.com"), "")

	def test_has_permission_denies_administrator(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			self.assertFalse(
				up.has_permission("Administrator", "read", user="sales_manager_test@nds.com")
			)

	def test_has_permission_allows_self(self):
		with patch("ndserp.setup.user_provisioning.frappe.get_roles") as get_roles:
			get_roles.return_value = [
				"NDS Module Manager",
				"المبيعات NDS ERP",
				"Sales Manager",
			]
			self.assertTrue(
				up.has_permission(
					"sales_manager_test@nds.com",
					"read",
					user="sales_manager_test@nds.com",
				)
			)
