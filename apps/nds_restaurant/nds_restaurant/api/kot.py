# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, now_datetime, time_diff_in_seconds


def on_pos_invoice_update(doc, method=None):
	# KOT generation is primarily triggered explicitly from POS API
	pass


def on_pos_invoice_trash(doc, method=None):
	from nds_restaurant.api.pos import _free_nds_table_for_invoice

	_cancel_kots_for_deleted_draft(doc)
	_free_nds_table_for_invoice(doc.name, doc=doc)


def _cancel_kots_for_deleted_draft(doc):
	"""P5-T2: deleting a draft the kitchen already has sends Cancelled KOTs for the sent items.

	Skipped when the caller already handled the kitchen (merge_orders sets
	frappe.flags.nds_skip_trash_kots to the invoice name). A failure is logged, never blocks the delete.
	"""
	if doc.docstatus != 0 or not frappe.db.table_exists("NDS KOT"):
		return
	if getattr(frappe.flags, "nds_skip_trash_kots", None) == doc.name:
		return
	if not frappe.db.exists("NDS KOT", {"pos_invoice": doc.name, "docstatus": 1}):
		return
	try:
		if not sent_state(doc.name):
			return
		frappe.db.savepoint("nds_trash_kots")
		generate_kots(doc.name, cancel_all=True, comments=_("Order {0} deleted").format(doc.name))
	except Exception:
		frappe.db.rollback(save_point="nds_trash_kots")
		frappe.log_error(title="KOT Creation Failed", message=frappe.get_traceback())


def before_pos_invoice_cancel(doc, method=None):
	"""Cancel submitted KOTs so paid invoices can be voided."""
	for kot_name in frappe.get_all(
		"NDS KOT",
		filters={"pos_invoice": doc.name, "docstatus": 1},
		pluck="name",
	):
		kot = frappe.get_doc("NDS KOT", kot_name)
		if kot.docstatus == 1:
			kot.flags.ignore_permissions = True
			kot.cancel()


def on_pos_invoice_cancel(doc, method=None):
	from nds_restaurant.api.pos import _free_nds_table_for_invoice

	_free_nds_table_for_invoice(doc.name, doc=doc)


BASELINE_KOT_TYPES = ("New Order", "Modified", "Transfer")
CANCEL_KOT_TYPES = ("Cancelled", "Partially Cancelled")
# P5-T3: KOTs the kitchen actually prepares (they can be Served and then Picked Up).
READY_KOT_TYPES = ("New Order", "Modified")
STATUS_READY_FOR_PREPARE = "Ready For Prepare"
STATUS_SERVED = "Served"
STATUS_PICKED_UP = "Picked Up"


def _kot_has(fieldname):
	return frappe.get_meta("NDS KOT").has_field(fieldname)


def _course_info(course, cache=None):
	"""(serving_priority, indicate_in_kds, course label) for an NDS Menu Course (P5-T4)."""
	if not course:
		return None, 0, None
	if cache is not None and course in cache:
		return cache[course]
	info = (None, 0, course)
	if frappe.db.exists("NDS Menu Course", course):
		meta = frappe.get_meta("NDS Menu Course")
		fields = [f for f in ("serving_priority", "indicate_in_kds", "course") if meta.has_field(f)]
		row = frappe.db.get_value("NDS Menu Course", course, fields, as_dict=True) if fields else {}
		info = (
			row.get("serving_priority") if row.get("serving_priority") is not None else None,
			1 if row.get("indicate_in_kds") else 0,
			row.get("course") or course,
		)
	if cache is not None:
		cache[course] = info
	return info


def latest_baseline_kot(invoice, unit):
	"""P5-T2: the KOT a cancel refers to, i.e. the unit's latest New Order/Modified/Transfer KOT."""
	rows = frappe.get_all(
		"NDS KOT",
		filters={
			"pos_invoice": invoice,
			"production_unit": unit,
			"docstatus": 1,
			"kot_type": ["in", list(BASELINE_KOT_TYPES)],
		},
		pluck="name",
		order_by="creation desc, name desc",
		limit=1,
	)
	return rows[0] if rows else None


