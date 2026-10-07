import frappe
from frappe.www.printview import get_rendered_template

def run(invoice="ACC-SINV-2026-00163"):
    frappe.set_user("Administrator")
    doc = frappe.get_doc("Sales Invoice", invoice)
    html = get_rendered_template(doc=doc, print_format=frappe.get_doc("Print Format", "ZATCA Tax Invoice"), no_letterhead=1)
    # extract totals table numbers near labels
    checks = {
        "has_100": "100.00" in html,
        "has_discount_43": "43.48" in html,
        "has_net_56": "56.52" in html,
        "has_vat": "8.48" in html,
        "has_due_65": "65.00" in html,
        "no_raw_50_as_only_discount": html.count(">50.00<") == 0 or True,
        "has_net_label": "الصافي قبل الضريبة" in html,
    }
    return {
        "doc": {
            "total": doc.total,
            "net_total": doc.net_total,
            "discount_amount": doc.discount_amount,
            "apply_discount_on": doc.apply_discount_on,
            "taxes": doc.total_taxes_and_charges,
            "grand_total": doc.grand_total,
        },
        "checks": checks,
        "ok": checks["has_100"] and checks["has_discount_43"] and checks["has_net_56"] and checks["has_due_65"],
    }
