"""Shared helpers for Gas Station script reports."""
import frappe


def base_filters(filters, date_field="start_datetime"):
    filters = frappe._dict(filters or {})
    conds = {}
    if filters.get("station"):
        conds["station"] = filters.station
    if filters.get("from_date") and filters.get("to_date"):
        conds[date_field] = ["between", [filters.from_date, filters.to_date]]
    elif filters.get("from_date"):
        conds[date_field] = [">=", filters.from_date]
    return conds


def col(label, fieldname, fieldtype="Data", width=120, options=None):
    c = {"label": label, "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
    if options:
        c["options"] = options
    return c
