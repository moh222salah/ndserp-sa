import frappe


def sync_orders(doc, method=None):
    invoices = [r.reference_name for r in doc.references if r.reference_doctype == "Sales Invoice"]
    if not invoices:
        return
    orders = frappe.get_all(
        "Optical Order",
        or_filters=[["sales_invoice", "in", invoices], ["insurer_invoice", "in", invoices]],
        pluck="name",
    )
    for name in orders:
        frappe.get_doc("Optical Order", name).sync_payments()
