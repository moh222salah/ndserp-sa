"""Current contract-value engine (Project-rooted).

Project.current_contract_value = Project.original_contract_value
  + sum of approved Contract Variation values for the project.
Recompute-from-source => idempotent.
"""
import frappe


def recompute_project(project):
	if not project or not frappe.db.exists("Project", project):
		return
	original = frappe.db.get_value("Project", project, "original_contract_value") or 0
	approved = frappe.db.sql("""select coalesce(sum(variation_value),0)
		from `tabContract Variation` where project=%s and status='Approved'""", project)[0][0] or 0
	frappe.db.set_value("Project", project, "current_contract_value",
		original + approved, update_modified=False)
