"""
P3: Create Item custom fields for variants and add-ons.
Ensures these fields exist on already-installed sites before migration runs.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Create P3 Item custom fields if they don't exist."""
	custom_fields = {
		"Item": [
			{
				"fieldname": "custom_pos_variants_tab",
				"label": "POS Variants",
				"fieldtype": "Tab Break",
				"insert_after": "website_specifications",
				"module": "NDS Restaurant",
			},
			{
				"fieldname": "custom_pos_item_variants",
				"label": "POS Item Variants",
				"fieldtype": "Table",
				"options": "NDS POS Item Variant",
				"insert_after": "custom_pos_variants_tab",
				"module": "NDS Restaurant",
			},
			{
				"fieldname": "custom_pos_add_on_items",
				"label": "POS Add On Items",
				"fieldtype": "Table",
				"options": "NDS Item Add On",
				"insert_after": "custom_pos_item_variants",
				"module": "NDS Restaurant",
			},
		],
	}
	
	# create_custom_fields will skip fields that already exist
	create_custom_fields(custom_fields, update=True)
	
	print("P3 Item custom fields created/updated")
