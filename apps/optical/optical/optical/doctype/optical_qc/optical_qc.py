import frappe
from frappe import _
from frappe.model.document import Document


class OpticalQC(Document):
    def validate(self):
        if self.is_new() and not self.checks:
            for item in (
                _("Frame verification"), _("Lens verification"), _("Prescription verification"),
                _("Measurements"), _("Visual inspection"),
            ):
                self.append("checks", {"check_item": item})
        if self.result == "Pass" and not all(c.passed for c in self.checks):
            frappe.throw(_("All checklist items must be passed to pass quality control"))

    def on_update(self):
        if self.result == "Pass" and self.has_value_changed("result"):
            job = frappe.get_doc("Optical Job", self.optical_job)
            if job.status == "Quality Control":
                job.advance_stage("Ready")

    @frappe.whitelist()
    def make_remake(self):
        if self.result != "Fail":
            frappe.throw(_("A remake can only be requested for a failed QC"))
        if self.remake:
            frappe.throw(_("Remake {0} already exists").format(self.remake))
        remake = frappe.get_doc({
            "doctype": "Optical Remake", "original_order": self.optical_order, "reason": "Lab Error",
            "responsibility": "Laboratory", "optical_qc": self.name,
            "laboratory": frappe.db.get_value("Optical Job", self.optical_job, "laboratory"),
            "notes": self.defects,
        })
        remake.insert()
        self.db_set("remake", remake.name)
        return remake.name
