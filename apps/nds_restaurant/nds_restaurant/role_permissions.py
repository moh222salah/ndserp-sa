# Copyright (c) 2026, NDS and contributors
# License: MIT

"""Idempotent Custom DocPerm setup for POS-facing roles."""

import frappe
from frappe.permissions import add_permission, setup_custom_perms, update_permission_property

POS_OPERATOR_ROLES = ("NDS Captain", "NDS Cashier", "NDS Manager")

# Masters required by POS Invoice.set_missing_values / party resolution
POS_MASTER_DOCTYPES = (
	"Account",
	"Customer",
	"Price List",
	"Mode of Payment",
	"Warehouse",
	"Cost Center",
	"Company",
	"Sales Taxes and Charges Template",
	"Item",
	"POS Profile",
)

POS_OPERATOR_PERM_TYPES = ("read", "select")

# Strip accidental grants on master rows we create via add_permission
MASTER_ROW_DENY_FLAGS = (
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
)

POS_INVOICE_ROLE_PERMISSIONS = {
	"NDS Cashier": ("read", "write", "create", "submit", "print"),
	"NDS Captain": ("read", "write", "create", "print"),
	"NDS Manager": ("read", "write", "create", "submit", "cancel", "print"),
}

POS_INVOICE_ROW_CLAMP_FLAGS = ("export",)

SNAPSHOT_PERM_FIELDS = POS_OPERATOR_PERM_TYPES + (
	"write",
	"create",
	"submit",
	"cancel",
	"print",
	"export",
)


def ensure_pos_operator_permissions():
	"""Grant POS operators permissions for checkout and POS Invoice lifecycle."""
	if not frappe.db.table_exists("Custom DocPerm"):
		return

	for doctype in POS_MASTER_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in POS_OPERATOR_ROLES:
			created_row = False
			for ptype in POS_OPERATOR_PERM_TYPES:
				if _raise_permission_flag(doctype, role, ptype):
					created_row = True
			if created_row:
				_clamp_new_master_operator_row(doctype, role)

	ensure_pos_invoice_operator_permissions()
	ensure_kds_permissions()
	ensure_shift_permissions()
	frappe.clear_cache(doctype="DocType")


KDS_ROLE = "NDS Kitchen"
KDS_DOCTYPE_PERMISSIONS = {"NDS KOT": ("read", "select")}


def ensure_kds_permissions():
	"""P4-T7: the NDS Kitchen role reads KOTs (KDS writes go through whitelisted APIs)."""
	if not frappe.db.exists("Role", KDS_ROLE):
		return
	for doctype, ptypes in KDS_DOCTYPE_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		created_row = False
		for ptype in ptypes:
			if _raise_permission_flag(doctype, KDS_ROLE, ptype):
				created_row = True
		if created_row:
			_clamp_new_master_operator_row(doctype, KDS_ROLE)


# P7-T5: closing a shift from the POS. ERPNext marks the opening Closed as the closing user
# (opening_entry.save()), and cashiers/managers read their closings in Desk. Creating and
# submitting openings/closings stays behind the whitelisted shift API.
SHIFT_ROLES = ("NDS Cashier", "NDS Manager")
SHIFT_DOCTYPE_PERMISSIONS = {
	# submit: ERPNext re-saves the submitted opening as the closing user when it consolidates
	"POS Opening Entry": ("read", "write", "submit"),
	"POS Closing Entry": ("read",),
}


def ensure_shift_permissions():
	for doctype, ptypes in SHIFT_DOCTYPE_PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in SHIFT_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			if _raise_permission_flag(doctype, role, "read"):
				# a new row: keep only what we grant below
				_clamp_new_master_operator_row(doctype, role)
			for ptype in ptypes:
				_raise_permission_flag(doctype, role, ptype)


def ensure_pos_invoice_operator_permissions():
	if not frappe.db.exists("DocType", "POS Invoice"):
		return
	for role, ptypes in POS_INVOICE_ROLE_PERMISSIONS.items():
		created_row = False
		for ptype in ptypes:
			if _raise_permission_flag("POS Invoice", role, ptype):
				created_row = True
		if created_row:
			_clamp_new_pos_invoice_operator_row(role)


def _raise_permission_flag(doctype, role, ptype, permlevel=0):
	"""Set a permission bit to 1 if missing; never lower existing flags. Returns True if row was created."""
	setup_custom_perms(doctype)

	filters = {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0}
	custom_name = frappe.db.get_value("Custom DocPerm", filters, "name")
	created_new = False

	if not custom_name:
		add_permission(doctype, role, permlevel=permlevel, ptype=ptype)
		custom_name = frappe.db.get_value("Custom DocPerm", filters, "name")
		created_new = bool(custom_name)

	if not custom_name:
		return created_new

	current = cint_perm(frappe.db.get_value("Custom DocPerm", custom_name, ptype))
	if not current:
		update_permission_property(doctype, role, permlevel, ptype, 1)

	if created_new and doctype == "POS Invoice":
		_clamp_new_pos_invoice_operator_row(role, permlevel)

	return created_new


def _clamp_new_pos_invoice_operator_row(role, permlevel=0):
	"""Clear export on POS Invoice rows we create; never touch pre-existing rows."""
	custom_name = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": "POS Invoice", "role": role, "permlevel": permlevel, "if_owner": 0},
		"name",
	)
	if not custom_name:
		return
	for flag in POS_INVOICE_ROW_CLAMP_FLAGS:
		if cint_perm(frappe.db.get_value("Custom DocPerm", custom_name, flag)):
			update_permission_property("POS Invoice", role, permlevel, flag, 0)


def _clamp_new_master_operator_row(doctype, role, permlevel=0):
	"""On rows we just created for master read/select, clear other flags add_permission may set."""
	custom_name = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0},
		"name",
	)
	if not custom_name:
		return
	for flag in MASTER_ROW_DENY_FLAGS:
		if cint_perm(frappe.db.get_value("Custom DocPerm", custom_name, flag)):
			update_permission_property(doctype, role, permlevel, flag, 0)


def cint_perm(value):
	return int(value or 0)


def snapshot_custom_docperm(doctype, role, permlevel=0):
	"""Return permission flags for a role on a doctype (Custom DocPerm or DocPerm)."""
	custom_name = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": 0},
		"name",
	)
	if custom_name:
		return frappe.db.get_value(
			"Custom DocPerm",
			custom_name,
			list(SNAPSHOT_PERM_FIELDS),
			as_dict=True,
		)

	docperm_name = frappe.db.get_value(
		"DocPerm",
		{"parent": doctype, "role": role, "permlevel": permlevel},
		"name",
	)
	if docperm_name:
		return frappe.db.get_value(
			"DocPerm",
			docperm_name,
			list(SNAPSHOT_PERM_FIELDS),
			as_dict=True,
		)

	return None
