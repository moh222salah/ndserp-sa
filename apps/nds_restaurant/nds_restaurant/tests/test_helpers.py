# Copyright (c) 2026, NDS and contributors
# License: MIT

"""Shared helpers for nds_restaurant integration tests."""

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.utils import flt, nowdate, today


def new_test_run_id():
	return uuid.uuid4().hex[:8]


def code(run_id, suffix):
	return f"NDSUT-{run_id}-{suffix}"


def ensure_test_branch(run_id):
	branch_name = code(run_id, "BR")
	if frappe.db.exists("Branch", branch_name):
		return branch_name
	frappe.get_doc({"doctype": "Branch", "branch": branch_name}).insert(ignore_permissions=True)
	return branch_name


def get_pos_profile_with_restaurant():
	"""Return a POS Profile that has custom_restaurant set, or None."""
	for name in frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name"):
		if frappe.db.get_value("POS Profile", name, "custom_restaurant"):
			return name
	return None


def ensure_pos_opening_entry(pos_profile, user=None):
	"""Create or refresh an open POS Opening Entry for today."""
	user = user or frappe.session.user
	company = frappe.db.get_value("POS Profile", pos_profile, "company")
	posting_date = today()

	existing = frappe.db.get_value(
		"POS Opening Entry",
		{"user": user, "pos_profile": pos_profile, "status": "Open", "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if existing:
		frappe.db.set_value(
			"POS Opening Entry",
			existing,
			{"period_start_date": posting_date, "posting_date": posting_date},
			update_modified=True,
		)
		return existing

	mop = frappe.db.get_value("Mode of Payment", {}, "name") or "Cash"
	doc = frappe.get_doc(
		{
			"doctype": "POS Opening Entry",
			"period_start_date": posting_date,
			"period_end_date": posting_date,
			"posting_date": posting_date,
			"user": user,
			"pos_profile": pos_profile,
			"company": company,
			"balance_details": [{"mode_of_payment": mop, "opening_amount": 0}],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def ensure_bin_qty(item_code, warehouse, qty):
	if not warehouse:
		return
	bin_name = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "name")
	if bin_name:
		frappe.db.set_value("Bin", bin_name, "actual_qty", qty, update_modified=False)
	else:
		frappe.get_doc(
			{
				"doctype": "Bin",
				"item_code": item_code,
				"warehouse": warehouse,
				"actual_qty": qty,
			}
		).insert(ignore_permissions=True)


def delete_if_exists(doctype, name):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def delete_items(item_codes):
	for item_code in item_codes:
		delete_if_exists("Item", item_code)


def delete_menus(menu_names):
	for menu_name in menu_names:
		if not menu_name:
			continue
		pl_name = frappe.db.get_value("NDS Menu", menu_name, "price_list")
		delete_if_exists("NDS Menu", menu_name)
		delete_if_exists("Price List", pl_name)


@contextmanager
def ignore_item_menu_link_validation():
	"""Skip Item validate hook while building fixtures that intentionally violate menu rules."""
	with patch("nds_restaurant.api.items.validate_item_links"):
		yield


@contextmanager
def ignore_menu_variant_validation():
	"""Skip NDS Menu variant/add-on validation while building legacy text fixtures."""
	from nds_restaurant.nds_restaurant.doctype.nds_menu.nds_menu import NDSMenu

	with patch.object(NDSMenu, "validate_variants_and_addons", lambda self: None):
		yield


def set_menu_item_variants_text(menu_doc, row_index, variants_text):
	"""Update deprecated variants text without running full menu validation."""
	row = menu_doc.items[row_index]
	frappe.db.set_value(
		"NDS Menu Item",
		row.name,
		"variants",
		variants_text,
		update_modified=False,
	)
	menu_doc.reload()


def cancel_and_delete_kot(kot_name):
	if not kot_name or not frappe.db.exists("NDS KOT", kot_name):
		return
	kot = frappe.get_doc("NDS KOT", kot_name)
	if kot.docstatus == 1:
		kot.cancel()
	frappe.delete_doc("NDS KOT", kot_name, force=True, ignore_permissions=True)


def cancel_and_delete_pos_invoice(invoice_name):
	if not invoice_name or not frappe.db.exists("POS Invoice", invoice_name):
		return
	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus == 1:
		invoice.cancel()
	elif invoice.docstatus == 0:
		frappe.delete_doc("POS Invoice", invoice_name, force=True, ignore_permissions=True)
		return
	frappe.delete_doc("POS Invoice", invoice_name, force=True, ignore_permissions=True)


def cleanup_invoice_and_kots(invoice_name):
	for kot_name in frappe.get_all(
		"NDS KOT", filters={"pos_invoice": invoice_name}, pluck="name"
	):
		cancel_and_delete_kot(kot_name)
	cancel_and_delete_pos_invoice(invoice_name)


def as_frappe_rows(rows):
	"""Wrap dict rows like frappe.get_all returns for attribute access in app code."""
	return [frappe._dict(row) for row in rows]