def _kot_header_extras(doc, profile, kot_type=None, unit=None):
	"""P5-T2/T4/T6 header fields, each only when this site's NDS KOT has the field."""
	extras = {}
	if _kot_has("branch") and frappe.get_meta("POS Profile").has_field("custom_branch") and profile.get("custom_branch"):
		extras["branch"] = profile.custom_branch
	if _kot_has("customer_name") and doc.get("customer_name"):
		extras["customer_name"] = doc.customer_name
	if _kot_has("order_status"):
		extras["order_status"] = STATUS_READY_FOR_PREPARE
	# P7-T2: the invoice's daily order number on every KOT of the order
	if _kot_has("daily_order_no") and doc.get("custom_daily_order_no"):
		extras["daily_order_no"] = doc.custom_daily_order_no
	# P8-T3: "Talabat #<id>" on the KDS card
	if _kot_has("aggregator") and doc.get("custom_aggregator"):
		extras["aggregator"] = doc.get("customer_name") or doc.custom_aggregator
		if _kot_has("aggregator_order_id") and doc.get("custom_aggregator_order_id"):
			extras["aggregator_order_id"] = doc.custom_aggregator_order_id
	if kot_type in CANCEL_KOT_TYPES and unit and _kot_has("original_kot"):
		original = latest_baseline_kot(doc.name, unit)
		if original:
			extras["original_kot"] = original
	return extras


def kot_type_supported(kot_type):
	"""True when the NDS KOT kot_type Select offers this option (unmigrated sites may not)."""
	field = frappe.get_meta("NDS KOT").get_field("kot_type")
	options = [o.strip() for o in ((field.options if field else "") or "").split("\n")]
	return kot_type in options


def _kot_item_entry(row):
	return {
		"qty": flt(row.qty),
		"item_code": row.item,
		"notes": row.get("comments") or "",
		"addon_group_id": row.get("addon_group_id") or "",
		"is_addon": row.get("is_addon") or 0,
		"course": row.get("course") or None,
	}


def sent_state(invoice):
	"""Per production unit, the quantities the kitchen currently holds for an invoice.

	Walks the submitted KOTs in order: New Order / Modified / Transfer KOTs carry the full state of
	their unit, Partially Cancelled KOTs lower the listed lines to their new qty, Cancelled KOTs clear
	the unit, and Duplicate (reprint) KOTs are ignored. Returns {unit: {(item, notes, addon_group):
	entry}}.
	"""
	state = {}
	kot_names = frappe.get_all(
		"NDS KOT",
		filters={"pos_invoice": invoice, "docstatus": 1},
		fields=["name", "kot_type", "production_unit"],
		order_by="creation asc, name asc",
	)
	for row in kot_names:
		if row.kot_type not in BASELINE_KOT_TYPES + CANCEL_KOT_TYPES:
			continue
		kot = frappe.get_doc("NDS KOT", row.name)
		unit = kot.production_unit
		if kot.kot_type in BASELINE_KOT_TYPES:
			unit_map = {}
			for item in kot.items:
				if flt(item.qty) <= 0:
					continue
				entry = _kot_item_entry(item)
				key = (entry["item_code"], entry["notes"], entry["addon_group_id"])
				if key in unit_map:
					unit_map[key]["qty"] += entry["qty"]
				else:
					unit_map[key] = entry
			state[unit] = unit_map
		elif kot.kot_type == "Cancelled":
			state[unit] = {}
		else:
			unit_map = state.setdefault(unit, {})
			for item in kot.items:
				entry = _kot_item_entry(item)
				key = (entry["item_code"], entry["notes"], entry["addon_group_id"])
				if entry["qty"] <= 0:
					unit_map.pop(key, None)
				elif key in unit_map:
					unit_map[key]["qty"] = entry["qty"]
				else:
					unit_map[key] = entry
	return {unit: items for unit, items in state.items() if items}


