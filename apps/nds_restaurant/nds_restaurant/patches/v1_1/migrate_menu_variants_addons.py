"""
P3-T2: Migrate comma-separated variants and add-ons from NDS Menu Item
       to Item child tables (custom_pos_item_variants and custom_pos_add_on_items).

Idempotent: running twice adds nothing new.
Does not call Item.save() — inserts child rows directly to avoid Item validation aborting migrate.
"""

import frappe
from frappe import _


def execute():
	frappe.clear_cache(doctype="Item")
	meta = frappe.get_meta("Item")

	if not meta.has_field("custom_pos_item_variants"):
		frappe.log_error(
			title="Variant migration skipped",
			message="Item.custom_pos_item_variants field does not exist yet. Run after create_p3_item_fields patch.",
		)
		return

	if not meta.has_field("custom_pos_add_on_items"):
		frappe.log_error(
			title="Variant migration skipped",
			message="Item.custom_pos_add_on_items field does not exist yet. Run after create_p3_item_fields patch.",
		)
		return

	if not frappe.db.exists("DocType", "NDS POS Item Variant"):
		frappe.log_error(
			title="Variant migration skipped",
			message="DocType 'NDS POS Item Variant' does not exist yet.",
		)
		return

	if not frappe.db.exists("DocType", "NDS Item Add On"):
		frappe.log_error(
			title="Variant migration skipped",
			message="DocType 'NDS Item Add On' does not exist yet.",
		)
		return

	unknown_codes = []
	conflicts = []
	per_item_errors = []
	migrated_count = 0

	menu_items = frappe.get_all(
		"NDS Menu Item",
		fields=["name", "item", "variants", "addons"],
		filters={"parenttype": "NDS Menu"},
	)

	item_variants = {}
	item_addons = {}

	for menu_item in menu_items:
		item_code = menu_item.item
		if not item_code:
			continue

		if menu_item.variants:
			variants = _parse_codes(menu_item.variants)
			valid_variants = []
			for v in variants:
				if frappe.db.exists("Item", v):
					valid_variants.append(v)
				else:
					unknown_codes.append(
						{
							"menu_item": menu_item.name,
							"item": item_code,
							"type": "variant",
							"code": v,
						}
					)

			item_variants.setdefault(item_code, set())
			old_variants = item_variants[item_code]
			new_variants = set(valid_variants)
			if old_variants and old_variants != new_variants:
				conflicts.append(
					{
						"item": item_code,
						"type": "variant",
						"old": sorted(old_variants),
						"new": sorted(new_variants),
					}
				)
			item_variants[item_code].update(valid_variants)

		if menu_item.addons:
			addons = _parse_codes(menu_item.addons)
			valid_addons = []
			for a in addons:
				if frappe.db.exists("Item", a):
					valid_addons.append(a)
				else:
					unknown_codes.append(
						{
							"menu_item": menu_item.name,
							"item": item_code,
							"type": "addon",
							"code": a,
						}
					)

			item_addons.setdefault(item_code, set())
			old_addons = item_addons[item_code]
			new_addons = set(valid_addons)
			if old_addons and old_addons != new_addons:
				conflicts.append(
					{
						"item": item_code,
						"type": "addon",
						"old": sorted(old_addons),
						"new": sorted(new_addons),
					}
				)
			item_addons[item_code].update(valid_addons)

	all_items = set(item_variants.keys()) | set(item_addons.keys())
	for item_code in all_items:
		if not frappe.db.exists("Item", item_code):
			continue

		try:
			variants = item_variants.get(item_code, set())
			addons = item_addons.get(item_code, set())
			added = 0
			added += _insert_child_rows(
				item_code,
				"NDS POS Item Variant",
				"custom_pos_item_variants",
				variants,
				skip_self=True,
			)
			added += _insert_child_rows(
				item_code,
				"NDS Item Add On",
				"custom_pos_add_on_items",
				addons,
				skip_self=False,
			)
			if added:
				migrated_count += 1
		except Exception as e:
			per_item_errors.append(f"Item {item_code}: {e!s}")
			frappe.log_error(title="NDS variant migration item error", message=per_item_errors[-1])

	_log_migration_summary(unknown_codes, conflicts, per_item_errors)
	print(f"Variant migration complete: {migrated_count} items updated")


def _insert_child_rows(parent_item, child_doctype, parentfield, codes, skip_self=False):
	existing = set(
		frappe.db.sql_list(
			f"""
			SELECT item FROM `tab{child_doctype}`
			WHERE parent = %s AND parenttype = 'Item' AND parentfield = %s
			""",
			(parent_item, parentfield),
		)
	)

	max_idx = frappe.db.sql(
		f"""
		SELECT COALESCE(MAX(idx), 0) FROM `tab{child_doctype}`
		WHERE parent = %s AND parenttype = 'Item' AND parentfield = %s
		""",
		(parent_item, parentfield),
	)[0][0]

	added = 0
	idx = int(max_idx or 0)
	for code in sorted(codes):
		if skip_self and code == parent_item:
			continue
		if not code or code in existing:
			continue
		if not frappe.db.exists("Item", code):
			continue

		idx += 1
		item_name = frappe.db.get_value("Item", code, "item_name") or code
		row = frappe.get_doc(
			{
				"doctype": child_doctype,
				"parent": parent_item,
				"parenttype": "Item",
				"parentfield": parentfield,
				"idx": idx,
				"item": code,
				"item_name": item_name,
			}
		)
		row.db_insert()
		existing.add(code)
		added += 1

	return added


def _log_migration_summary(unknown_codes, conflicts, per_item_errors):
	if not (unknown_codes or conflicts or per_item_errors):
		return

	message = []

	if unknown_codes:
		message.append("Unknown item codes (not in Item master):")
		for uc in unknown_codes[:50]:
			message.append(
				f"  {uc['type']}: {uc['code']} in menu item {uc['menu_item']} (parent {uc['item']})"
			)
		if len(unknown_codes) > 50:
			message.append(f"  ... and {len(unknown_codes) - 50} more")

	if conflicts:
		message.append("\nCross-menu conflicts (different menus had different values, using union):")
		for conf in conflicts[:20]:
			message.append(f"  Item {conf['item']} {conf['type']}: {conf['old']} vs {conf['new']}")
		if len(conflicts) > 20:
			message.append(f"  ... and {len(conflicts) - 20} more")

	if per_item_errors:
		message.append("\nPer-item errors (other items still migrated):")
		for err in per_item_errors[:30]:
			message.append(f"  {err}")
		if len(per_item_errors) > 30:
			message.append(f"  ... and {len(per_item_errors) - 30} more")

	frappe.log_error(title="NDS variant migration", message="\n".join(message))


def _parse_codes(text):
	if not text:
		return []
	return [code.strip() for code in text.split(",") if code.strip()]
