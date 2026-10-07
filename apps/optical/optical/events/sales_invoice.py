import frappe


def _orders_for(invoice_name):
    return frappe.get_all(
        "Optical Order",
        or_filters=[["sales_invoice", "=", invoice_name], ["insurer_invoice", "=", invoice_name]],
        pluck="name",
    )


def on_submit(doc, method=None):
    for name in _orders_for(doc.name):
        frappe.get_doc("Optical Order", name).sync_payments()


def on_cancel(doc, method=None):
    for name in _orders_for(doc.name):
        order = frappe.get_doc("Optical Order", name)
        if order.sales_invoice == doc.name:
            order.db_set("sales_invoice", None)
        if order.insurer_invoice == doc.name:
            order.db_set("insurer_invoice", None)
            claim = order.get("insurance_claim")
            if claim:
                frappe.db.set_value("Insurance Claim", claim, {"insurer_invoice": None, "status": "Approved"})
        order.sync_payments()
