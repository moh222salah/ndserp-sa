# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document


class NDSMenu(Document):
	def before_save(self):
		if not self.price_list:
			self.ensure_price_list()
		self.sync_item_prices()
	
	def validate(self):
		"""P3-T3: Validate that variants and add-ons are in the menu."""
		self.validate_variants_and_addons()

	def ensure_price_list(self):
		pl_name = f"NDS-{self.name}"
		if not frappe.db.exists("Price List", pl_name):
			pl = frappe.get_doc({
				"doctype": "Price List",
				"price_list_name": pl_name,
				"selling": 1,
				"buying": 0,
				"enabled": 1,
				"currency": frappe.db.get_default("currency") or "USD",
			})
			pl.insert(ignore_permissions=True)
		self.price_list = pl_name

	def sync_item_prices(self):
		if not self.price_list:
			return
		for row in self.items or []:
			if not row.item or row.rate is None:
				continue
			existing = frappe.db.get_value(
				"Item Price",
				{"item_code": row.item, "price_list": self.price_list, "selling": 1},
				"name",
			)
			if existing:
				frappe.db.set_value("Item Price", existing, "price_list_rate", row.rate)
			else:
				frappe.get_doc({
					"doctype": "Item Price",
					"item_code": row.item,
					"price_list": self.price_list,
					"selling": 1,
					"price_list_rate": row.rate,
				}).insert(ignore_permissions=True)
	
	def validate_variants_and_addons(self):
		"""
		P3-T3: For each enabled menu row, validate that all variants and add-ons
		of that item are also enabled rows in this menu.
		"""
		if not self.enabled:
			return
		
		# Build a set of enabled item codes in this menu
		enabled_items = set()
		for row in self.items or []:
			if not row.disabled and row.item:
				enabled_items.add(row.item)
		
		# Check each row's variants and add-ons
		for row in self.items or []:
			if row.disabled or not row.item:
				continue
			
			# Get the Item's variants and add-ons from custom fields
			if not frappe.db.exists("Item", row.item):
				continue
			
			# Only check if Item has the custom fields (guard against pre-migration)
			meta = frappe.get_meta("Item")
			if not meta.has_field("custom_pos_item_variants"):
				continue
			
			item_doc = frappe.get_doc("Item", row.item)
			
			# Validate variants
			for variant_row in item_doc.get("custom_pos_item_variants", []):
				variant_code = variant_row.item
				if variant_code == row.item:
					frappe.throw(
						_("Item {0} cannot be its own variant").format(
							frappe.bold(row.item)
						)
					)
				if variant_code and variant_code not in enabled_items:
					frappe.throw(
						_("Variant {0} of item {1} is not in menu {2}").format(
							frappe.bold(variant_code),
							frappe.bold(row.item),
							frappe.bold(self.name)
						)
					)
			
			# Validate add-ons
			for addon_row in item_doc.get("custom_pos_add_on_items", []):
				addon_code = addon_row.item
				if addon_code == row.item:
					frappe.throw(
						_("Item {0} cannot be its own add-on").format(
							frappe.bold(row.item)
						)
					)
				if addon_code and addon_code not in enabled_items:
					frappe.throw(
						_("Add-on {0} of item {1} is not in menu {2}").format(
							frappe.bold(addon_code),
							frappe.bold(row.item),
							frappe.bold(self.name)
						)
					)
