# Copyright (c) 2026, NDS and contributors
# License: MIT

from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint

DEFAULT_KOT_FORMAT = "NDS KOT"
DEFAULT_BILL_FORMAT = "NDS Receipt"


def _existing_format(name):
	"""A print format name only if it exists on this site (formats sync on migrate)."""
	return name if name and frappe.db.exists("Print Format", name) else None


def _printview_url(doctype, name, print_format=None):
	url = f"/printview?doctype={quote(doctype)}&name={quote(name)}&no_letterhead=1&trigger_print=1"
	if print_format:
		url += f"&format={quote(print_format)}"
	return url


def _send_to_printer(doctype, name, printer, print_format):
	"""Queue a network (CUPS) print job; returns (printed, error_reason)."""
	try:
		from frappe.utils.print_format import print_by_server

		print_by_server(doctype, name, printer, print_format=print_format, no_letterhead=1)
		return True
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS Network Print")
		return False


# ---------------------------------------------------------------------------
# KOT printing (P6-T3)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def print_kot(kot_name):
	"""Print a KOT on its resolved network printer (the format comes from the printer row)."""
	kot = _get_kot(kot_name)
	_assert_pos_access(kot.pos_profile)
	return _print_kot(kot)


def _print_kot(kot, print_format=None):
	printer, row_format = _resolve_kot_printer(kot)
	fmt = _existing_format(print_format) or _existing_format(row_format) or _existing_format(DEFAULT_KOT_FORMAT)
	result = {"printed": False, "printer": printer, "print_format": fmt}
	if not printer:
		result["reason"] = "no_printer"
		return result
	if _send_to_printer("NDS KOT", kot.name, printer, fmt):
		result["printed"] = True
	else:
		result["reason"] = "print_failed"
	return result


def _resolve_kot_printer(kot):
	"""(printer, print_format): production unit rows, then room rows, then the POS Profile printers."""
	# Production unit printers first
	if kot.get("production_unit") and frappe.db.exists("NDS Production Unit", kot.production_unit):
		unit = frappe.get_doc("NDS Production Unit", kot.production_unit)
		for row in unit.get("printer_settings") or []:
			if row.kot and row.printer:
				if kot.order_type == "Take Away" and row.get("block_takeaway_kot"):
					continue
				return row.printer, row.get("kot_print_format")

	# Room printers
	if kot.get("table"):
		room = frappe.db.get_value("NDS Table", kot.table, "restaurant_room")
		if room and frappe.db.exists("NDS Room", room):
			room_doc = frappe.get_doc("NDS Room", room)
			for row in room_doc.get("printer_settings") or []:
				if row.kot and row.printer:
					return row.printer, row.get("kot_print_format")

	# POS Profile fallback
	if not kot.get("pos_profile") or not frappe.db.exists("POS Profile", kot.pos_profile):
		return None, None
	profile = frappe.get_doc("POS Profile", kot.pos_profile)
	if kot.order_type in ("Take Away", "Delivery"):
		return profile.get("custom_parcel_order_printer"), None
	return profile.get("custom_table_order_printer"), None


# ---------------------------------------------------------------------------
# Bill printing (P6-T2)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def print_bill(invoice):
	"""Route a bill to the room printer, then the POS Profile printer; else tell the POS to use the browser.

	A draft is marked printed either way (P2-T3), exactly like mark_invoice_printed.
	"""
	from nds_restaurant.api.pos import (
		_assert_invoice_not_locked,
		_invoice_table_name,
		mark_invoice_printed,
	)
	from nds_restaurant.utils.access import get_capabilities

	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice or ""))
	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_access(doc.pos_profile)
	table = _invoice_table_name(doc)
	if doc.docstatus == 0 and table:
		_assert_invoice_not_locked(doc, table, get_capabilities(profile=doc.pos_profile))

	profile = frappe.get_doc("POS Profile", doc.pos_profile)
	fmt = _existing_format(profile.get("print_format")) or _existing_format(DEFAULT_BILL_FORMAT)
	printer = _resolve_bill_printer(doc, profile, table)
	result = {"invoice": doc.name, "printed": False, "printer": printer, "print_format": fmt}
	if printer and _send_to_printer("POS Invoice", doc.name, printer, fmt):
		result["printed"] = True
		result["method"] = "network"
	else:
		result["method"] = "browser"
		result["print_url"] = _printview_url("POS Invoice", doc.name, fmt)
		if printer:
			result["reason"] = "print_failed"

	marked = mark_invoice_printed(doc.name)
	result["invoice_printed"] = marked.get("invoice_printed")
	result["modified"] = marked.get("modified")
	return result


def _resolve_bill_printer(doc, profile, table=None):
	room = doc.get("custom_nds_room")
	if not room and table:
		room = frappe.db.get_value("NDS Table", table, "restaurant_room")
	if room and frappe.db.exists("NDS Room", room):
		for row in frappe.get_doc("NDS Room", room).get("printer_settings") or []:
			if row.get("bill") and row.printer:
				return row.printer
	for row in profile.get("custom_printer_settings") or []:
		if row.get("bill") and row.printer:
			return row.printer
	return None


