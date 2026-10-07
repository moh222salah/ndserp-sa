"""Shared IPC valuation engine (Client IPC + Subcontract IPC).

ASSUMED STANDARD MODEL — see ASSUMPTIONS.md. Every line here is an industry-
standard interim-payment-certificate calculation adopted in the absence of the
confirmed legacy formula. Correct any line here and both IPC types update.

Order of application (adopted):
    work_done   = Σ (current_qty × unit_price)
    storage     = Σ storage_value                 # materials on site: ADDS
    gross_val   = work_done + storage
    − temporary deductions (item level)
    − item deductions (item level)
    − header deductions (percentage → on gross_val, else entered)
    = subtotal
    − retention%        × work_done               # on work done
    − advance recovery% × work_done
    − insurance%        × work_done
    = net_before_tax
    + output_tax%       × net_before_tax          # VAT: ADDS
    − withholding_tax%  × net_before_tax          # WHT: DEDUCTS
    = net_current
Previous/Total come from prior Approved/Posted certificates of the same
contract/subcontract; a single certificate never overwrites cumulative history.
"""
import frappe

_APPROVED = ("Approved", "Posted")


def _prev_item(item_table, boq_field, boq_value, exclude_parent):
	if not boq_value:
		return 0.0, 0.0
	row = frappe.db.sql(
		f"""
		select coalesce(sum(it.current_qty), 0), coalesce(sum(it.current_value), 0)
		from `tab{item_table}` it
		inner join `tab{item_table.replace(' Item', '')}` hd on it.parent = hd.name
		where it.`{boq_field}` = %s and hd.status in %s and hd.name != %s
		""", (boq_value, _APPROVED, exclude_parent or ""))[0]
	return float(row[0] or 0), float(row[1] or 0)


def _prev_net(parent_table, scope_field, scope_value, exclude_name):
	if not scope_value:
		return 0.0
	return float(frappe.db.sql(
		f"""
		select coalesce(sum(net_current), 0) from `tab{parent_table}`
		where `{scope_field}` = %s and status in %s and name != %s
		""", (scope_value, _APPROVED, exclude_name or ""))[0][0] or 0)


def compute_ipc(doc, *, item_table, parent_table, boq_field, scope_field, scope_value):
	work_done = storage = temp = item_ded = 0.0

	for row in doc.items:
		row.current_value = (row.current_qty or 0) * (row.unit_price or 0)
		pq, pv = _prev_item(item_table, boq_field, row.get(boq_field), doc.name)
		row.previous_qty, row.previous_value = pq, pv
		row.total_qty = pq + (row.current_qty or 0)
		row.total_value = pv + row.current_value
		row.net_value = (row.current_value + (row.storage_value or 0)
						 - (row.temporary_deduction_value or 0)
						 - (row.item_deduction_value or 0))
		work_done += row.current_value
		storage += row.storage_value or 0
		temp += row.temporary_deduction_value or 0
		item_ded += row.item_deduction_value or 0

	gross_val = work_done + storage

	hdr_ded = 0.0
	for d in doc.header_deductions:
		if d.percentage:
			d.current_value = gross_val * (d.percentage or 0) / 100.0
		hdr_ded += d.current_value or 0

	subtotal = gross_val - temp - item_ded - hdr_ded
	retention = work_done * (doc.retention_percent or 0) / 100.0
	advance = work_done * (doc.advance_recovery_percent or 0) / 100.0
	insurance = work_done * (doc.insurance_percent or 0) / 100.0
	net_before_tax = subtotal - retention - advance - insurance
	output_tax = net_before_tax * (doc.output_tax_percent or 0) / 100.0
	withholding = net_before_tax * (doc.withholding_tax_percent or 0) / 100.0
	net_current = net_before_tax + output_tax - withholding

	doc.gross_work_done = work_done
	doc.storage_total = storage
	doc.gross_valuation = gross_val
	doc.temporary_deductions_total = temp
	doc.item_deductions_total = item_ded
	doc.header_deductions_total = hdr_ded
	doc.retention_current = retention
	doc.advance_recovery_current = advance
	doc.insurance_current = insurance
	doc.output_tax_amount = output_tax
	doc.withholding_tax_amount = withholding
	doc.net_current = net_current

	prev_net = _prev_net(parent_table, scope_field, scope_value, doc.name)
	doc.previous_net = prev_net
	doc.total_net = prev_net + net_current
