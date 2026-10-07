# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _


def execute():
	"""
	P9-T1: Validate that existing NDS Report Settings have a Buying Price List.
	Since buying_price_list is now mandatory, this patch lists any records without one.
	They must be fixed on their next save.
	"""
	settings_list = frappe.get_all(
		"NDS Report Settings",
		filters={"buying_price_list": ["in", [None, ""]]},
		fields=["name", "branch"]
	)
	
	if settings_list:
		branches = ", ".join([s.branch for s in settings_list])
		frappe.log_error(
			title="NDS Report Settings: Missing Buying Price List",
			message=_(
				"The following branches have NDS Report Settings without a Buying Price List: {0}. "
				"The Buying Price List field is now mandatory. Please update these records."
			).format(branches)
		)
		
		frappe.msgprint(
			_(
				"Warning: {0} NDS Report Settings record(s) are missing a Buying Price List. "
				"Branches: {1}. Please update them."
			).format(len(settings_list), branches),
			indicator="orange"
		)
