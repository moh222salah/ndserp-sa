import frappe
from frappe.utils import today


def expire_warranties():
    frappe.db.sql(
        "UPDATE `tabOptical Warranty` SET status = 'Expired' WHERE status = 'Active' AND end_date < %s",
        today(),
    )
