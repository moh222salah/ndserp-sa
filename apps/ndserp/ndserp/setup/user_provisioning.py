"""Restrict module Managers to provisioning users in their own module.

System Managers / Administrator are unrestricted. Users with the helper role
`NDS Module Manager` may create or update other Users only when:

1. They hold exactly one module gate role from ``MANAGER_GATE_TO_USER_PROFILE``
2. The target User's Role Profile is that module's ``* User NDS`` **or**
   ``* Manager NDS`` pack (so a Sales Manager can create Sales Users and other
   Sales Managers)
3. No desk-admin roles (System Manager, etc.) are on the target

Managers may edit their own User record for non-role fields (language, etc.)
but cannot change their own roles or Role Profile through this path.

List / form access is scoped: a module manager only sees themselves and users
that carry their module's User or Manager Role Profile (never Administrator
or other modules' staff).

Create on unsaved ``new-*`` User docs is allowed; validation still runs on save.
"""

from __future__ import annotations

import frappe
from frappe import _

# Gate role on the manager → User Role Profile they may assign.
MANAGER_GATE_TO_USER_PROFILE: dict[str, str] = {
	"المبيعات NDS ERP": "Sales User NDS",
	"حسابات NDS ERP": "Accounts User NDS",
	"مخازن NDS ERP": "Stock User NDS",
	"المشتريات NDS ERP": "Purchase User NDS",
	"الاصول NDS ERP": "Assets User NDS",
	"HR NDS": "HR User NDS",
	"نقاط البيع NDS ERP": "POS User NDS",
}

# Same gate → Manager Role Profile (create peers like themselves).
MANAGER_GATE_TO_MANAGER_PROFILE: dict[str, str] = {
	"المبيعات NDS ERP": "Sales Manager NDS",
	"حسابات NDS ERP": "Accounts Manager NDS",
	"مخازن NDS ERP": "Stock Manager NDS",
	"المشتريات NDS ERP": "Purchase Manager NDS",
	"الاصول NDS ERP": "Assets Manager NDS",
	"HR NDS": "HR Manager NDS",
	"نقاط البيع NDS ERP": "POS Manager NDS",
}

MODULE_MANAGER_ROLE = "NDS Module Manager"

# Never assignable by module managers (desk / system admin).
FORBIDDEN_ROLES = frozenset(
	{
		"Administrator",
		"System Manager",
		"Workspace Manager",
	}
)

# Always present / harmless on User; ignore when comparing to Role Profile roles.
_IGNORE_ROLES = frozenset({"All", "Guest", "Desk User"})

_UNRESTRICTED_ROLES = frozenset({"Administrator", "System Manager"})


def validate_user(doc, method=None):
	"""User.validate hook — enforce module-manager provisioning rules."""
	actor = frappe.session.user
	if not actor or actor == "Guest":
		return

	actor_roles = set(frappe.get_roles(actor))
	if actor == "Administrator" or actor_roles & _UNRESTRICTED_ROLES:
		return

	if MODULE_MANAGER_ROLE not in actor_roles:
		return

	allowed_profiles = get_allowed_role_profiles(actor)

	if doc.name == actor:
		_reject_self_role_changes(doc)
		return

	assigned = _assigned_role_profiles(doc)
	if len(assigned) != 1 or assigned.isdisjoint(allowed_profiles):
		frappe.throw(
			_("As a module manager you may only assign Role Profile: {0}.").format(
				frappe.bold(", ".join(sorted(allowed_profiles)))
			),
			frappe.PermissionError,
		)

	allowed_profile = next(iter(assigned))
	_reject_forbidden_and_extra_roles(doc, allowed_profile)


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Limit User list for module managers to self + their module packs."""
	user = user or frappe.session.user
	if not _is_scoped_module_manager(user):
		return ""

	try:
		allowed_profiles = get_allowed_role_profiles(user)
	except frappe.PermissionError:
		return _sql_only_self(user)

	return _sql_self_or_profiles(user, allowed_profiles)


def get_role_profile_permission_query_conditions(user: str | None = None) -> str:
	"""Limit Role Profile link picker to this module's User + Manager packs."""
	user = user or frappe.session.user
	if not _is_scoped_module_manager(user):
		return ""

	try:
		allowed_profiles = get_allowed_role_profiles(user)
	except frappe.PermissionError:
		return "1=0"

	names = ", ".join(frappe.db.escape(p) for p in sorted(allowed_profiles))
	return f"(`tabRole Profile`.name IN ({names}))"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	"""Block module managers from opening Users outside their scoped set.

	Create / in-progress new docs are allowed; ``validate_user`` still enforces
	allowed Role Profiles on save.
	"""
	user = user or frappe.session.user
	if not _is_scoped_module_manager(user):
		return None

	if ptype == "create":
		return True

	docname = doc if isinstance(doc, str) else getattr(doc, "name", None)
	if not docname:
		return True

	if not isinstance(doc, str):
		is_new = getattr(doc, "is_new", None)
		if callable(is_new) and is_new():
			return True
	if isinstance(docname, str) and docname.startswith("new-"):
		return True

	if docname == user:
		return True

	if docname == "Administrator":
		return False
	if _target_has_unrestricted_role(docname):
		return False

	try:
		allowed_profiles = get_allowed_role_profiles(user)
	except frappe.PermissionError:
		return False

	if any(_user_has_role_profile(docname, p) for p in allowed_profiles):
		return True

	return False


