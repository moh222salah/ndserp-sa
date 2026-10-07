#!/usr/bin/env python3
"""
Preview script for P3-T2 variant migration.
Prints the planned changes without writing to the database.

Usage:
  bench --site restaurant.nds-sa.com execute nds_restaurant.scripts.preview_variant_migration.preview
"""

import frappe
from frappe import _


def preview():
	"""
	Preview what the variant migration will do, without making changes.
	"""
	print("\n" + "="*80)
	print("VARIANT MIGRATION PREVIEW")
	print("="*80 + "\n")
	
	# Get all menu items with variants or addons
	menu_items = frappe.get_all(
		"NDS Menu Item",
		fields=["name", "item", "variants", "addons", "parent"],
		filters={"parenttype": "NDS Menu"}
	)
	
	if not menu_items:
		print("No menu items found.\n")
		return
	
	# Group by item
	item_data = {}  # {item_code: {variants: set, addons: set, menus: set}}
	unknown_codes = []
	
	for menu_item in menu_items:
		item_code = menu_item.item
		if not item_code:
			continue
		
		if item_code not in item_data:
			item_data[item_code] = {
				"variants": set(),
				"addons": set(),
				"menus": set()
			}
		
		item_data[item_code]["menus"].add(menu_item.parent)
		
		# Parse variants
		if menu_item.variants:
			variants = _parse_codes(menu_item.variants)
			for v in variants:
				if frappe.db.exists("Item", v):
					item_data[item_code]["variants"].add(v)
				else:
					unknown_codes.append({
						"menu": menu_item.parent,
						"item": item_code,
						"type": "variant",
						"code": v
					})
		
		# Parse add-ons
		if menu_item.addons:
			addons = _parse_codes(menu_item.addons)
			for a in addons:
				if frappe.db.exists("Item", a):
					item_data[item_code]["addons"].add(a)
				else:
					unknown_codes.append({
						"menu": menu_item.parent,
						"item": item_code,
						"type": "addon",
						"code": a
					})
	
	# Print planned changes
	print(f"Found {len(item_data)} unique parent items\n")
	
	for item_code in sorted(item_data.keys()):
		data = item_data[item_code]
		
		if not data["variants"] and not data["addons"]:
			continue
		
		print(f"Item: {item_code}")
		print(f"  Used in menus: {', '.join(sorted(data['menus']))}")
		
		if data["variants"]:
			print(f"  Will add variants: {', '.join(sorted(data['variants']))}")
			# Check if item is its own variant
			if item_code in data["variants"]:
				print(f"    WARNING: Item {item_code} is listed as its own variant!")
		
		if data["addons"]:
			print(f"  Will add add-ons: {', '.join(sorted(data['addons']))}")
		
		print()
	
	# Print unknown codes
	if unknown_codes:
		print("\n" + "-"*80)
		print("UNKNOWN ITEM CODES (will be skipped):")
		print("-"*80 + "\n")
		
		for uc in unknown_codes:
			print(f"  Menu '{uc['menu']}' → Item '{uc['item']}' → {uc['type']} '{uc['code']}'")
		
		print()
	
	# Print conflicts (menus with different values for the same item)
	print("\n" + "-"*80)
	print("CROSS-MENU CONFLICT CHECK:")
	print("-"*80 + "\n")
	
	# Check each menu's values for each item
	conflicts = []
	for item_code in item_data.keys():
		menu_variants = {}  # {menu: set of variant codes}
		menu_addons = {}
		
		for menu_item in menu_items:
			if menu_item.item != item_code:
				continue
			
			menu = menu_item.parent
			
			if menu_item.variants:
				variants = set(_parse_codes(menu_item.variants))
				menu_variants[menu] = variants
			
			if menu_item.addons:
				addons = set(_parse_codes(menu_item.addons))
				menu_addons[menu] = addons
		
		# Check if all menus agree
		if len(menu_variants) > 1:
			variant_sets = list(menu_variants.values())
			if not all(s == variant_sets[0] for s in variant_sets):
				conflicts.append({
					"item": item_code,
					"type": "variants",
					"menus": menu_variants
				})
		
		if len(menu_addons) > 1:
			addon_sets = list(menu_addons.values())
			if not all(s == addon_sets[0] for s in addon_sets):
				conflicts.append({
					"item": item_code,
					"type": "add-ons",
					"menus": menu_addons
				})
	
	if conflicts:
		print("Found conflicts (migration will use union of all values):\n")
		for conf in conflicts:
			print(f"  Item {conf['item']} {conf['type']}:")
			for menu, codes in conf["menus"].items():
				print(f"    {menu}: {', '.join(sorted(codes))}")
			print()
	else:
		print("No conflicts found. All menus agree on variants/add-ons.\n")
	
	print("="*80)
	print("Preview complete. Run migrate to apply these changes.")
	print("="*80 + "\n")


def _parse_codes(text):
	"""Parse comma-separated item codes, trim whitespace."""
	if not text:
		return []
	return [code.strip() for code in text.split(",") if code.strip()]


if __name__ == "__main__":
	frappe.init(site="restaurant.nds-sa.com")
	frappe.connect()
	preview()
	frappe.destroy()
