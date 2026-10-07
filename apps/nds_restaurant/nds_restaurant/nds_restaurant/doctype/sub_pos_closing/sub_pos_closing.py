# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


class SubPOSClosing(Document):
	def validate(self):
		if not self.pos_opening_entry:
			frappe.throw(frappe._("POS Opening Entry is required"))
		from nds_restaurant.api.shift import sub_period_start

		opening = frappe.get_doc("POS Opening Entry", self.pos_opening_entry)
		# P7-T5: a sub-cashier closes on the main cashier's opening (ERPNext v16 allows one open
		# opening per profile); without a user it is the opening's own cashier as before
		self.user = self.user or opening.user
		self.company = opening.company
		self.pos_profile = opening.pos_profile
		if self.user == opening.user:
			self.period_start_date = opening.period_start_date
		else:
			self.period_start_date = sub_period_start(opening.name, self.user, exclude=self.name)
		if not self.period_end_date:
			self.period_end_date = now_datetime()
		self.load_transactions()

	def load_transactions(self):
		"""P7-T1: invoices this cashier took payment for; P7-T4: reconciliation per mode of payment."""
		from nds_restaurant.api.shift import cashier_drafts, cashier_invoices, payment_reconciliation

		drafts = cashier_drafts(self.user, self.pos_profile)
		if drafts:
			frappe.throw(frappe._("Submit/Delete Draft Invoices: {0}").format(", ".join(drafts)))
		invoices = cashier_invoices(self.user, self.pos_profile, self.period_start_date)
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

		entered = {
			row.mode_of_payment: row.closing_amount
			for row in (self.get("payment_reconciliation") or [])
			if row.mode_of_payment and row.closing_amount is not None
		}
		self.set("payment_reconciliation", [])
		own = self.user == frappe.db.get_value("POS Opening Entry", self.pos_opening_entry, "user")
		for row in payment_reconciliation(
			self.pos_opening_entry, [i.name for i in invoices], entered, include_opening=own
		):
			self.append("payment_reconciliation", row)
