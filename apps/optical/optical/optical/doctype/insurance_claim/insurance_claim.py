import frappe
from frappe import _
from frappe.model.document import Document


class InsuranceClaim(Document):
    def validate(self):
        if self.status == "Approved" and not self.approval_no:
            frappe.throw(_("Approval Number is required to approve a claim"))
        if self.status == "Settled" and not (self.settled_amount and self.settlement_date):
            frappe.throw(_("Settled Amount and Settlement Date are required for a settled claim"))

    def on_update(self):
        if self.status == "Approved":
            frappe.db.set_value("Optical Order", self.optical_order,
                                {"insurance_approved": 1, "insurance_approval_no": self.approval_no})

    @frappe.whitelist()
    def make_insurer_invoice(self):
        self.check_permission("write")
        order = frappe.get_doc("Optical Order", self.optical_order)
        return order.make_insurer_invoice()