def sent_quantities(invoice):
	"""{(item_code, notes, addon_group_id): qty} already sent to the kitchen, summed over units."""
	totals = {}
	for unit_map in sent_state(invoice).values():
		for key, entry in unit_map.items():
			totals[key] = totals.get(key, 0) + flt(entry["qty"])
	return totals


def sent_items_payload(invoice):
	return [
		{"item_code": k[0], "notes": k[1], "addon_group_id": k[2], "qty": qty}
		for k, qty in sorted(sent_quantities(invoice).items())
		if qty > 0
	]



@frappe.whitelist()
def kot_execute(invoice):
	"""Generate KOTs for a POS Invoice by routing items to Production Units (list of KOT names)."""
	return generate_kots(invoice)


def kot_execute_with_warnings(invoice):
	"""P5-T1: {created, warnings}; warnings name items whose group isn't in any Production Unit."""
	warnings = []
	created = generate_kots(invoice, warnings=warnings)
	return {"created": created, "warnings": warnings}


def generate_kots(invoice, cancel_all=False, comments=None, warnings=None):
	"""Diff the invoice against its last KOTs per unit and submit New/Modified/Cancelled KOTs.

	cancel_all=True treats the order as empty (void): every unit with outstanding items gets a
	Cancelled KOT. `comments` overrides the order comments on the generated KOTs. Pass a list as
	`warnings` to collect the unmapped-item-group warnings (P5-T1).
	"""
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
	if not units and not cancel_all and doc.items:
		# P5-T1
		frappe.throw(_("Create NDS Production unit against POS Profile {0}").format(doc.pos_profile))
	group_to_unit = {}
	for unit_name in units:
		unit = frappe.get_doc("NDS Production Unit", unit_name)
		for row in unit.item_groups:
			group_to_unit[row.item_group] = unit_name
	course_cache = {}
	unmapped = []

	invoice_item_meta = frappe.get_meta("POS Invoice Item")
	kot_item_meta = frappe.get_meta("NDS KOT Items")

	# P3-T6: Group current invoice items by (item_code, notes, addon_group_id) key
	current = {}
	for item in ([] if cancel_all else doc.items):
		item_group = frappe.db.get_value("Item", item.item_code, "item_group")
		unit = group_to_unit.get(item_group)
		if not unit:
			if (item_group, item.item_code) not in unmapped:
				unmapped.append((item_group, item.item_code))
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

	if warnings is not None:
		for item_group, item_code in unmapped:
			warnings.append(
				_("Item group '{0}' for item '{1}' is not in any production").format(item_group or "", item_code)
			)

	# P3-T6: what the kitchen already has, per unit, keyed by (item_code, notes, addon_group_id).
	prev_items = sent_state(doc.name)

	created = []
	order_type = doc.get("custom_nds_order_type") or "Dine In"
	table = doc.get("custom_nds_table")
	if comments is None:
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

		from nds_restaurant.kot_naming import cancellation_kot_naming_series

		kot_naming_series = (
			cancellation_kot_naming_series(series)
			if kot_type in ("Cancelled", "Partially Cancelled")
			else series
		)

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
			if kot_item_meta.has_field("serving_priority") and it.get("course"):
				priority = _course_info(it["course"], course_cache)[0]
				if priority is not None:
					kot_item["serving_priority"] = priority

			kot_items.append(kot_item)

		kot = frappe.get_doc(
			{
				"doctype": "NDS KOT",
				"naming_series": kot_naming_series,
				"kot_type": kot_type,
				"production_unit": unit,
				"pos_invoice": doc.name,
				"table": table,
				"order_type": order_type,
				"pos_profile": doc.pos_profile,
				"user": frappe.session.user,
				"comments": comments,
				"items": kot_items,
				**_kot_header_extras(doc, profile, kot_type=kot_type, unit=unit),
			}
		)
		kot.insert(ignore_permissions=True)
		kot.submit()
		_publish_new_kot(kot)
		created.append(kot.name)
		_maybe_print_kot(kot)

	frappe.db.set_value(
		"POS Invoice",
		doc.name,
		"custom_kot_generated",
		1,
		update_modified=False,
	)
	return created


