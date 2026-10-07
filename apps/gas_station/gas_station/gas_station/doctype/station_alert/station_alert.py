import frappe
from frappe.model.document import Document


class StationAlert(Document):
    @frappe.whitelist()
    def acknowledge(self):
        self.status = "Acknowledged"
        self.acknowledged_by = frappe.session.user
        self.acknowledged_at = frappe.utils.now_datetime()
        self.save()

    @frappe.whitelist()
    def clear_alert(self):
        self.status = "Cleared"
        self.cleared_at = frappe.utils.now_datetime()
        self.save()
