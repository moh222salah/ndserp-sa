import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class OpticalWarranty(Document):
    def validate(self):
        if getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(_("End Date cannot be before Start Date"))
