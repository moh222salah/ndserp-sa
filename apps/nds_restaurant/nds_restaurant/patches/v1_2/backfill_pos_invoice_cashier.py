# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe


def execute():
	"""P7-T1: invoices made before the cashier field was filled get Cashier = Owner."""
	if not frappe.get_meta("POS Invoice").has_field("custom_cashier"):
		return
	frappe.db.sql(
		"""UPDATE `tabPOS Invoice` SET custom_cashier = owner
		WHERE IFNULL(custom_cashier, '') = ''"""
	)
