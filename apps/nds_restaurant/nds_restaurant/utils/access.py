# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P4: POS/KDS capability resolution and access guards.

Every helper tolerates sites where the NDS custom fields are not migrated (has_field guards), so the
shared bench can serve unmigrated sites without errors.
"""

import frappe
from frappe import _

MANAGER_ROLES = ("NDS Manager", "System Manager")
DEFAULT_BILLING_ROLES = ("NDS Cashier", "NDS Manager", "System Manager")
VERIFY_CANCEL_ROLES = ("NDS Manager", "System Manager")
NDS_POS_ROLES = ("NDS Manager", "NDS Cashier", "NDS Captain")
NDS_KITCHEN_ROLE = "NDS Kitchen"
KDS_ROLES = NDS_POS_ROLES + (NDS_KITCHEN_ROLE,)
BRANCH_EXEMPT_ROLES = ("System Manager", "NDS Manager")


def _user(user=None):
	return user or frappe.session.user


def user_roles(user=None):
	return set(frappe.get_roles(_user(user)))


def is_manager(user=None):
	user = _user(user)
	if user == "Administrator":
		return True
	return bool(user_roles(user) & set(MANAGER_ROLES))


def _profile_doc(profile):
	if not profile:
		return None
	if isinstance(profile, str):
		if not frappe.db.exists("POS Profile", profile):
			return None
		return frappe.get_cached_doc("POS Profile", profile)
	return profile


def profile_roles(profile, fieldname):
	"""Roles listed in an NDS Role Permitted table on the POS Profile (empty if not migrated)."""
	doc = _profile_doc(profile)
	if not doc or not doc.meta.has_field(fieldname):
		return set()
	return {row.role for row in (doc.get(fieldname) or []) if row.get("role")}


def get_capabilities(user=None, profile=None):
	"""P4-T1: what the user may do on this POS Profile."""
	user = _user(user)
	doc = _profile_doc(profile)
	roles = user_roles(user)
	manager = is_manager(user)

	billing_roles = profile_roles(doc, "custom_role_allowed_for_billing") or set(DEFAULT_BILLING_ROLES)
	can_bill = manager or bool(roles & billing_roles)

	transfer_roles = profile_roles(doc, "custom_transfer_role_permissions")
	can_transfer = manager or bool(roles & transfer_roles)

	restricted_roles = profile_roles(doc, "custom_role_restricted_for_table_order")
	table_restricted = (not manager) and (not can_transfer) and bool(roles & restricted_roles)

	remove_items = bool(doc and doc.meta.has_field("custom_remove_items") and doc.get("custom_remove_items"))
	can_remove_items = manager or remove_items

	can_verify_cancel = user == "Administrator" or bool(roles & set(VERIFY_CANCEL_ROLES))

	return {
		"is_manager": 1 if manager else 0,
		"can_bill": 1 if can_bill else 0,
		"can_transfer": 1 if can_transfer else 0,
		"table_restricted": 1 if table_restricted else 0,
		"can_remove_items": 1 if can_remove_items else 0,
		"can_verify_cancel": 1 if can_verify_cancel else 0,
	}


def assert_can_bill(profile, user=None):
	"""P4-T2: payment and order-type changes need a billing role."""
	if not get_capabilities(user, profile)["can_bill"]:
		frappe.throw(_("Not permitted to bill"), frappe.PermissionError)


def assert_can_transfer(profile, user=None):
	"""P4-T4: captain transfer, table move and merge need a transfer role (managers always may)."""
	if not get_capabilities(user, profile)["can_transfer"]:
		frappe.throw(_("Not permitted to transfer orders"), frappe.PermissionError)


def invoice_captain(doc):
	"""The captain who owns an order: custom_captain when set, else the creator."""
	if doc is None:
		return None
	getter = doc.get if hasattr(doc, "get") else (lambda k, d=None: getattr(doc, k, d))
	return getter("custom_captain") or getter("owner")


def branch_users(branch):
	if not branch:
		return []
	return frappe.get_all(
		"NDS Branch User",
		filters={"parent": branch, "parenttype": "Branch"},
		pluck="user",
	)


def user_branches(user=None):
	user = _user(user)
	return set(
		frappe.get_all(
			"NDS Branch User",
			filters={"parenttype": "Branch", "user": user},
			pluck="parent",
		)
	)


def _branch_exempt(user):
	return user == "Administrator" or bool(user_roles(user) & set(BRANCH_EXEMPT_ROLES))


def assert_branch_access(user, branch):
	"""P4-T6: only users listed on the Branch may open the POS (managers are exempt).

	An empty Branch User table denies everyone except Administrator, System Manager and NDS Manager.
	"""
	user = _user(user)
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if not branch or _branch_exempt(user):
		return
	if user not in branch_users(branch):
		frappe.throw(
			_("User not allowed to access POS: you are not assigned to branch {0}").format(branch),
			frappe.PermissionError,
		)


def has_kds_role(user=None):
	user = _user(user)
	if user == "Administrator":
		return True
	roles = user_roles(user)
	return bool(roles & (set(KDS_ROLES) | {"System Manager"}))


def assert_kds_access(unit, user=None):
	"""P4-T7: KDS needs an NDS role and a seat in the Branch User table of the unit's branch."""
	user = _user(user)
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if not has_kds_role(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	unit_name = unit.name if hasattr(unit, "name") else unit
	if not unit_name or not frappe.db.exists("NDS Production Unit", unit_name):
		frappe.throw(_("Production Unit {0} not found").format(unit_name or ""))
	if _branch_exempt(user):
		return
	branch = frappe.db.get_value("NDS Production Unit", unit_name, "branch")
	if branch and user not in branch_users(branch):
		frappe.throw(
			_("Not permitted: you are not assigned to branch {0}").format(branch),
			frappe.PermissionError,
		)


def can_view_all_units(user=None):
	return _branch_exempt(_user(user))
