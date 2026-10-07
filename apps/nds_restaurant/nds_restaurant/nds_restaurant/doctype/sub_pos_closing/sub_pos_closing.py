# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


class SubPOSClosing(Document):
	def validate(self):
		if not self.pos_opening_entry:
			frappe.throw(frappe._("POS Opening Entry is required"))
		opening = frappe.get_doc("POS Opening Entry", self.pos_opening_entry)
		self.user = opening.user
		self.company = opening.company
		self.pos_profile = opening.pos_profile
		self.period_start_date = opening.period_start_date
		if not self.period_end_date:
			self.period_end_date = now_datetime()
		self.load_transactions()

	def load_transactions(self):
		invoices = frappe.get_all(
			"POS Invoice",
			filters={
				"owner": self.user,
				"pos_profile": self.pos_profile,
				"docstatus": 1,
				"posting_date": [">=", str(self.period_start_date)[:10]],
			},
			fields=["name", "posting_date", "grand_total", "customer", "net_total", "total_qty", "docstatus", "status"],
		)
		drafts = frappe.get_all(
			"POS Invoice",
			filters={"owner": self.user, "pos_profile": self.pos_profile, "docstatus": 0},
			pluck="name",
		)
		if drafts:
			frappe.throw(frappe._("Submit/Delete Draft Invoices: {0}").format(", ".join(drafts)))
		self.pos_transactions = []
		grand = net = qty = 0
		for inv in invoices:
			self.append("pos_transactions", {
				"pos_invoice": inv.name,
				"posting_date": inv.posting_date,
				"grand_total": inv.grand_total,
				"customer": inv.customer,
			})
			grand += flt(inv.grand_total)
			net += flt(inv.net_total)
			qty += flt(inv.total_qty)
		self.grand_total = grand
		self.net_total = net
		self.total_quantity = qty