def create_notice_kot(invoice, unit, unit_items, comments, old_qty=None, kot_type="Transfer"):
	"""Submit an informational KOT (merge/transfer notice) that also becomes the unit's baseline.

	unit_items: {(item, notes, addon_group): entry} as returned by sent_state(). old_qty maps the
	same keys to what the receiving order already had. Falls back to a Modified KOT on sites whose
	kot_type Select doesn't offer the notice type yet.
	"""
	doc = frappe.get_doc("POS Invoice", invoice)
	profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	series = profile.get("custom_kot_naming_series") or "KOT-.#####"
	if not kot_type_supported(kot_type):
		kot_type = "Modified"
	kot_item_meta = frappe.get_meta("NDS KOT Items")
	old_qty = old_qty or {}
	rows = []
	for key, entry in sorted(unit_items.items()):
		if flt(entry["qty"]) <= 0:
			continue
		row = {
			"item": entry["item_code"],
			"item_name": frappe.db.get_value("Item", entry["item_code"], "item_name"),
			"qty": entry["qty"],
			"old_qty": flt(old_qty.get(key) or 0),
		}
		if kot_item_meta.has_field("comments") and entry.get("notes"):
			row["comments"] = entry["notes"]
		if kot_item_meta.has_field("addon_group_id") and entry.get("addon_group_id"):
			row["addon_group_id"] = entry["addon_group_id"]
		if kot_item_meta.has_field("is_addon") and entry.get("is_addon"):
			row["is_addon"] = entry["is_addon"]
		if kot_item_meta.has_field("course") and entry.get("course"):
			row["course"] = entry["course"]
			if kot_item_meta.has_field("serving_priority"):
				priority = _course_info(entry["course"])[0]
				if priority is not None:
					row["serving_priority"] = priority
		rows.append(row)
	if not rows:
		return None
	kot = frappe.get_doc(
		{
			"doctype": "NDS KOT",
			"naming_series": series,
			"kot_type": kot_type,
			"production_unit": unit,
			"pos_invoice": doc.name,
			"table": doc.get("custom_nds_table"),
			"order_type": doc.get("custom_nds_order_type") or "Dine In",
			"pos_profile": doc.pos_profile,
			"user": frappe.session.user,
			"comments": comments,
			"items": rows,
			**_kot_header_extras(doc, profile, kot_type=kot_type, unit=unit),
		}
	)
	kot.insert(ignore_permissions=True)
	kot.submit()
	_publish_new_kot(kot)
	_maybe_print_kot(kot)
	return kot.name


DUPLICATE_SKIP_FIELDS = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}


