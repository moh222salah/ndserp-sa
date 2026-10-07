import frappe
from frappe.www.printview import get_rendered_template

def run(invoice="ACC-SINV-2026-00161"):
    frappe.set_user("Administrator")
    doc = frappe.get_doc("Sales Invoice", invoice)
    pf = frappe.get_doc("Print Format", "ZATCA Tax Invoice")
    html = get_rendered_template(doc=doc, print_format=pf, no_letterhead=1)
    has_label = "المبلغ كتابة" in html
    has_value = bool(doc.in_words) and (doc.in_words in html)
    return {
        "has_label": has_label,
        "has_value": has_value,
        "in_words": doc.in_words,
        "snippet": html[html.find("words-box"):html.find("words-box")+400] if "words-box" in html else None,
    }
