from __future__ import annotations

import frappe

# api.save_custom_translation() (see amir_theme_v16/incontext/api.py) restricts
# writes to ("System Manager", "Translation Editor"). Provisioning the role
# idempotently here means non-admin translators can be granted write access
# out-of-the-box; safe to run on every install/migrate.
TRANSLATION_EDITOR_ROLE = "Translation Editor"


def after_install():
	after_migrate()


def after_migrate():
	from amir_theme_v16.api.smart_action_permissions import setup_smart_action_permission_types

	setup_smart_action_permission_types()
	_ensure_translation_editor_role()


def _ensure_translation_editor_role():
	if not frappe.db.exists("Role", TRANSLATION_EDITOR_ROLE):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": TRANSLATION_EDITOR_ROLE,
				"desk_access": 1,
				"description": "Can add/update in-context translations without full System Manager access.",
			}
		).insert(ignore_permissions=True)
