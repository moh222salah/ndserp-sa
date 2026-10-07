"""Coercion helpers — PTS sends numbers as strings sometimes, and not every
sensor reports every value. Missing values stay None (never coerced to 0)."""
import frappe


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def dt(v):
    if not v:
        return None
    try:
        return frappe.utils.get_datetime(v)
    except Exception:
        return None


def s(v):
    return None if v is None else str(v)