# ---------------------------------------------------------------------------
# KOT reprint (P6-T4)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def reprint_kot(kot_name):
	"""Reprint a KOT: submit a Duplicate KOT (P5-T5) and print it in the reprint format."""
	from nds_restaurant.api.kot import create_duplicate_kot
	from nds_restaurant.utils.access import get_capabilities

	kot = _get_kot(kot_name)
	_assert_pos_access(kot.pos_profile)
	profile = frappe.get_doc("POS Profile", kot.pos_profile)
	if not cint(profile.get("custom_enable_kot_reprint") or 0):
		frappe.throw(_("KOT reprint is disabled for POS Profile {0}").format(kot.pos_profile))
	caps = get_capabilities(profile=kot.pos_profile)
	if not (caps.get("can_bill") or caps.get("is_manager")):
		frappe.throw(_("Not permitted to reprint KOTs"), frappe.PermissionError)
	if kot.docstatus != 1:
		frappe.throw(_("Only submitted KOTs can be reprinted"))

	duplicate = create_duplicate_kot(kot.name)
	dup = frappe.get_doc("NDS KOT", duplicate)
	result = _print_kot(dup, print_format=profile.get("custom_reprint_kot_format"))
	result.update({"kot": dup.name, "original_kot": dup.get("original_kot") or kot.name})
	if not result["printed"]:
		result["print_url"] = _printview_url("NDS KOT", dup.name, result.get("print_format"))
	return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_kot(kot_name):
	if not kot_name or not frappe.db.exists("NDS KOT", kot_name):
		frappe.throw(_("KOT {0} not found").format(kot_name or ""))
	return frappe.get_doc("NDS KOT", kot_name)


def _assert_pos_access(pos_profile):
	from nds_restaurant.api.pos import _assert_pos_profile_access

	_assert_pos_profile_access(pos_profile)


@frappe.whitelist()
def get_bill_html(invoice):
	"""Rendered bill (the profile's print format) for QZ Tray printing (P6-T5)."""
	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice or ""))
	profile_name = frappe.db.get_value("POS Invoice", invoice, "pos_profile")
	_assert_pos_access(profile_name)
	fmt = _existing_format(frappe.db.get_value("POS Profile", profile_name, "print_format")) or _existing_format(
		DEFAULT_BILL_FORMAT
	)
	return frappe.get_print("POS Invoice", invoice, print_format=fmt, no_letterhead=1)


# ---------------------------------------------------------------------------
# QZ Tray signing (P6-T5)
# ---------------------------------------------------------------------------

QZ_SETTINGS = "NDS QZ Settings"
QZ_ROLES = ("NDS Manager", "NDS Cashier", "NDS Captain", "System Manager")


def _qz_settings_installed():
	return bool(frappe.db.exists("DocType", QZ_SETTINGS))


def _assert_qz_user():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if user != "Administrator" and not (set(frappe.get_roles(user)) & set(QZ_ROLES)):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _qz_private_key():
	if not _qz_settings_installed():
		return None
	from frappe.utils.password import get_decrypted_password

	return get_decrypted_password(QZ_SETTINGS, QZ_SETTINGS, "private_key", raise_exception=False)


@frappe.whitelist()
def qz_certificate():
	"""Public certificate for qz.security.setCertificatePromise (None = unsigned mode)."""
	_assert_qz_user()
	if not _qz_settings_installed():
		return None
	return frappe.db.get_single_value(QZ_SETTINGS, "certificate") or None


@frappe.whitelist(methods=["POST"])
def qz_sign(message):
	"""SHA512/RSA signature of a QZ request, base64. None when no key is configured (unsigned mode)."""
	import base64

	_assert_qz_user()
	if not message or not isinstance(message, str) or len(message) > 20000:
		frappe.throw(_("Invalid QZ message"))
	key = _qz_private_key()
	if not key:
		return None
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import padding

	try:
		private_key = serialization.load_pem_private_key(key.encode(), password=None)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS QZ signing key")
		frappe.throw(_("The QZ private key in NDS QZ Settings is not a valid unencrypted PEM key"))
	signature = private_key.sign(message.encode(), padding.PKCS1v15(), hashes.SHA512())
	return base64.b64encode(signature).decode()


@frappe.whitelist()
def get_print_config(pos_profile):
	_assert_pos_access(pos_profile)
	profile = frappe.get_doc("POS Profile", pos_profile)
	return {
		"qz_print": profile.get("custom_qz_print"),
		"qz_host": profile.get("custom_qz_host") or "localhost",
		"qz_printer": profile.get("custom_qz_printer"),
		"printers": [
			{
				"printer": row.printer,
				"bill": row.bill,
				"kot": row.kot,
			}
			for row in (profile.get("custom_printer_settings") or [])
		],
		"table_order_printer": profile.get("custom_table_order_printer"),
		"parcel_order_printer": profile.get("custom_parcel_order_printer"),
	}
