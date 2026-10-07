# Copyright (c) 2026, NDS and contributors
# License: MIT

"""POS Invoice validate hooks for NDS Restaurant orders."""

import frappe


def validate_nds_menu_selling_price_list(doc, method=None):
	"""
	After ERPNext POS Invoice validate resets selling_price_list from the profile,
	re-apply the resolved NDS menu price list (line rates are left unchanged).

	Fail-safe on unmigrated shared sites: never raises; logs unexpected errors.
	"""
	try:
		_apply_nds_menu_selling_price_list(doc)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS menu price list")


def _apply_nds_menu_selling_price_list(doc):
	if doc.doctype != "POS Invoice" or not doc.pos_profile:
		return

	if doc.docstatus != 0:
		return

	if not _nds_menu_price_validate_schema_ready():
		return

	profile_meta = frappe.get_meta("POS Profile")
	if not profile_meta.has_field("custom_restaurant"):
		return

	profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	restaurant = profile.get("custom_restaurant")
	if not restaurant or not frappe.db.exists("NDS Restaurant", restaurant):
		return

	inv_meta = doc.meta
	order_type = None
	room = None
	if inv_meta.has_field("custom_nds_order_type"):
		order_type = doc.get("custom_nds_order_type")
	if inv_meta.has_field("custom_nds_room"):
		room = doc.get("custom_nds_room")

	# P8-T1: an aggregator order keeps its aggregator's price list
	if order_type == "Aggregator" and inv_meta.has_field("custom_aggregator") and doc.get("custom_aggregator"):
		from nds_restaurant.api.aggregators import order_settings

		settings = order_settings(doc)
		if settings and settings.get("price_list"):
			doc.selling_price_list = settings["price_list"]
			return

	from nds_restaurant.api.pos import _resolve_menu

	menu_name = _resolve_menu(restaurant, room, order_type)
	if not menu_name or not frappe.db.exists("NDS Menu", menu_name):
		return

	menu_meta = frappe.get_meta("NDS Menu")
	menu_doc = frappe.get_cached_doc("NDS Menu", menu_name)
	price_list = None
	if menu_meta.has_field("price_list") and menu_doc.get("price_list"):
		price_list = menu_doc.price_list
	elif profile.get("selling_price_list"):
		price_list = profile.selling_price_list

	if price_list and inv_meta.has_field("selling_price_list"):
		doc.selling_price_list = price_list


def _nds_menu_price_validate_schema_ready():
	"""Require doctypes, tables, and fields used by menu resolution and price list apply."""
	for doctype in ("NDS Restaurant", "NDS Menu"):
		if not frappe.db.exists("DocType", doctype):
			return False

	pos_profile_meta = frappe.get_meta("POS Profile")
	pos_invoice_meta = frappe.get_meta("POS Invoice")
	menu_meta = frappe.get_meta("NDS Menu")

	if not pos_profile_meta.has_field("custom_restaurant"):
		return False
	if not pos_invoice_meta.has_field("selling_price_list"):
		return False
	if not menu_meta.has_field("price_list"):
		return False

	rest_meta = frappe.get_meta("NDS Restaurant")
	if rest_meta.has_field("room_wise_menu") and not frappe.db.table_exists("NDS Menu For Room"):
		return False
	if rest_meta.has_field("order_type_wise_menu") and not frappe.db.table_exists(
		"NDS Order Type Menu"
	):
		return False

	if pos_invoice_meta.has_field("custom_nds_room") and not frappe.db.table_exists("NDS Room"):
		return False

	return True
