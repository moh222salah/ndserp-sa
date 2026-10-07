# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.model.document import Document


class NDSRestaurant(Document):
	def validate(self):
		if self.default_room and not frappe.db.exists("NDS Room", self.default_room):
			frappe.throw(frappe._("Default Room {0} does not exist").format(self.default_room))