def create_duplicate_kot(kot_name):
	"""P5-T5: submit a copy of a KOT with kot_type Duplicate, linked through original_kot.

	Duplicates are a reprint for the kitchen: sent_state() ignores them, so later order
	edits still diff against the real New Order/Modified/cancel history.
	"""
	original = frappe.get_doc("NDS KOT", kot_name)
	if original.kot_type == "Duplicate" and original.get("original_kot"):
		original = frappe.get_doc("NDS KOT", original.original_kot)
	if not kot_type_supported("Duplicate"):
		frappe.throw(_("This site's NDS KOT has no Duplicate type; run bench migrate"))

	kot_meta = frappe.get_meta("NDS KOT")
	item_meta = frappe.get_meta("NDS KOT Items")
	header_fields = [
		df.fieldname
		for df in kot_meta.fields
		if df.fieldtype not in ("Table", "Section Break", "Column Break", "Tab Break", "HTML", "Button")
		and df.fieldname not in DUPLICATE_SKIP_FIELDS
	]
	values = {f: original.get(f) for f in header_fields}
	series = None
	if original.get("pos_profile") and frappe.db.exists("POS Profile", original.pos_profile):
		series = frappe.db.get_value("POS Profile", original.pos_profile, "custom_kot_naming_series")
	values.update(
		{
			"doctype": "NDS KOT",
			"naming_series": series or "KOT-.#####",
			"kot_type": "Duplicate",
			"user": frappe.session.user,
		}
	)
	for fieldname, value in (
		("original_kot", original.name),
		("served", 0),
		("serve_time", None),
		("confirmed", 0),
		("verified_by", None),
		("delay_notified", 0),
		("picked_up_time", None),
		("production_time", None),
	):
		if kot_meta.has_field(fieldname):
			values[fieldname] = value
	if kot_meta.has_field("order_status") and original.get("order_status"):
		values["order_status"] = "Ready For Prepare" if "Ready For Prepare" in (
			kot_meta.get_field("order_status").options or ""
		).split("\n") else original.order_status

	item_fields = [
		df.fieldname
		for df in item_meta.fields
		if df.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML", "Button")
	]
	values["items"] = [
		{**{f: row.get(f) for f in item_fields}, **({"served": 0} if item_meta.has_field("served") else {})}
		for row in original.items
	]
	duplicate = frappe.get_doc(values)
	# The draft behind a cancel KOT is usually deleted; the copy must still be creatable.
	duplicate.flags.ignore_links = True
	duplicate.insert(ignore_permissions=True)
	duplicate.submit()
	_publish_new_kot(duplicate)
	return duplicate.name


