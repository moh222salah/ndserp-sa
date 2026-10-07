# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, add_to_date


def on_pos_invoice_update(doc, method=None):
	# KOT generation is primarily triggered explicitly from POS API
	pass


def on_pos_invoice_trash(doc, method=None):
	if doc.custom_nds_table:
		frappe.db.set_value(
			"NDS Table",
			doc.custom_nds_table,
			{"occupied": 0, "current_invoice": None},
		)


@frappe.whitelist()
def kot_execute(invoice):
	"""Generate KOTs for a POS Invoice by routing items to Production Units."""
	doc = frappe.get_doc("POS Invoice", invoice)
	profile = frappe.get_doc("POS Profile", doc.pos_profile)
	series = profile.get("custom_kot_naming_series") or "KOT-.#####"
	if not series:
		frappe.throw(_("Set KOT Naming Series on POS Profile"))

	# Build item_group -> production unit map
	units = frappe.get_all(
		"NDS Production Unit",
		filters={"pos_profile": doc.pos_profile},
		pluck="name",
	)
	group_to_unit = {}
	for unit_name in units:
		unit = frappe.get_doc("NDS Production Unit", unit_name)
		for row in unit.item_groups:
			group_to_unit[row.item_group] = unit_name

	invoice_item_meta = frappe.get_meta("POS Invoice Item")
	kot_item_meta = frappe.get_meta("NDS KOT Items")

	# P3-T6: Group current invoice items by (item_code, notes, addon_group_id) key
	current = {}
	for item in doc.items:
		item_group = frappe.db.get_value("Item", item.item_code, "item_group")
		unit = group_to_unit.get(item_group)
		if not unit:
			continue
		current.setdefault(unit, {})
		
		notes = item.get("custom_nds_notes") or "" if invoice_item_meta.has_field("custom_nds_notes") else ""
		addon_group = (
			item.get("custom_addon_group_id") or ""
			if invoice_item_meta.has_field("custom_addon_group_id")
			else ""
		)
		item_key = (item.item_code, notes, addon_group)

		if item_key not in current[unit]:
			current[unit][item_key] = {
				"qty": 0,
				"item_code": item.item_code,
				"notes": notes,
				"addon_group_id": addon_group,
				"is_addon": item.get("custom_is_addon") or 0
				if invoice_item_meta.has_field("custom_is_addon")
				else 0,
				"course": item.get("custom_nds_course") or None
				if invoice_item_meta.has_field("custom_nds_course")
				else None,
			}
		current[unit][item_key]["qty"] += flt(item.qty)

	# P3-T6: Previous KOTs with composite key for diff
	prev_items = {}
	prev_kots = frappe.get_all(
		"NDS KOT",
		filters={"pos_invoice": doc.name, "docstatus": 1, "kot_type": ["in", ["New Order", "Modified"]]},
		pluck="name",
		order_by="creation desc",
	)
	seen_units = set()
	for kot_name in prev_kots:
		kot = frappe.get_doc("NDS KOT", kot_name)
		if kot.production_unit in seen_units:
			continue
		seen_units.add(kot.production_unit)
		prev_items[kot.production_unit] = {}
		for row in kot.items:
			if flt(row.qty) <= 0:
				continue
			notes = row.get("comments") or ""
			addon_group = row.get("addon_group_id") or ""
			item_key = (row.item, notes, addon_group)
			prev_items[kot.production_unit][item_key] = {
				"qty": flt(row.qty),
				"item_code": row.item,
				"notes": notes,
				"addon_group_id": addon_group,
				"is_addon": row.get("is_addon") or 0,
				"course": row.get("course") or None,
			}

	created = []
	order_type = doc.get("custom_nds_order_type") or "Dine In"
	table = doc.get("custom_nds_table")
	comments = doc.get("custom_order_comments")

	all_units = set(current.keys()) | set(prev_items.keys())
	for unit in all_units:
		new_map = current.get(unit, {})
		old_map = prev_items.get(unit, {})

		if not old_map and new_map:
			kot_type = "New Order"
			items = [
				{
					"item": v["item_code"],
					"qty": v["qty"],
					"old_qty": 0,
					"notes": v["notes"],
					"addon_group_id": v["addon_group_id"],
					"is_addon": v["is_addon"],
					"course": v["course"],
				}
				for k, v in new_map.items()
			]
		elif not new_map and old_map:
			kot_type = "Cancelled"
			items = [
				{
					"item": v["item_code"],
					"qty": 0,
					"old_qty": v["qty"],
					"cancelled_qty": v["qty"],
					"notes": v["notes"],
					"addon_group_id": v["addon_group_id"],
					"is_addon": v["is_addon"],
					"course": v["course"],
				}
				for k, v in old_map.items()
			]
		else:
			# Items added or increased
			added = {
				k: new_map[k]
				for k in new_map
				if k not in old_map or new_map[k]["qty"] > old_map[k]["qty"]
			}
			# Items removed or decreased
			removed = {
				k: old_map[k]
				for k in old_map
				if k not in new_map or new_map[k]["qty"] < old_map[k]["qty"]
			}
			
			if not added and not removed:
				continue
			
			if removed and not added:
				kot_type = "Partially Cancelled"
				items = []
				for k, old_v in removed.items():
					new_v = new_map.get(k)
					new_qty = new_v["qty"] if new_v else 0
					cancelled = old_v["qty"] - new_qty
					items.append({
						"item": old_v["item_code"],
						"qty": new_qty,
						"old_qty": old_v["qty"],
						"cancelled_qty": cancelled,
						"notes": old_v["notes"],
						"addon_group_id": old_v["addon_group_id"],
						"is_addon": old_v["is_addon"],
						"course": old_v["course"],
					})
			else:
				kot_type = "Modified"
				items = []
				for k, old_v in removed.items():
					if k not in new_map:
						items.append({
							"item": old_v["item_code"],
							"qty": 0,
							"old_qty": old_v["qty"],
							"cancelled_qty": old_v["qty"],
							"notes": old_v["notes"],
							"addon_group_id": old_v["addon_group_id"],
							"is_addon": old_v["is_addon"],
							"course": old_v["course"],
						})
				for k, v in new_map.items():
					old_v = old_map.get(k)
					old_qty = old_v["qty"] if old_v else 0
					items.append({
						"item": v["item_code"],
						"qty": v["qty"],
						"old_qty": old_qty,
						"cancelled_qty": max(0, old_qty - v["qty"]),
						"notes": v["notes"],
						"addon_group_id": v["addon_group_id"],
						"is_addon": v["is_addon"],
						"course": v["course"],
					})

		if not items:
			continue

		# P3-T6: Include new fields in KOT items
		kot_items = []
		for it in items:
			kot_item = {
				"item": it["item"],
				"item_name": frappe.db.get_value("Item", it["item"], "item_name"),
				"qty": it["qty"],
				"old_qty": it["old_qty"],
			}
			
			if kot_item_meta.has_field("comments") and it.get("notes"):
				kot_item["comments"] = it["notes"]
			if kot_item_meta.has_field("addon_group_id") and it.get("addon_group_id"):
				kot_item["addon_group_id"] = it["addon_group_id"]
			if kot_item_meta.has_field("is_addon") and it.get("is_addon"):
				kot_item["is_addon"] = it["is_addon"]
			if kot_item_meta.has_field("course") and it.get("course"):
				kot_item["course"] = it["course"]
			if kot_item_meta.has_field("cancelled_qty") and it.get("cancelled_qty"):
				kot_item["cancelled_qty"] = it["cancelled_qty"]
			
			kot_items.append(kot_item)
		
		kot = frappe.get_doc(
			{
				"doctype": "NDS KOT",
				"naming_series": series,
				"kot_type": kot_type,
				"production_unit": unit,
				"pos_invoice": doc.name,
				"table": table,
				"order_type": order_type,
				"pos_profile": doc.pos_profile,
				"user": frappe.session.user,
				"comments": comments,
				"items": kot_items,
			}
		)
		kot.insert(ignore_permissions=True)
		kot.submit()
		created.append(kot.name)
		_maybe_print_kot(kot)

	frappe.db.set_value("POS Invoice", doc.name, "custom_kot_generated", 1)
	return created


