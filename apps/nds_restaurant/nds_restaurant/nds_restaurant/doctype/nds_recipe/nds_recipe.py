# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.model.document import Document


class NDSRecipe(Document):
	def validate(self):
		if not self.ingredients:
			frappe.throw(frappe._("Add at least one ingredient"))
		for row in self.ingredients:
			if not frappe.db.get_value("Item", row.ingredient, "is_stock_item"):
				frappe.throw(
					frappe._("Ingredient {0} must have Maintain Stock checked").format(row.ingredient)
				)
