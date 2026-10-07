"""Verify sharper Phase 1 QR helper + print format."""

from __future__ import annotations

import base64
import struct

import frappe
from frappe.utils.pdf import get_pdf
from frappe.www.printview import get_rendered_template
from ksa_compliance.jinja import _generate_decoded_string
from ndserp.jinja import _get_phase_1_qr_values, get_ndserp_zatca_phase_1_qr


def run(invoice: str = "ACC-SINV-2026-00161"):
	frappe.set_user("Administrator")
	vals = _get_phase_1_qr_values(invoice)
	raw = base64.b64decode(_generate_decoded_string(vals))
	tags = []
	i = 0
	while i < len(raw):
		tag = raw[i]
		i += 1
		ln = raw[i]
		i += 1
		val = raw[i : i + ln]
		i += ln
		tags.append({"tag": tag, "val": val.decode()})

	png = base64.b64decode(get_ndserp_zatca_phase_1_qr(invoice))
	w, h = struct.unpack(">II", png[16:24])
	with open("/tmp/zatca_qr_fixed.png", "wb") as f:
		f.write(png)

	doc = frappe.get_doc("Sales Invoice", invoice)
	pf = frappe.get_doc("Print Format", "ZATCA Tax Invoice")
	html = get_rendered_template(doc=doc, print_format=pf, no_letterhead=1)
	pdf_len = len(get_pdf(html))

	return {
		"values": vals,
		"tags": tags,
		"png_wh": [w, h],
		"png_bytes": len(png),
		"html_has_200": ('width="200"' in html) or ("200px" in html),
		"html_has_qr": "data:image/png;base64," in html,
		"html_no_old_helper_call": "get_zatca_phase_1_qr_for_invoice" not in pf.html,
		"uses_new_helper": "get_ndserp_zatca_phase_1_qr" in pf.html,
		"pdf_bytes": pdf_len,
		"amounts_two_decimals": vals[3].count(".") == 1 and len(vals[3].split(".")[1]) == 2,
	}
