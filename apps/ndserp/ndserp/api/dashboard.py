"""
Mobile Dashboard API (ERPNext v16).

get_dashboard -> the logged-in user's figures for a period (posting date between from_date and to_date):
                 net sales, number of invoices, total of Pay payment entries and the amount per mode of payment.
                 Only SUBMITTED documents created by the user count; amounts are in company currency.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate

from ndserp.api.sales_invoice import APIError, _get_user_context, _handle


@frappe.whitelist(methods=["GET"])
def get_dashboard(from_date=None, to_date=None):
	"""
	net_sales       -> sum of invoice net totals (before VAT); returns are negative, so this is net of returns.
	invoice_count   -> number of regular invoices (returns not counted).
	pay_total       -> sum of Pay payment entries (refunds / money paid out).
	modes_of_payment-> per mode: received (Receive payment entries + payments on invoices),
	                   paid (Pay payment entries + refunds on return invoices) and net = received - paid.
	"""

	def run():
		start, end = _parse_period(from_date, to_date)
		ctx = _get_user_context()
		user = frappe.session.user
		args = {"user": user, "start": start, "end": end}

		sales = frappe.db.sql(
			"""
			select
				ifnull(sum(base_net_total), 0) as net_sales,
				ifnull(sum(case when is_return = 0 then 1 else 0 end), 0) as invoice_count
			from `tabSales Invoice`
			where owner = %(user)s and docstatus = 1 and posting_date between %(start)s and %(end)s
			""",
			args,
			as_dict=True,
		)[0]

		received, paid = defaultdict(float), defaultdict(float)
		pay_total = 0.0
		for mode, payment_type, amount in frappe.db.sql(
			"""
			select mode_of_payment, payment_type, sum(base_paid_amount)
			from `tabPayment Entry`
			where owner = %(user)s and docstatus = 1 and payment_type in ('Receive', 'Pay')
				and posting_date between %(start)s and %(end)s
			group by mode_of_payment, payment_type
			""",
			args,
		):
			if payment_type == "Receive":
				received[mode] += flt(amount)
			else:
				paid[mode] += flt(amount)
				pay_total += flt(amount)

		# Payments taken on the invoice itself (POS); negative on return invoices = refunded
		for mode, amount in frappe.db.sql(
			"""
			select sip.mode_of_payment, sum(sip.base_amount)
			from `tabSales Invoice Payment` sip
			inner join `tabSales Invoice` si on si.name = sip.parent
			where si.owner = %(user)s and si.docstatus = 1 and si.is_pos = 1
				and si.posting_date between %(start)s and %(end)s
			group by sip.mode_of_payment, sign(sip.base_amount)
			""",
			args,
		):
			if flt(amount) >= 0:
				received[mode] += flt(amount)
			else:
				paid[mode] += abs(flt(amount))

		modes = [
			{
				"mode_of_payment": mode,
				"received": flt(received.get(mode), 2),
				"paid": flt(paid.get(mode), 2),
				"net": flt(flt(received.get(mode)) - flt(paid.get(mode)), 2),
			}
			for mode in sorted(set(received) | set(paid), key=lambda m: m or "")
		]

		frappe.clear_messages()
		return {
			"success": True,
			"data": {
				"from_date": str(start),
				"to_date": str(end),
				"currency": frappe.get_cached_value("Company", ctx.company, "default_currency"),
				"net_sales": flt(sales.net_sales, 2),
				"invoice_count": int(sales.invoice_count),
				"pay_total": flt(pay_total, 2),
				"modes_of_payment": modes,
			},
		}

	return _handle(run)


def _parse_period(from_date, to_date):
	errors, dates = [], {}
	for field, value in (("from_date", from_date), ("to_date", to_date)):
		if not value:
			errors.append(f"{field} is required ('YYYY-MM-DD')")
			continue
		try:
			dates[field] = getdate(value)
		except Exception:
			errors.append(f"{field} must be 'YYYY-MM-DD'")
	if len(dates) == 2 and dates["from_date"] > dates["to_date"]:
		errors.append("from_date must be on or before to_date")
	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)
	return dates["from_date"], dates["to_date"]