@frappe.whitelist()
def get_kots(production_unit, include_served=0):
	filters = {"production_unit": production_unit, "docstatus": 1}
	if not int(include_served or 0):
		filters["served"] = 0
		filters["confirmed"] = 0

	kots = frappe.get_all(
		"NDS KOT",
		filters=filters,
		fields=[
			"name",
			"kot_type",
			"table",
			"order_type",
			"pos_invoice",
			"user",
			"creation",
			"comments",
			"served",
			"confirmed",
			"daily_order_no",
		],
		order_by="creation asc",
		limit_page_length=100,
	)
	result = []
	for k in kots:
		doc = frappe.get_doc("NDS KOT", k.name)
		d = k
		d["items"] = [
			{
				"item": r.item,
				"item_name": r.item_name,
				"qty": r.qty,
				"old_qty": r.old_qty,
				"comments": r.comments,
				"served": r.served,
			}
			for r in doc.items
		]
		result.append(d)
	return result


@frappe.whitelist()
def serve_kot(kot_name):
	doc = frappe.get_doc("NDS KOT", kot_name)
	doc.served = 1
	doc.serve_time = now_datetime()
	
	# Set order_status if field exists
	if frappe.get_meta("NDS KOT").has_field("order_status"):
		doc.order_status = "Served"
	
	doc.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def confirm_kot(kot_name):
	doc = frappe.get_doc("NDS KOT", kot_name)
	doc.confirmed = 1
	doc.served = 1
	doc.serve_time = now_datetime()
	
	# Set order_status if field exists
	if frappe.get_meta("NDS KOT").has_field("order_status"):
		doc.order_status = "Served"
	
	doc.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def get_production_units():
	return frappe.get_all(
		"NDS Production Unit",
		fields=["name", "pos_profile", "branch"],
		order_by="name asc"
	)


