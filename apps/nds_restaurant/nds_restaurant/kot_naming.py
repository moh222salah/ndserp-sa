# Copyright (c) 2026, NDS and contributors
# License: MIT

"""NDS KOT naming series helpers (DocType field + Property Setter)."""

import frappe

CNCL_KOT_SERIES = "CNCL-KOT-.#####"
NDS_KOT_DOCTYPE = "NDS KOT"
NAMING_SERIES_FIELD = "naming_series"


def get_kot_naming_series_options():
	"""Return effective naming_series options (property setter overrides DocField)."""
	meta = frappe.get_meta(NDS_KOT_DOCTYPE)
	field = meta.get_field(NAMING_SERIES_FIELD) if meta else None
	options_text = (field.options or "") if field else ""

	ps_value = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": NDS_KOT_DOCTYPE,
			"field_name": NAMING_SERIES_FIELD,
			"property": "options",
		},
		"value",
	)
	if ps_value:
		options_text = ps_value

	return [line.strip() for line in (options_text or "").split("\n") if line.strip()]


def cancellation_kot_naming_series(profile_series):
	"""Pick CNCL series when configured; otherwise fall back to profile series."""
	options = get_kot_naming_series_options()
	if CNCL_KOT_SERIES in options:
		return CNCL_KOT_SERIES
	return profile_series


def ensure_cncl_kot_naming_series_option():
	"""Idempotent: append CNCL-KOT series to Property Setter options when present."""
	if not frappe.db.table_exists("Property Setter"):
		return

	ps_name = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": NDS_KOT_DOCTYPE,
			"field_name": NAMING_SERIES_FIELD,
			"property": "options",
		},
		"name",
	)
	if not ps_name:
		return

	value = frappe.db.get_value("Property Setter", ps_name, "value") or ""
	options = [line.strip() for line in value.split("\n") if line.strip()]
	if CNCL_KOT_SERIES in options:
		return

	options.append(CNCL_KOT_SERIES)
	frappe.db.set_value("Property Setter", ps_name, "value", "\n".join(options))
