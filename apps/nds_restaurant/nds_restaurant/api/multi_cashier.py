# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _


def validate_pos_opening(doc, method=None):
	# P7-T3: the daily-close rule applies with or without multi-cashier mode
	from nds_restaurant.api.shift import assert_previous_day_closed

	assert_previous_day_closed(doc.pos_profile, exclude=doc.name if not doc.is_new() else None)

	profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	if not profile.get("custom_enable_multiple_cashier"):
		return

	main_users = [
		row.user
		for row in profile.applicable_for_users
		if row.get("custom_main_cashier")
	]
	if not main_users:
		return

	is_main = doc.user in main_users
	open_main = frappe.db.exists(
		"POS Opening Entry",
		{
			"pos_profile": doc.pos_profile,
			"status": "Open",
			"docstatus": 1,
			"user": ["in", main_users],
		},
	)
	if not is_main and not open_main:
		frappe.throw(_("Main cashier must open POS before sub-cashiers"))


def validate_pos_closing(doc, method=None):
	profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	if not profile.get("custom_enable_multiple_cashier"):
		return

	main_users = [
		row.user
		for row in profile.applicable_for_users
		if row.get("custom_main_cashier")
	]
	if doc.user not in main_users:
		return

	# Ensure all sub cashiers have submitted Sub POS Closing
	openings = frappe.get_all(
		"POS Opening Entry",
		filters={
			"pos_profile": doc.pos_profile,
			"status": "Open",
			"docstatus": 1,
			"user": ["not in", main_users],
		},
		fields=["name", "user"],
	)
	for op in openings:
		closed = frappe.db.exists(
			"Sub POS Closing",
			{"pos_opening_entry": op.name, "docstatus": 1},
		)
		if not closed:
			frappe.throw(
				_("Sub cashier {0} must submit Sub POS Closing before final close").format(op.user)
			)

	# P7-T5: sub-cashiers working on the main cashier's opening close with a Sub POS Closing
	from nds_restaurant.api.shift import unclosed_sub_cashiers

	if doc.pos_opening_entry:
		pending = unclosed_sub_cashiers(doc.pos_opening_entry, doc.pos_profile, main_users)
		if pending:
			frappe.throw(
				_("Sub cashier {0} must submit Sub POS Closing before final close").format(", ".join(pending))
			)
