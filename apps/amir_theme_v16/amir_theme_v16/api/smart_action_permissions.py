"""Dedicated Permission Manager checkboxes for the three Smart Submit Action
buttons — "Save Final Submit", "Revert To Draft", "Cancel Delete".

Built entirely on Frappe v16's own `Permission Type` doctype
(frappe.core.doctype.permission_type): creating one auto-generates a real
Check custom field on Custom DocPerm/DocPerm/DocShare AND registers the name
in `frappe.permissions.get_doctype_ptype_map()`, which is what both the
Permission Manager page (`custom_rights = doctype_ptype_map[doctype]`) and
`frappe.has_permission()` (via `get_rights()`) read from. No core file is
touched and no core JS is patched — this is the sanctioned extension point,
verified by creating/checking/deleting a throwaway Permission Type by hand
before writing this module.

These checkboxes are an OPTIONAL, ADDITIVE refinement layer, never a
replacement for the underlying submit/cancel/delete/create rights the
buttons already require (see smart_actions.can_show_smart_actions) — a role
can never gain access through this checkbox that its real rights wouldn't
already allow, only lose it. For any doctype where a checkbox was never
provisioned (outside TARGET_DOCTYPES, or on a site where this hasn't run
yet), the buttons fall back to the plain submit/cancel/delete/create check
exactly as before this feature existed.
"""

from __future__ import annotations

import frappe

# perm_type -> the base rights it can only ever narrow, never widen.
SMART_ACTION_PERM_TYPES: dict[str, list[str]] = {
	"save_final_submit": ["submit"],
	"revert_to_draft": ["cancel", "delete", "create"],
	"cancel_delete": ["cancel", "delete"],
}

# Curated, not exhaustive: the same "core transactional/financial document"
# set this app's tafqit sibling app (custom_inwords_en_ar) already targets —
# covers the doctypes these buttons are realistically used on day to day.
# Provisioning one more doctype later is a 3-line Permission Type insert, not
# a schema change, so this list is deliberately conservative rather than
# blanketing every submittable doctype in the framework (which would add
# 3 extra Custom Fields on every Permission Manager screen site-wide,
# most of them irrelevant, for doctypes no one uses these buttons on).
TARGET_DOCTYPES: tuple[str, ...] = (
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Payment Entry",
	"Journal Entry",
	"Expense Claim",
	"Stock Entry",
)


def setup_smart_action_permission_types() -> None:
	"""Idempotent. Safe to call on every migrate.

	For each (doctype, button) pair not yet provisioned: creates the
	Permission Type (→ the checkbox appears in Permission Manager) and, in
	that SAME one-time pass, seeds it ON for every role that already holds
	the underlying base right(s) — so existing behaviour does not regress
	the instant the checkbox exists. After this first pass the checkbox is
	entirely admin-owned: later migrates never touch it again (an admin's
	manual uncheck must stick), because the whole block is skipped once the
	Permission Type already exists.
	"""
	for doctype in TARGET_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		for perm_type, base_ptypes in SMART_ACTION_PERM_TYPES.items():
			_provision_once(doctype, perm_type, base_ptypes)


def _provision_once(doctype: str, perm_type: str, base_ptypes: list[str]) -> None:
	name = f"{frappe.scrub(doctype)}_{perm_type}"
	if frappe.db.exists("Permission Type", name):
		return

	frappe.get_doc(
		{
			"doctype": "Permission Type",
			"doc_type": doctype,
			"perm_type": perm_type,
		}
	).insert(ignore_permissions=True)

	_seed_default_grants(doctype, perm_type, base_ptypes)


def _seed_default_grants(doctype: str, perm_type: str, base_ptypes: list[str]) -> None:
	"""One-time backfill: switch the new checkbox ON for every role that
	already holds every base right, using Frappe's own Permission Manager
	helpers (the exact functions its "toggle a checkbox" click handler
	calls) so this behaves identically to an admin ticking the box by hand.
	"""
	from frappe.permissions import setup_custom_perms, update_permission_property

	# Materialises Custom DocPerm rows for every role from the doctype's
	# standard permissions, if that hasn't already happened for this doctype.
	setup_custom_perms(doctype)

	rows = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": doctype, "permlevel": 0},
		fields=["name", "role", *base_ptypes],
	)
	for row in rows:
		if all(row.get(p) for p in base_ptypes):
			update_permission_property(doctype, row.role, 0, perm_type, 1, validate=False)


def get_smart_action_gates(doctype: str) -> dict[str, bool]:
	"""One entry per button: True unless a Permission Type has been
	provisioned for this (doctype, button) AND the acting user's roles
	don't grant it — i.e. an unprovisioned doctype never gets gated by this
	layer at all.
	"""
	gates: dict[str, bool] = {}
	for perm_type in SMART_ACTION_PERM_TYPES:
		name = f"{frappe.scrub(doctype)}_{perm_type}"
		if frappe.db.exists("Permission Type", name):
			gates[perm_type] = bool(frappe.has_permission(doctype, perm_type))
		else:
			gates[perm_type] = True
	return gates
