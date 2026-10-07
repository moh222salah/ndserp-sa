import frappe
from frappe import _
from frappe.model.document import Document


class SubcontractBOQItem(Document):
    def validate(self):
        self.amount = (self.qty or 0) * (self.rate or 0)
        if self.client_boq_item and self.project:
            cp = frappe.db.get_value("Budget BOQ Item", self.client_boq_item, "project")
            if cp and cp != self.project:
                frappe.throw(_("Client BOQ Item is not in the same Project as the Subcontract."))
