# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, floor


def get_item_availability(item_code, warehouse, exclude_invoice=None):
	"""Return portions available based on limiting ingredient stock minus draft reservations."""
	recipe = frappe.db.get_value("NDS Recipe", {"item": item_code, "enabled": 1}, "name")
	if not recipe:
		return None
	doc = frappe.get_doc("NDS Recipe", recipe)
	portions = None
	for row in doc.ingredients:
		if not row.qty:
			continue
		stock = flt(
			frappe.db.get_value(
				"Bin",
				{"item_code": row.ingredient, "warehouse": warehouse},
				"actual_qty",
			)
			or 0
		)
		reserved = _reserved_qty(row.ingredient, warehouse, exclude_invoice=exclude_invoice)
		available = max(stock - reserved, 0)
		p = floor(available / flt(row.qty))
		portions = p if portions is None else min(portions, p)
	return portions if portions is not None else 0


def get_stock_item_availability(item_code, warehouse, exclude_invoice=None):
	"""Available qty for a stock item minus qty reserved on other draft POS invoices."""
	if not frappe.db.get_value("Item", item_code, "is_stock_item"):
		return None
	actual_qty = flt(
		frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": warehouse},
			"actual_qty",
		)
		or 0
	)
	reserved = _reserved_stock_item_qty(item_code, warehouse, exclude_invoice=exclude_invoice)
	return max(actual_qty - reserved, 0)


def _reserved_qty(ingredient, warehouse, exclude_invoice=None):
	"""Sum ingredient demand from draft POS invoices that use recipes."""
	drafts = frappe.get_all(
		"POS Invoice",
		filters={"docstatus": 0, "set_warehouse": warehouse},
		pluck="name",
	)
	total = 0
	for inv in drafts:
		if exclude_invoice and inv == exclude_invoice:
			continue
		items = frappe.get_all(
			"POS Invoice Item",
			filters={"parent": inv},
			fields=["item_code", "qty"],
		)
		for it in items:
			recipe = frappe.db.get_value("NDS Recipe", {"item": it.item_code, "enabled": 1}, "name")
			if not recipe:
				continue
			req = frappe.db.get_value(
				"NDS Recipe Item",
				{"parent": recipe, "ingredient": ingredient},
				"qty",
			)
			if req:
				total += flt(req) * flt(it.qty)
	return total


def _reserved_stock_item_qty(item_code, warehouse, exclude_invoice=None):
	"""Sum qty of a stock item on draft POS invoices (non-recipe lines)."""
	if frappe.db.exists("NDS Recipe", {"item": item_code, "enabled": 1}):
		return 0

	drafts = frappe.get_all(
		"POS Invoice",
		filters={"docstatus": 0, "set_warehouse": warehouse},
		pluck="name",
	)
	total = 0
	for inv in drafts:
		if exclude_invoice and inv == exclude_invoice:
			continue
		rows = frappe.get_all(
			"POS Invoice Item",
			filters={"parent": inv, "item_code": item_code},
			fields=["qty"],
		)
		for row in rows:
			total += flt(row.qty)
	return total


@frappe.whitelist()
def get_availability_map(items, warehouse):
	import json

	if isinstance(items, str):
		items = json.loads(items)
	return {item: get_item_availability(item, warehouse) for item in items}


def on_pos_invoice_submit(doc, method=None):
	"""Create Material Issue Stock Entry from recipes."""
	issue_recipe_stock(doc)


def issue_recipe_stock(doc):
	"""Material Issue of the recipe ingredients for a POS Invoice or an aggregator Sales Invoice (P8-T2)."""
	if doc.get("custom_recipe_stock_entry"):
		return
	warehouse = doc.set_warehouse
	if not warehouse:
		return

	ingredients = {}
	for item in doc.items:
		recipe_name = frappe.db.get_value("NDS Recipe", {"item": item.item_code, "enabled": 1}, "name")
		if not recipe_name:
			continue
		recipe = frappe.get_doc("NDS Recipe", recipe_name)
		for row in recipe.ingredients:
			key = row.ingredient
			ingredients[key] = ingredients.get(key, 0) + flt(row.qty) * flt(item.qty)

	if not ingredients:
		return

	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": doc.company,
			"from_warehouse": warehouse,
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"s_warehouse": warehouse,
					"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
					"conversion_factor": 1,
					"transfer_qty": qty,
				}
				for item_code, qty in ingredients.items()
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	frappe.db.set_value(doc.doctype, doc.name, "custom_recipe_stock_entry", se.name)
	doc.custom_recipe_stock_entry = se.name


def on_pos_invoice_cancel(doc, method=None):
	"""Cancel linked recipe stock entry."""
	cancel_recipe_stock(doc)


def cancel_recipe_stock(doc):
	se_name = doc.get("custom_recipe_stock_entry")
	if not se_name:
		return
	if frappe.db.exists("Stock Entry", se_name):
		se = frappe.get_doc("Stock Entry", se_name)
		if se.docstatus == 1:
			se.cancel()
