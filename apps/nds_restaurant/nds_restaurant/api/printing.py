# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _


@frappe.whitelist()
def print_kot(kot_name):
	"""Resolve printer for a KOT and queue network print if configured."""
	kot = frappe.get_doc("NDS KOT", kot_name)
	printer = _resolve_kot_printer(kot)
	if not printer:
		return {"printed": False, "reason": "no_printer"}

	html = frappe.get_print("NDS KOT", kot_name, print_format=None)
	try:
		from frappe.utils.print_format import print_by_server

		print_by_server("NDS KOT", kot_name, printer, doc=None, no_letterhead=1)
		return {"printed": True, "printer": printer}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS Network Print")
		return {"printed": False, "html": html, "printer": printer}


@frappe.whitelist()
def get_bill_html(invoice):
	return frappe.get_print("POS Invoice", invoice)


@frappe.whitelist()
def get_print_config(pos_profile):
	profile = frappe.get_doc("POS Profile", pos_profile)
	return {
		"qz_print": profile.get("custom_qz_print"),
		"qz_host": profile.get("custom_qz_host") or "localhost",
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


def _resolve_kot_printer(kot):
	# Production unit printers first
	unit = frappe.get_doc("NDS Production Unit", kot.production_unit)
	for row in unit.printer_settings or []:
		if row.kot and row.printer:
			if kot.order_type == "Take Away" and row.block_takeaway_kot:
				continue
			return row.printer

	# Room printers
	if kot.table:
		room = frappe.db.get_value("NDS Table", kot.table, "restaurant_room")
		if room:
			room_doc = frappe.get_doc("NDS Room", room)
			for row in room_doc.printer_settings or []:
				if row.kot and row.printer:
					return row.printer

	# POS Profile fallback
	profile = frappe.get_doc("POS Profile", kot.pos_profile) if kot.pos_profile else None
	if not profile:
		return None
	if kot.order_type in ("Take Away", "Delivery"):
		return profile.get("custom_parcel_order_printer")
	return profile.get("custom_table_order_printer")