def retarget_open_kots(invoice, table):
	"""Point the not-yet-served KOTs of an invoice at a new table so the KDS shows where to serve."""
	names = frappe.get_all(
		"NDS KOT",
		filters={"pos_invoice": invoice, "docstatus": 1, "served": 0},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value("NDS KOT", name, "table", table, update_modified=False)
	return names


@frappe.whitelist()
def get_kots(production_unit, include_served=0):
	from nds_restaurant.utils.access import assert_kds_access

	assert_kds_access(production_unit)
	return _get_kots(production_unit, include_served)


def _get_kots(production_unit, include_served=0):
	filters = {"production_unit": production_unit, "docstatus": 1}
	kot_meta = frappe.get_meta("NDS KOT")
	if not int(include_served or 0):
		# P5-T3: open work is "Ready For Prepare"; verified cancels leave the board (P4-T8)
		if kot_meta.has_field("order_status"):
			filters["order_status"] = STATUS_READY_FOR_PREPARE
		filters["served"] = 0
		filters["confirmed"] = 0
	fields = [
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
	]
	for optional in ("original_kot", "branch", "customer_name", "order_status", "aggregator", "aggregator_order_id"):
		if kot_meta.has_field(optional):
			fields.append(optional)
	kots = frappe.get_all(
		"NDS KOT",
		filters=filters,
		fields=fields,
		order_by="creation asc",
		limit_page_length=100,
	)
	# P5-T4: only the unit's branch. KOTs without a branch (made before P5) stay visible.
	unit_branch = frappe.db.get_value("NDS Production Unit", production_unit, "branch")
	if unit_branch and kot_meta.has_field("branch"):
		kots = [k for k in kots if not k.get("branch") or k.get("branch") == unit_branch]
	kot_item_meta = frappe.get_meta("NDS KOT Items")
	course_cache = {}
	result = []
	for k in kots:
		doc = frappe.get_doc("NDS KOT", k.name)
		d = k
		rows = []
		for r in doc.items:
			row = {
				"item": r.item,
				"item_name": r.item_name,
				"qty": r.qty,
				"old_qty": r.old_qty,
				"comments": r.comments,
				"served": r.served,
			}
			if kot_item_meta.has_field("is_addon"):
				row["is_addon"] = r.get("is_addon") or 0
			if kot_item_meta.has_field("addon_group_id"):
				row["addon_group_id"] = r.get("addon_group_id") or ""
			if kot_item_meta.has_field("cancelled_qty"):
				row["cancelled_qty"] = r.get("cancelled_qty") or 0
			course = r.get("course") if kot_item_meta.has_field("course") else None
			priority, indicate, label = _course_info(course, course_cache)
			if kot_item_meta.has_field("serving_priority") and r.get("serving_priority"):
				priority = r.serving_priority
			row.update({"course": label, "serving_priority": priority, "indicate_in_kds": indicate})
			rows.append(row)
		d["items"] = _sort_items_by_priority(rows)
		pending = [x["serving_priority"] for x in d["items"] if x.get("serving_priority") is not None and not x.get("served")]
		d["priority"] = min(pending) if pending else None
		result.append(d)
	return result


def _sort_items_by_priority(rows):
	"""P5-T4: lowest serving priority first; add-ons stay right after the item they belong to."""
	groups = []
	by_group = {}
	for row in rows:
		gid = row.get("addon_group_id") or ""
		if row.get("is_addon") and gid and gid in by_group:
			by_group[gid]["rows"].append(row)
			continue
		group = {"rows": [row], "priority": row.get("serving_priority"), "idx": len(groups)}
		groups.append(group)
		if gid and not row.get("is_addon"):
			by_group[gid] = group
	groups.sort(key=lambda g: (g["priority"] is None, g["priority"] if g["priority"] is not None else 0, g["idx"]))
	return [row for g in groups for row in g["rows"]]


def _kot_for_kds(kot_name):
	from nds_restaurant.utils.access import assert_kds_access

	if not kot_name or not frappe.db.exists("NDS KOT", kot_name):
		frappe.throw(_("KOT {0} not found").format(kot_name or ""))
	doc = frappe.get_doc("NDS KOT", kot_name)
	assert_kds_access(doc.production_unit)
	return doc


@frappe.whitelist(methods=["POST"])
def serve_kot(kot_name):
	doc = _kot_for_kds(kot_name)
	serve_time = now_datetime()
	values = {"served": 1, "serve_time": serve_time}
	if _kot_has("order_status"):
		values["order_status"] = STATUS_SERVED
	if _kot_has("production_time") and doc.creation:
		# P5-T3: whole minutes from KOT creation to serve
		values["production_time"] = max(int(time_diff_in_seconds(serve_time, doc.creation) // 60), 0)
	# db_set: a submitted KOT may point at a draft that was since cancelled or merged
	# (deleted), so a full save() would fail link validation.
	doc.db_set(values)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def mark_picked_up(kot_name):
	"""P5-T3: the captain collected a served KOT from the pass (Served -> Picked Up).

	P4-T7 guard: same KDS access rule (NDS role + branch seat, managers exempt) plus POS Profile access.
	"""
	from nds_restaurant.api.pos import _assert_pos_profile_access

	if not _kot_has("order_status") or not _kot_has("picked_up_time"):
		frappe.throw(_("NDS KOT has no Picked Up status on this site; run bench migrate"))
	doc = _kot_for_kds(kot_name)
	if doc.pos_profile:
		_assert_pos_profile_access(doc.pos_profile)
	if doc.docstatus != 1 or doc.kot_type not in READY_KOT_TYPES:
		frappe.throw(_("Only New Order and Modified KOTs can be picked up"))
	status = doc.get("order_status") or (STATUS_SERVED if doc.served else STATUS_READY_FOR_PREPARE)
	if status == STATUS_PICKED_UP:
		frappe.throw(_("KOT {0} is already picked up").format(doc.name))
	if status != STATUS_SERVED:
		frappe.throw(_("KOT {0} is not served yet").format(doc.name))
	picked_up_time = now_datetime()
	doc.db_set({"order_status": STATUS_PICKED_UP, "picked_up_time": picked_up_time})
	return {"ok": True, "kot": doc.name, "order_status": STATUS_PICKED_UP, "picked_up_time": picked_up_time}


@frappe.whitelist(methods=["POST"])
def confirm_kot(kot_name):
	"""P4-T8: a manager verifies a cancel KOT; it then leaves the KDS."""
	from nds_restaurant.utils.access import get_capabilities

	doc = _kot_for_kds(kot_name)
	if not get_capabilities(profile=doc.pos_profile)["can_verify_cancel"]:
		frappe.throw(_("Only an NDS Manager can verify cancelled KOTs"), frappe.PermissionError)
	if doc.kot_type not in CANCEL_KOT_TYPES:
		frappe.throw(_("Only cancel KOTs need verification"))
	values = {"confirmed": 1, "served": 1, "serve_time": now_datetime()}
	kot_meta = frappe.get_meta("NDS KOT")
	if kot_meta.has_field("verified_by"):
		values["verified_by"] = frappe.session.user
	if kot_meta.has_field("order_status"):
		values["order_status"] = "Served"
	# Cancel KOTs usually outlive their (deleted) draft, so avoid save()'s link validation.
	doc.db_set(values)
	return {"ok": True, "verified_by": values.get("verified_by")}


@frappe.whitelist()
def get_production_units():
	"""P4-T7: units in the user's branches (managers see all); empty without an NDS role."""
	from nds_restaurant.utils.access import can_view_all_units, has_kds_role, user_branches

	if frappe.session.user == "Guest" or not has_kds_role():
		return []
	units = frappe.get_all(
		"NDS Production Unit",
		fields=["name", "pos_profile", "branch"],
		order_by="name asc",
	)
	if can_view_all_units():
		return units
	branches = user_branches()
	return [u for u in units if u.branch and u.branch in branches]


@frappe.whitelist()
def get_kds_context(production_unit):
	from nds_restaurant.utils.access import assert_kds_access, get_capabilities

	if not frappe.db.exists("NDS Production Unit", production_unit):
		frappe.throw(_("Production Unit {0} not found").format(production_unit))
	assert_kds_access(production_unit)
	unit = frappe.get_doc("NDS Production Unit", production_unit)
	profile = frappe.get_doc("POS Profile", unit.pos_profile) if unit.pos_profile else None
	return {
		"production_unit": production_unit,
		"kot_warning_time": (profile.get("custom_kot_warning_time") if profile else 15) or 15,
		"kot_audio_alert": profile.get("custom_kot_audio_alert") if profile else 0,
		"kot_alert_sound": profile.get("custom_kot_alert_sound") if profile else None,
		"can_verify": get_capabilities(profile=profile)["can_verify_cancel"],
		"kots": _get_kots(production_unit),
	}


def _publish_kds_event(event, message):
	"""P5-T7: realtime nudge for KDS screens (polling stays the fallback).

	Published to the site room (every Desk user); NDS roles have desk access, so
	every KDS user is a System User. The payload carries names only.
	"""
	try:
		frappe.publish_realtime(event, message, after_commit=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS KDS realtime")


def _publish_new_kot(kot):
	_publish_kds_event(
		"nds_new_kot",
		{"kot": kot.name, "production_unit": kot.production_unit, "kot_type": kot.kot_type},
	)


def _delay_job_ready():
	if not frappe.db.table_exists("NDS KOT") or not frappe.db.table_exists("NDS Notification Recipient"):
		return False
	kmeta = frappe.get_meta("NDS KOT")
	pmeta = frappe.get_meta("POS Profile")
	return (
		pmeta.has_field("custom_notify_kot_delay")
		and kmeta.has_field("order_status")
		and kmeta.has_field("delay_notified")
	)


def _delay_recipients(profile, branch, cache):
	"""Users holding one of the profile's recipient roles AND seated in the branch."""
	key = (profile, branch)
	if key in cache:
		return cache[key]
	from nds_restaurant.utils.access import branch_users

	roles = frappe.get_all(
		"NDS Notification Recipient",
		filters={"parent": profile, "parenttype": "POS Profile"},
		pluck="role",
	)
	users = []
	seated = set(branch_users(branch)) if branch else set()
	if roles and seated:
		with_role = set(
			frappe.get_all(
				"Has Role",
				filters={"role": ["in", roles], "parenttype": "User", "parent": ["in", list(seated)]},
				pluck="parent",
			)
		)
		users = sorted(
			frappe.get_all(
				"User",
				filters={"name": ["in", list(with_role)], "enabled": 1},
				pluck="name",
			)
			if with_role
			else []
		)
		users = [u for u in users if u not in ("Administrator", "Guest")]
	cache[key] = users
	return users


def check_kot_delays(pos_profile=None):
	"""P5-T8 (every minute): one alert per delayed KOT per recipient, then mark it notified.

	A KOT is delayed when it is still Ready For Prepare and older than the profile's
	KOT Warning Time. Recipients are users with a role from the profile's Recipients
	table who are also in the Branch Users table of the KOT's branch.
	"""
	if not _delay_job_ready():
		return
	kmeta = frappe.get_meta("NDS KOT")
	has_branch = kmeta.has_field("branch")
	unit_has_branch = frappe.get_meta("NDS Production Unit").has_field("branch")
	profile_has_branch = frappe.get_meta("POS Profile").has_field("custom_branch")
	filters = {"custom_notify_kot_delay": 1, "disabled": 0}
	if pos_profile:
		filters["name"] = pos_profile
	profiles = frappe.get_all(
		"POS Profile",
		filters=filters,
		fields=["name", "custom_kot_warning_time"]
		+ (["custom_branch"] if profile_has_branch else []),
	)
	now = now_datetime()
	cache = {}
	unit_branch = {}
	for p in profiles:
		minutes = cint(p.get("custom_kot_warning_time")) or 15
		cutoff = add_to_date(now, minutes=-minutes)
		delayed = frappe.get_all(
			"NDS KOT",
			filters={
				"pos_profile": p.name,
				"docstatus": 1,
				"kot_type": ["in", list(READY_KOT_TYPES)],
				"order_status": STATUS_READY_FOR_PREPARE,
				"served": 0,
				"delay_notified": 0,
				"creation": ["<", cutoff],
			},
			fields=["name", "production_unit", "table", "creation"] + (["branch"] if has_branch else []),
			order_by="creation asc",
		)
		for kot in delayed:
			branch = kot.get("branch")
			if not branch and unit_has_branch and kot.production_unit:
				if kot.production_unit not in unit_branch:
					unit_branch[kot.production_unit] = frappe.db.get_value(
						"NDS Production Unit", kot.production_unit, "branch"
					)
				branch = unit_branch[kot.production_unit]
			branch = branch or p.get("custom_branch")
			late = int(time_diff_in_seconds(now, kot.creation) // 60)
			subject = _("KOT {0} ({1}, table {2}) delayed {3} min").format(
				kot.name, kot.production_unit or "-", kot.table or "-", late
			)
			for user in _delay_recipients(p.name, branch, cache):
				frappe.get_doc(
					{
						"doctype": "Notification Log",
						"subject": subject,
						"type": "Alert",
						"document_type": "NDS KOT",
						"document_name": kot.name,
						"for_user": user,
						"from_user": "Administrator",
					}
				).insert(ignore_permissions=True)
			frappe.db.set_value("NDS KOT", kot.name, "delay_notified", 1, update_modified=False)
			_publish_kds_event(
				"nds_kot_delay",
				{"kot": kot.name, "production_unit": kot.production_unit, "minutes": late},
			)


def _maybe_print_kot(kot):
	from nds_restaurant.api.printing import _print_kot

	try:
		_print_kot(kot)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "NDS KOT Print")
