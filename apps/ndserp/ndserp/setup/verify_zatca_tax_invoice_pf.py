"""Verify ZATCA Tax Invoice print format renders with Phase 1 QR."""

from __future__ import annotations

import frappe
from frappe.utils.pdf import get_pdf
from frappe.www.printview import get_rendered_template


def run(invoice: str | None = None):
	invoice = invoice or frappe.db.get_value(
		"Sales Invoice", {"company": "NDS (Demo)", "docstatus": 1}, "name", order_by="modified desc"
	)
	if not invoice:
		return {"ok": False, "error": "No submitted Sales Invoice found for NDS (Demo)"}

	doc = frappe.get_doc("Sales Invoice", invoice)
	print_format = frappe.get_doc("Print Format", "ZATCA Tax Invoice")
	frappe.set_user("Administrator")
	html = get_rendered_template(doc=doc, print_format=print_format, no_letterhead=1)

	checks = {
		"has_title": ("فاتورة ضريبية" in html) or ("فاتورة ضريبية مبسطة" in html),
		"has_buyer": "Buyer / العميل" in html,
		"has_seller": "Seller / المورد" in html,
		"has_items_header": "Natures of goods or services" in html,
		"has_totals": "Total Amount Due" in html,
		"has_qr_img": "data:image/png;base64" in html,
		"no_phase1_error": "Does not have active ZATCA Phase 1 Business Settings" not in html,
		"has_invoice_name": doc.name in html,
	}

	pdf_bytes = get_pdf(html)
	out_path = frappe.get_site_path("private", "files", f"{invoice}_zatca_tax_invoice.pdf")
	with open(out_path, "wb") as f:
		f.write(pdf_bytes)

	# Also verify QR helper directly
	from ksa_compliance.jinja import get_zatca_phase_1_qr_for_invoice

	qr = get_zatca_phase_1_qr_for_invoice(invoice)

	return {
		"ok": all(checks.values()) and bool(qr) and len(pdf_bytes) > 1000,
		"invoice": invoice,
		"checks": checks,
		"qr_len": len(qr) if qr else 0,
		"pdf_bytes": len(pdf_bytes),
		"pdf_path": out_path,
	}
