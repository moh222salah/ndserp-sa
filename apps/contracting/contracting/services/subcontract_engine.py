"""Subcontract current-value engine.

Mirrors the client-side variation engine but at the subcontract header level:
current_value = original_value + sum of *approved* Subcontract Variation values.
Recompute-from-source keeps it idempotent — approving, rejecting, cancelling or
deleting a variation and recomputing always yields the correct position.
"""
import frappe


def recompute_subcontract(subcontract):
	if not subcontract or not frappe.db.exists("Subcontract", subcontract):
		return

	original = frappe.db.get_value("Subcontract", subcontract, "original_value") or 0

	approved_delta = frappe.db.sql(
		"""
		select coalesce(sum(variation_value), 0)
		from `tabSubcontract Variation`
		where subcontract = %s and status = 'Approved'
		""", subcontract)[0][0] or 0

	frappe.db.set_value("Subcontract", subcontract, "current_value",
		original + approved_delta, update_modified=False)