def role_profile_has_permission(doc, ptype: str = "read", user: str | None = None) -> bool | None:
	"""Module managers may only read their module's Role Profiles."""
	user = user or frappe.session.user
	if not _is_scoped_module_manager(user):
		return None

	# Never allow create/write/delete of Role Profile itself.
	if ptype in {"create", "write", "delete", "submit", "cancel", "amend"}:
		return False

	docname = doc if isinstance(doc, str) else getattr(doc, "name", None)
	if not docname:
		return False

	try:
		return docname in get_allowed_role_profiles(user)
	except frappe.PermissionError:
		return False


@frappe.whitelist()
def get_allowed_role_profiles_for_session() -> list[str]:
	"""Whitelisted helper for User form client filters."""
	user = frappe.session.user
	if not _is_scoped_module_manager(user):
		return []
	try:
		return sorted(get_allowed_role_profiles(user))
	except frappe.PermissionError:
		return []


def get_allowed_user_profile(user: str | None = None) -> str:
	"""Return the module's User Role Profile (backward-compatible helper)."""
	user = user or frappe.session.user
	gate = _single_module_gate(user)
	return MANAGER_GATE_TO_USER_PROFILE[gate]


def get_allowed_role_profiles(user: str | None = None) -> set[str]:
	"""User + Manager Role Profiles this module manager may assign / see."""
	user = user or frappe.session.user
	gate = _single_module_gate(user)
	return {
		MANAGER_GATE_TO_USER_PROFILE[gate],
		MANAGER_GATE_TO_MANAGER_PROFILE[gate],
	}


def _single_module_gate(user: str) -> str:
	gates = set(frappe.get_roles(user)) & set(MANAGER_GATE_TO_USER_PROFILE)

	if not gates:
		frappe.throw(
			_("NDS Module Manager must hold exactly one module workspace role."),
			frappe.PermissionError,
		)

	if len(gates) > 1:
		frappe.throw(
			_(
				"NDS Module Manager holds multiple module workspace roles ({0}). "
				"Keep a single module gate role to create users."
			).format(", ".join(sorted(gates))),
			frappe.PermissionError,
		)

	return next(iter(gates))


def _is_scoped_module_manager(user: str) -> bool:
	if not user or user in ("Guest", "Administrator"):
		return False
	roles = set(frappe.get_roles(user))
	if roles & _UNRESTRICTED_ROLES:
		return False
	return MODULE_MANAGER_ROLE in roles


def _sql_only_self(user: str) -> str:
	return f"(`tabUser`.name = {frappe.db.escape(user)})"


def _sql_self_or_profiles(user: str, role_profiles: set[str]) -> str:
	user_sql = frappe.db.escape(user)
	profile_list = ", ".join(frappe.db.escape(p) for p in sorted(role_profiles))
	return f"""(
		`tabUser`.name = {user_sql}
		OR `tabUser`.name IN (
			SELECT parent FROM `tabUser Role Profile`
			WHERE role_profile IN ({profile_list})
		)
		OR IFNULL(`tabUser`.role_profile_name, '') IN ({profile_list})
	)"""


def _user_has_role_profile(username: str, role_profile: str) -> bool:
	if frappe.db.exists(
		"User Role Profile",
		{"parent": username, "role_profile": role_profile},
	):
		return True
	return frappe.db.get_value("User", username, "role_profile_name") == role_profile


def _target_has_unrestricted_role(username: str) -> bool:
	roles = set(frappe.get_roles(username))
	return bool(roles & _UNRESTRICTED_ROLES) or username == "Administrator"


def _assigned_role_profiles(doc) -> set[str]:
	profiles = {r.role_profile for r in (doc.get("role_profiles") or []) if r.role_profile}
	legacy = (doc.get("role_profile_name") or "").strip()
	if legacy:
		profiles.add(legacy)
	return profiles


def _reject_self_role_changes(doc) -> None:
	"""Managers may edit themselves but not escalate or change packs."""
	if doc.is_new():
		return

	before = doc.get_doc_before_save()
	if not before:
		return

	if _assigned_role_profiles(before) != _assigned_role_profiles(doc):
		frappe.throw(
			_("You cannot change your own Role Profile."),
			frappe.PermissionError,
		)

	old_roles = {d.role for d in before.roles}
	new_roles = {d.role for d in doc.roles}
	if old_roles != new_roles:
		frappe.throw(
			_("You cannot change your own roles."),
			frappe.PermissionError,
		)


def _reject_forbidden_and_extra_roles(doc, allowed_profile: str) -> None:
	user_roles = {d.role for d in doc.roles}
	blocked = user_roles & FORBIDDEN_ROLES
	if blocked:
		frappe.throw(
			_("These roles are not allowed: {0}").format(", ".join(sorted(blocked))),
			frappe.PermissionError,
		)

	if not frappe.db.exists("Role Profile", allowed_profile):
		frappe.throw(
			_("Role Profile {0} is missing. Run bench migrate for ndserp.").format(
				allowed_profile
			)
		)

	profile_doc = frappe.get_cached_doc("Role Profile", allowed_profile)
	profile_roles = {r.role for r in profile_doc.roles}

	extra = user_roles - profile_roles - _IGNORE_ROLES
	if extra:
		frappe.throw(
			_("Only roles from Role Profile {0} are allowed. Extra roles: {1}").format(
				frappe.bold(allowed_profile), ", ".join(sorted(extra))
			),
			frappe.PermissionError,
		)
