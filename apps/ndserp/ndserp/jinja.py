"""Jinja helpers for ndserp print formats."""

from __future__ import annotations

import base64
from io import BytesIO
from math import floor

import frappe
import pyqrcode
from frappe.utils import flt
from ksa_compliance.jinja import _format_date, _generate_decoded_string
from ksa_compliance.ksa_compliance.doctype.zatca_phase_1_business_settings.zatca_phase_1_business_settings import (
	ZATCAPhase1BusinessSettings,
)
from num2words import num2words

# Arabic currency labels for invoice print (code -> (main, fraction))
_AR_CURRENCY = {
	"SAR": ("ريال سعودي", "هللة"),
	"EGP": ("جنيه مصري", "قرش"),
	"AED": ("درهم إماراتي", "فلس"),
	"KWD": ("دينار كويتي", "فلس"),
	"BHD": ("دينار بحريني", "فلس"),
	"OMR": ("ريال عماني", "بيسة"),
	"QAR": ("ريال قطري", "درهم"),
	"USD": ("دولار أمريكي", "سنت"),
	"EUR": ("يورو", "سنت"),
}


def get_arabic_amount_in_words(amount, currency: str | None = None) -> str:
	"""Return amount in Arabic words only, e.g. ``تسعمائة و تسعون ريال سعودي فقط``."""
	try:
		number = abs(flt(amount))
	except Exception:
		return ""

	currency = currency or frappe.db.get_default("currency") or "SAR"
	main_name, fraction_name = _AR_CURRENCY.get(currency, (currency, ""))

	fraction_units = frappe.db.get_value("Currency", currency, "fraction_units") or 100
	fraction_units = int(fraction_units) or 100

	main = int(floor(number))
	fraction = int(round((number - main) * fraction_units))
	if fraction >= fraction_units:
		main += 1
		fraction = 0

	if main == 0 and fraction == 0:
		return f"صفر {main_name} فقط"

	parts: list[str] = []
	if main:
		parts.append(f"{_to_arabic_words(main)} {main_name}")
	if fraction and fraction_name:
		parts.append(f"{_to_arabic_words(fraction)} {fraction_name}")

	return " و ".join(parts) + " فقط"


def _to_arabic_words(n: int) -> str:
	try:
		return num2words(int(n), lang="ar")
	except Exception:
		return str(n)


def get_ndserp_zatca_phase_1_qr(invoice_name: str) -> str | None:
	"""Phase 1 TLV QR with ZATCA-friendly amount formatting and a sharper PNG.

	ksa_compliance encodes floats as ``990.0`` / ``0.0`` and uses a modest PNG
	scale. PDF engines (wkhtmltopdf) then downsample that image in the print
	format, which often makes the code hard to scan. This helper:

	- formats invoice total and VAT as two-decimal strings (``990.00``)
	- builds a larger PNG (scale 10, error correction H)
	"""
	values = _get_phase_1_qr_values(invoice_name)
	if values is None:
		return None
	payload = _generate_decoded_string(values)
	return _png_base64(payload, scale=10)


def _get_phase_1_qr_values(invoice_name: str) -> list | None:
	doctype = None
	if frappe.db.exists("POS Invoice", invoice_name):
		doctype = "POS Invoice"
	elif frappe.db.exists("Sales Invoice", invoice_name):
		doctype = "Sales Invoice"
	else:
		return None

	invoice = frappe.get_doc(doctype, invoice_name)
	settings_name = frappe.db.get_value(
		"ZATCA Phase 1 Business Settings", {"company": invoice.company}, "name"
	)
	if not settings_name:
		return None

	settings = frappe.get_doc("ZATCA Phase 1 Business Settings", settings_name)
	assert isinstance(settings, ZATCAPhase1BusinessSettings)
	if settings.status == "Disabled":
		return None

	timestamp = _format_date(invoice.posting_date, invoice.posting_time)
	grand_total = f"{abs(float(invoice.grand_total or 0)):.2f}"
	total_vat = f"{abs(float(invoice.total_taxes_and_charges or 0)):.2f}"
	return [
		invoice.company,
		settings.vat_registration_number or "",
		timestamp,
		grand_total,
		total_vat,
	]


def _png_base64(data: str, scale: int = 10) -> str | None:
	if not data:
		return None
	qr = pyqrcode.create(data, error="H")
	with BytesIO() as buffer:
		qr.png(buffer, scale=scale, module_color=(0, 0, 0, 255), background=(255, 255, 255, 255))
		buffer.seek(0)
		return base64.b64encode(buffer.getvalue()).decode("utf-8")
