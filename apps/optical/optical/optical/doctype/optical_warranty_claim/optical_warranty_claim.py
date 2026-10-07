import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class OpticalWarrantyClaim(Document):
    def validate(self):
        w = frappe.db.get_value("Optical Warranty", self.warranty, ["start_date", "end_date"], as_dict=True)
        if self.is_new() and not (getdate(w.start_date) <= getdate(self.claim_date) <= getdate(w.end_date)):
            frappe.throw(_("The claim date is outside the warranty period"))
        if self.status == "Approved" and not self.approved_by:
            self.approved_by = frappe.session.user

    def on_update(self):
        if self.status in ("Approved", "Completed"):
            frappe.db.set_value("Optical Warranty", self.warranty, "status", "Claimed")

    @frappe.whitelist()
    def make_remake(self):
        if self.claim_type != "Remake":
            frappe.throw(_("Claim type must be Remake"))
        if self.status not in ("Approved", "Completed"):
            frappe.throw(_("Approve the claim first"))
        if self.remake:
            frappe.throw(_("Remake {0} already exists").format(self.remake))
        remake = frappe.get_doc({
            "doctype": "Optical Remake", "original_order": self.optical_order, "reason": "Defective Material",
            "responsibility": "Manufacturer", "warranty_covered": 1, "warranty_claim": self.name, "notes": self.issue,
        })
        remake.insert()
        self.db_set("remake", remake.name)
        return remake.name
