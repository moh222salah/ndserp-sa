# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.model.document import Document


class NDSTable(Document):
	def validate(self):
		if self.restaurant:
			branch = frappe.db.get_value("NDS Restaurant", self.restaurant, "branch")
			if branch:
				self.branch = branch
