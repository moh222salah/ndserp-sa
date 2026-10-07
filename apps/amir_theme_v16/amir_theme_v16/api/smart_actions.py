"""Server side of the "Smart Submit Actions" buttons (draft → submit,
submitted → revert-to-draft / cancel & delete).

Every check here re-verifies what the client already gated on — is_submittable,
no active Workflow, and the cancel/delete/create role permissions — because a
whitelisted endpoint must never trust the caller. `revert_to_draft` is the one
genuinely destructive operation, so it runs as a single request: Frappe wraps
each request in one DB transaction, so if any step raises, everything before
it (the cancel, the delete) is rolled back too and the submitted document is
left exactly as it was — never a half-reverted state.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import copy_doc

from amir_theme_v16.api.smart_action_permissions import get_smart_action_gates


def _has_active_workflow(doctype: str) -> bool:
	return bool(frappe.db.exists("Workflow", {"document_type": doctype, "is_active": 1}))


@frappe.whitelist()
def revert_to_draft(doctype: str, docname: str) -> dict:
	"""Cancel a submitted document, delete it, then re-insert it as a fresh
	draft under the exact same name/serial.

	Runs the official `doc.cancel()` (not a shortcut) so every on_cancel side
	effect — GL/stock ledger reversal, linked-document updates — happens
	exactly as it would for a normal manual cancel. Runs the official
	`frappe.delete_doc()` so link-existence checks still apply: if some other
	document now depends on this one, deletion fails loudly here instead of
	leaving the system in a half-reverted state.
	"""
	doc = frappe.get_doc(doctype, docname)

	if doc.docstatus.is_draft():
		frappe.throw(_("{0} is already a draft.").format(docname))
	if doc.docstatus.is_cancelled():
		frappe.throw(_("A cancelled document cannot be reverted to draft."))

	if not (
		doc.has_permission("cancel")
		and doc.has_permission("delete")
		and frappe.has_permission(doctype, "create")
		and get_smart_action_gates(doctype)["revert_to_draft"]
	):
		frappe.throw(
			_("You don't have permission to revert this document to draft."),
			frappe.PermissionError,
		)

	if _has_active_workflow(doctype):
		frappe.throw(
			_("{0} uses a workflow — revert to draft is disabled to avoid conflicting with it.").format(
				_(doctype)
			)
		)

	original_name = doc.name

	# Snapshot the current field values (system fields cleared, no_copy fields
	# kept) BEFORE cancel/delete, so nothing is lost in the round trip.
	snapshot = copy_doc(doc)

	# 1) Cancel through the official flow.
	doc.cancel()

	# 2) Delete through the official flow (still checks for live links).
	frappe.delete_doc(doctype, original_name, ignore_permissions=False)

	# 3) Recreate as a fresh draft, reusing the exact same name/serial.
	snapshot.insert(set_name=original_name)

	return {"name": snapshot.name}


@frappe.whitelist()
def can_show_smart_actions(doctype: str) -> dict:
	"""Single round trip for the client: whether this doctype has an active
	Workflow (buttons must stay hidden) and the doctype-level permissions
	that gate each button. Doctype-level `can_*` flags already live in
	frappe.boot for the *currently loaded* doctypes, but a document can be
	opened before its doctype's permission set is warm in that cache, and the
	workflow check has no boot-time equivalent at all — so this is one small
	authoritative call instead of trusting client state that might be stale.
	"""
	result = {
		"has_workflow": _has_active_workflow(doctype),
		"can_submit": bool(frappe.has_permission(doctype, "submit")),
		"can_cancel": bool(frappe.has_permission(doctype, "cancel")),
		"can_delete": bool(frappe.has_permission(doctype, "delete")),
		"can_create": bool(frappe.has_permission(doctype, "create")),
	}
	# Optional fine-grained Permission Manager checkboxes — see
	# smart_action_permissions.py. True (no extra gate) for any doctype
	# where they haven't been provisioned.
	result.update(get_smart_action_gates(doctype))
	return result
