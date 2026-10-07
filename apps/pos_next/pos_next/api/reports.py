# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def _validate_pos_profile_access(pos_profile: str) -> None:
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	if not frappe.db.exists("POS Profile", pos_profile):
		frappe.throw(_("POS Profile {0} does not exist").format(pos_profile))

	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user},
	)

	if not has_access and not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))


def _resolve_period(
	period: str,
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
) -> Tuple[str, str, str]:
	"""Return (from_date, to_date, label) for the requested period."""
	today = getdate(nowdate())
	period = (period or "session").lower().strip()

	if period == "yesterday":
		yesterday = today - timedelta(days=1)
		return str(yesterday), str(yesterday), _("Yesterday")

	if period == "week":
		start = today - timedelta(days=today.weekday())
		return str(start), str(today), _("This Week")

	if period == "month":
		start = today.replace(day=1)
		return str(start), str(today), _("This Month")

	if period == "custom":
		if not from_date or not to_date:
			frappe.throw(_("From Date and To Date are required for custom period"))
		start = getdate(from_date)
		end = getdate(to_date)
		if start > end:
			frappe.throw(_("From Date cannot be after To Date"))
		return str(start), str(end), _("Custom Range")

	if period == "session":
		return "", "", _("Current Shift")

	frappe.throw(_("Invalid period: {0}").format(period))


def _build_invoice_filters(
	pos_profile: str,
	from_date: str,
	to_date: str,
	pos_opening_shift: Optional[str] = None,
	use_shift: bool = False,
	shift_start: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
	params: Dict[str, Any] = {"pos_profile": pos_profile}

	if use_shift:
		if not pos_opening_shift:
			frappe.throw(_("No open shift found for session report"))

		params["pos_opening_shift"] = pos_opening_shift
		conditions = [
			"si.pos_profile = %(pos_profile)s",
			"si.docstatus = 1",
			"si.is_pos = 1",
			"""(
				si.posa_pos_opening_shift = %(pos_opening_shift)s
				OR (
					si.is_return = 1
					AND IFNULL(si.posa_pos_opening_shift, '') = ''
					AND TIMESTAMP(si.posting_date, si.posting_time) >= %(shift_start)s
				)
			)""",
		]
		params["shift_start"] = shift_start or frappe.db.get_value(
			"POS Opening Shift", pos_opening_shift, "period_start_date"
		)
	else:
		conditions = [
			"si.pos_profile = %(pos_profile)s",
			"si.docstatus = 1",
			"si.is_pos = 1",
			"si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
		]
		params["from_date"] = from_date
		params["to_date"] = to_date

	return " AND ".join(conditions), params


def _get_summary(where_clause: str, params: Dict[str, Any]) -> Dict[str, Any]:
	summary = frappe.db.sql(
		f"""
		SELECT
			SUM(CASE WHEN si.is_return = 0 THEN 1 ELSE 0 END) AS sales_count,
			SUM(CASE WHEN si.is_return = 0 THEN si.grand_total ELSE 0 END) AS sales_total,
			SUM(CASE WHEN si.is_return = 1 THEN 1 ELSE 0 END) AS returns_count,
			SUM(CASE WHEN si.is_return = 1 THEN ABS(si.grand_total) ELSE 0 END) AS returns_total,
			SUM(si.grand_total) AS net_total,
			SUM(CASE WHEN si.is_return = 0 THEN si.total_qty ELSE 0 END) AS items_sold,
			SUM(CASE WHEN si.is_return = 1 THEN ABS(si.total_qty) ELSE 0 END) AS items_returned
		FROM `tabSales Invoice` si
		WHERE {where_clause}
		""",
		params,
		as_dict=True,
	)[0]

	return {
		"sales_count": int(summary.get("sales_count") or 0),
		"sales_total": flt(summary.get("sales_total")),
		"returns_count": int(summary.get("returns_count") or 0),
		"returns_total": flt(summary.get("returns_total")),
		"net_total": flt(summary.get("net_total")),
		"items_sold": flt(summary.get("items_sold")),
		"items_returned": flt(summary.get("items_returned")),
	}


def _get_payment_breakdown(where_clause: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
	return frappe.db.sql(
		f"""
		SELECT
			sip.mode_of_payment,
			SUM(sip.amount) AS amount
		FROM `tabSales Invoice Payment` sip
		INNER JOIN `tabSales Invoice` si ON sip.parent = si.name
		WHERE {where_clause}
		GROUP BY sip.mode_of_payment
		ORDER BY amount DESC
		""",
		params,
		as_dict=True,
	)


def _get_returns(where_clause: str, params: Dict[str, Any], limit: int = 0) -> List[Dict[str, Any]]:
	limit_clause = ""
	query_params = dict(params)
	if limit and limit > 0:
		limit_clause = "LIMIT %(limit)s"
		query_params["limit"] = limit

	return frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.customer,
			si.customer_name,
			si.posting_date,
			si.posting_time,
			si.grand_total,
			si.return_against
		FROM `tabSales Invoice` si
		WHERE {where_clause}
			AND si.is_return = 1
		ORDER BY si.posting_date DESC, si.posting_time DESC
		{limit_clause}
		""",
		query_params,
		as_dict=True,
	)


def _get_recent_invoices(where_clause: str, params: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
	params = {**params, "limit": limit}
	return frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.customer,
			si.customer_name,
			si.posting_date,
			si.posting_time,
			si.grand_total,
			si.is_return,
			si.return_against
		FROM `tabSales Invoice` si
		WHERE {where_clause}
		ORDER BY si.posting_date DESC, si.posting_time DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)


@frappe.whitelist()
def get_sales_report(
	pos_profile: str,
	period: str = "session",
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
	pos_opening_shift: Optional[str] = None,
):
	"""
	Get POS sales report for a profile and time period.

	Periods:
	- session: current open shift (requires pos_opening_shift)
	- yesterday: previous calendar day
	- week: current calendar week (Mon–today)
	- month: current calendar month
	- custom: requires from_date and to_date
	"""
	_validate_pos_profile_access(pos_profile)

	resolved_from, resolved_to, period_label = _resolve_period(period, from_date, to_date)
	use_shift = period.lower().strip() == "session"

	if use_shift and not pos_opening_shift:
		return {
			"period": period,
			"period_label": period_label,
			"from_date": None,
			"to_date": None,
			"has_open_shift": False,
			"summary": {
				"sales_count": 0,
				"sales_total": 0,
				"returns_count": 0,
				"returns_total": 0,
				"net_total": 0,
				"items_sold": 0,
				"items_returned": 0,
			},
			"payment_breakdown": [],
			"returns": [],
			"recent_invoices": [],
		}

	shift_start = None
	if use_shift and pos_opening_shift:
		shift_start = frappe.db.get_value(
			"POS Opening Shift", pos_opening_shift, "period_start_date"
		)

	where_clause, params = _build_invoice_filters(
		pos_profile,
		resolved_from,
		resolved_to,
		pos_opening_shift=pos_opening_shift,
		use_shift=use_shift,
		shift_start=shift_start,
	)

	return {
		"period": period,
		"period_label": period_label,
		"from_date": str(shift_start) if use_shift and shift_start else resolved_from or None,
		"to_date": str(nowdate()) if use_shift else resolved_to or None,
		"has_open_shift": bool(use_shift and pos_opening_shift),
		"pos_opening_shift": pos_opening_shift if use_shift else None,
		"summary": _get_summary(where_clause, params),
		"payment_breakdown": _get_payment_breakdown(where_clause, params),
		"returns": _get_returns(where_clause, params),
		"recent_invoices": _get_recent_invoices(where_clause, params),
	}
