import frappe


def ensure_profile(customer):
    """Every optical customer has exactly one Optical Profile (name == customer)."""
    if not customer:
        return None
    if frappe.db.exists("Optical Profile", customer):
        return customer
    doc = frappe.get_doc({"doctype": "Optical Profile", "customer": customer})
    doc.insert(ignore_permissions=True)
    return doc.name
