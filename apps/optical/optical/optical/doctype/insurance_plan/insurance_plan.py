import frappe
from frappe import _
from frappe.model.document import Document


class InsurancePlan(Document):
    def validate(self):
        if not 0 <= (self.coverage_percent or 0) <= 100:
            frappe.throw(_("Coverage Percentage must be between 0 and 100"))
