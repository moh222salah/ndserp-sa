import frappe
from frappe import _
from frappe.model.document import Document
from contracting.services.variation_engine import recompute_project


class ContractVariation(Document):
	def validate(self):
		total = 0.0
		for row in self.items:
			row.variation_amount = (row.variation_qty or 0) * (row.variation_rate or 0)
			total += row.variation_amount or 0
		self.variation_value = total

	def on_update(self):
		recompute_project(self.project)

	def on_cancel(self):
		recompute_project(self.project)

	def on_trash(self):
		recompute_project(self.project)