@frappe.whitelist()
def get_kds_context(production_unit):
	if not frappe.db.exists("NDS Production Unit", production_unit):
		frappe.throw(_("Production Unit {0} not found").format(production_unit))
	unit = frappe.get_doc("NDS Production Unit", production_unit)
	profile = frappe.get_doc("POS Profile", unit.pos_profile) if unit.pos_profile else None
	return {
		"production_unit": production_unit,
		"kot_warning_time": (profile.get("custom_kot_warning_time") if profile else 15) or 15,
		"kot_audio_alert": profile.get("custom_kot_audio_alert") if profile else 0,
		"kot_alert_sound": profile.get("custom_kot_alert_sound") if profile else None,
		"kots": get_kots(production_unit),
	}


def check_kot_delays():
	"""Hourly: notify when KOTs exceed warning time."""
	profiles = frappe.get_all(
		"POS Profile",
		filters={"custom_notify_kot_delay": 1},
		fields=["name", "custom_kot_warning_time"],
	)
	for p in profiles:
		minutes = p.custom_kot_warning_time or 15
		cutoff = add_to_date(now_datetime(), minutes=-minutes)
		delayed = frappe.get_all(
			"NDS KOT",
			filters={
				"pos_profile": p.name,
				"docstatus": 1,
				"served": 0,
				"creation": ["<", cutoff],
			},
			fields=["name", "production_unit", "table"],
		)
		if not delayed:
			continue
		recipients = frappe.get_all(
			"NDS Notification Recipient",
			filters={"parent": p.name, "parenttype": "POS Profile"},
			pluck="role",
		)
		users = set()
		for role in recipients:
			users.update(frappe.get_all("Has Role", filters={"role": role}, pluck="parent"))
		for user in users:
			if user in ("Administrator", "Guest"):
				continue
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"subject": _("KOT delay: {0} open tickets").format(len(delayed)),
					"email_content": _("Production units have delayed KOTs"),
					"type": "Alert",
					"document_type": "NDS KOT",
					"for_user": user,
				}
			).insert(ignore_permissions=True)


def _maybe_print_kot(kot):
	from nds_restaurant.api.printing import print_kot

	try:
		print_kot(kot.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS KOT Print")
