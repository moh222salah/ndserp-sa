"""
Item validation hooks for NDS Restaurant.
P3-T3: Validate that variants and add-ons are in menus.
"""

import frappe
from frappe import _


def validate_item_links(doc, method=None):
	"""
	Item validate hook: when an Item's variants or add-ons change,
	validate that they are in every enabled NDS Menu that contains this item.
	
	Guards against missing custom fields (pre-migration).
	"""
	meta = frappe.get_meta("Item")
	if not meta.has_field("custom_pos_item_variants"):
		return
	
	if not meta.has_field("custom_pos_add_on_items"):
		return

	variant_codes = {row.item for row in doc.get("custom_pos_item_variants", []) if row.item}
	addon_codes = {row.item for row in doc.get("custom_pos_add_on_items", []) if row.item}

	if doc.name in variant_codes:
		frappe.throw(_("Item {0} cannot be its own variant").format(frappe.bold(doc.name)))

	if doc.name in addon_codes:
		frappe.throw(_("Item {0} cannot be its own add-on").format(frappe.bold(doc.name)))

	# Get all enabled NDS Menus that contain this item
	menus = frappe.db.sql("""
		SELECT DISTINCT mi.parent
		FROM `tabNDS Menu Item` mi
		INNER JOIN `tabNDS Menu` m ON m.name = mi.parent
		WHERE mi.item = %s
		  AND mi.parenttype = 'NDS Menu'
		  AND mi.disabled = 0
		  AND m.enabled = 1
	""", (doc.name,), as_dict=True)
	
	if not menus:
		return

	# For each menu, check that all variants and add-ons are enabled rows
	for menu_row in menus:
		menu_name = menu_row.parent
		
		# Get enabled items in this menu
		enabled_items = set(frappe.db.sql_list("""
			SELECT item
			FROM `tabNDS Menu Item`
			WHERE parent = %s
			  AND parenttype = 'NDS Menu'
			  AND disabled = 0
			  AND item IS NOT NULL
		""", (menu_name,)))
		
		# Check variants
		for variant_code in variant_codes:
			if variant_code not in enabled_items:
				frappe.throw(
					_("Variant {0} of {1} is not in menu {2}").format(
						frappe.bold(variant_code),
						frappe.bold(doc.name),
						frappe.bold(menu_name)
					)
				)
		
		# Check add-ons
		for addon_code in addon_codes:
			if addon_code not in enabled_items:
				frappe.throw(
					_("Add-on {0} of {1} is not in menu {2}").format(
						frappe.bold(addon_code),
						frappe.bold(doc.name),
						frappe.bold(menu_name)
					)
				)
