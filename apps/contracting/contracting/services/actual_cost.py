"""Actual cost aggregation (no allocation document — read from posted ERPNext docs).

Reads construction cost dimensions (ct_cost_code / ct_wbs / ct_boq_item) that the
app adds to the source documents, aggregated by Project. Each source is queried
independently and guarded, so a missing custom field on one doctype never breaks
the whole report.

Subcontract IPC is intentionally NOT summed here: its economic cost lands as a
Purchase Invoice, which IS summed — summing both would double-count.
"""
import frappe


def _q(sql, params):
	try:
		return frappe.db.sql(sql, params, as_dict=True)
	except Exception:
		return []


def actual_by(project, dim):
	"""dim: 'cost_code' or 'boq_item'. Returns {dimension_value: amount}."""
	col = "ct_" + dim
	agg = {}

	def add(rows):
		for r in rows:
			k = r.get("k")
			if k:
				agg[k] = agg.get(k, 0) + (r.get("amt") or 0)

	add(_q(f"""select pii.{col} as k, sum(pii.net_amount) as amt
		from `tabPurchase Invoice Item` pii
		inner join `tabPurchase Invoice` pi on pii.parent = pi.name
		where pi.docstatus = 1 and pii.project = %s and pii.{col} is not null
		group by pii.{col}""", (project,)))

	add(_q(f"""select ja.{col} as k, sum(ja.debit) as amt
		from `tabJournal Entry Account` ja
		inner join `tabJournal Entry` je on ja.parent = je.name
		where je.docstatus = 1 and ja.project = %s and ja.{col} is not null
		group by ja.{col}""", (project,)))

	add(_q(f"""select ec.{col} as k, sum(ec.total_sanctioned_amount) as amt
		from `tabExpense Claim` ec
		where ec.docstatus = 1 and ec.project = %s and ec.{col} is not null
		group by ec.{col}""", (project,)))

	add(_q(f"""select sed.{col} as k, sum(sed.amount) as amt
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on sed.parent = se.name
		where se.docstatus = 1 and se.project = %s and sed.{col} is not null
		group by sed.{col}""", (project,)))

	add(_q(f"""select ss.{col} as k, sum(ss.net_pay) as amt
		from `tabSalary Slip` ss
		where ss.docstatus = 1 and ss.project = %s and ss.{col} is not null
		group by ss.{col}""", (project,)))

	return agg
