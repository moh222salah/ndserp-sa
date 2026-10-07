# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.utils import flt


def execute():
	"""
	Convert legacy burning-materials child rows (cost_per_unit × units_per_day)
	into burning_materials_daily_amount on NDS Report Settings.
	Idempotent: only migrates when legacy child rows still exist.
	"""
	if not frappe.db.table_exists("tabNDS Report Settings"):
		return

	meta = frappe.get_meta("NDS Report Settings")
	if not meta.has_field("burning_materials_daily_amount"):
		return

	for name in frappe.get_all("NDS Report Settings", pluck="name"):
		legacy_total = _legacy_burning_total(name)
		if not legacy_total:
			continue

		current = flt(
			frappe.db.get_value("NDS Report Settings", name, "burning_materials_daily_amount")
		)
		if not current:
			frappe.db.set_value(
				"NDS Report Settings",
				name,
				"burning_materials_daily_amount",
				legacy_total,
				update_modified=False,
			)

		_clear_legacy_burning_rows(name)


def _legacy_burning_total(parent):
	if not frappe.db.table_exists("tabNDS Burning Material"):
		return 0

	rows = frappe.get_all(
		"NDS Burning Material",
		filters={"parent": parent, "parenttype": "NDS Report Settings"},
		fields=["cost_per_unit", "units_per_day"],
	)
	total = 0
	for row in rows:
		total += flt(row.cost_per_unit) * flt(row.units_per_day or 1)
	return total


def _clear_legacy_burning_rows(parent):
	if not frappe.db.table_exists("tabNDS Burning Material"):
		return

	frappe.db.delete(
		"NDS Burning Material",
		{"parent": parent, "parenttype": "NDS Report Settings"},
	)
