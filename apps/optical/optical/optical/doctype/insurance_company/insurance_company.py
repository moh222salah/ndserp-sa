import frappe
from frappe import _
from frappe.model.document import Document


class InsuranceCompany(Document):
    def after_insert(self):
        if self.customer:
            return
        defaults = frappe.get_single("Selling Settings")
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": self.company_name,
            "customer_type": "Company",
            "customer_group": defaults.customer_group or "All Customer Groups",
            "territory": defaults.territory or "All Territories",
        })
        customer.insert(ignore_permissions=True)
        self.db_set("customer", customer.name)
