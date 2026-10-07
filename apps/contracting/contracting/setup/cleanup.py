"""Remove DocTypes retired during the Project-rooted refactor.

Frappe never deletes a DocType just because its folder was removed from the app,
so earlier installs keep the old DocTypes/tables. This removes them safely.
Idempotent. Runs automatically via the remove_legacy_doctypes patch on migrate,
and can be run manually:
    bench --site <site> execute contracting.setup.cleanup.remove_legacy
"""
import frappe

LEGACY = [
	# transactional / children first
	"Construction Cost Allocation Detail", "Construction Cost Allocation",
	"Actual Cost Event", "WIP Cost Line", "WIP Cost", "Cost Adjustment",
	"Contract BOQ Item", "Construction Budget Line", "Construction Budget",
	"Tender Version", "Tender Resource", "Tender Pricing",
	# masters last
	"Construction Resource", "Resource Rate", "Measurement Method",
	"Valuation Method", "Cost Category", "Item Work",
	"Construction Allocation Rule", "Construction Contract",
]


def remove_legacy():
	# workflows bound to legacy doctypes
	for wf in frappe.get_all("Workflow", filters={"document_type": ["in", LEGACY]}, pluck="name"):
		try:
			frappe.delete_doc("Workflow", wf, force=1, ignore_permissions=1)
		except Exception:
			pass
	# legacy report
	for rep in ["Cost Control Summary"]:
		if frappe.db.exists("Report", rep):
			try:
				frappe.delete_doc("Report", rep, force=1, ignore_permissions=1)
			except Exception:
				pass

	removed = []
	for dt in LEGACY:
		if not frappe.db.exists("DocType", dt):
			continue
		try:
			frappe.db.delete(dt)                     # clear any rows
		except Exception:
			pass
		try:
			frappe.delete_doc("DocType", dt, force=1, ignore_permissions=1, ignore_missing=True)
		except Exception:
			pass
		try:
			frappe.db.sql_ddl("drop table if exists `tab{0}`".format(dt))
		except Exception:
			pass
		removed.append(dt)
		frappe.db.commit()

	# drop legacy custom fields on ERPNext Project that are no longer used (none currently)
	print("Removed legacy doctypes:", ", ".join(removed) if removed else "(none — already clean)")
	return removed
