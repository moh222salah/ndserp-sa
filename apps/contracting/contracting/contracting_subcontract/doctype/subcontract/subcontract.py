import frappe
from frappe import _
from frappe.model.document import Document
from contracting.services.subcontract_engine import recompute_subcontract

APPROVED_STATES = ("Approved", "Active", "Suspended", "Completed", "Closed")


class Subcontract(Document):
	def validate(self):
		if self.start_date and self.end_date and self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date."))
		if self.exchange_rate is not None and self.exchange_rate <= 0:
			frappe.throw(_("Exchange Rate must be greater than zero."))
		before = self.get_doc_before_save()
		if before and before.status in APPROVED_STATES and \
				(before.original_value or 0) != (self.original_value or 0):
			frappe.throw(_("Original Value is immutable once the subcontract is approved."))

	def on_update(self):
		recompute_subcontract(self.name)
