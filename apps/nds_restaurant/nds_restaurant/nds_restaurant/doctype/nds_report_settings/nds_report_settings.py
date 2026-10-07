# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document


class NDSReportSettings(Document):
	def validate(self):
		"""Validate NDS Report Settings."""
		# P9-T1: Validate no_of_hours between 0 and 12
		if self.extended_hours and self.no_of_hours:
			hours = int(self.no_of_hours or 0)
			if hours < 0 or hours > 12:
				frappe.throw(_("No Of Hours must be between 0 and 12"))
