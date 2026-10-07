import frappe
from frappe import _
from frappe.model.document import Document
from contracting.services.measurement_service import item_value, get_previous


class OperationMeasurement(Document):
	def validate(self):
		if self.from_date and self.to_date and self.to_date < self.from_date:
			frappe.throw(_("To Date cannot be before From Date."))
		self._compute()

	def _compute(self):
		gross = 0.0
		for row in self.items:
			bp = frappe.db.get_value("Budget BOQ Item", row.boq_item,
				["project", "selling_rate", "unit"], as_dict=True)
			if bp and bp.project and bp.project != self.project:
				frappe.throw(_("Row {0}: BOQ Item is not in the selected Project.").format(row.idx))
			if not row.unit_price:
				row.unit_price = (bp and bp.selling_rate) or 0
			row.current_value = item_value(row.qty, row.unit_price)
			pq, pv = get_previous(row.boq_item, self.name)
			row.previous_qty, row.previous_value = pq, pv
			row.total_qty = pq + (row.qty or 0)
			row.total_value = pv + (row.current_value or 0)
			gross += row.current_value or 0
		ded = 0.0
		for d in self.deductions:
			d.amount = (gross * (d.percentage or 0) / 100.0) if d.percentage else (d.amount or 0)
			ded += d.amount or 0
		self.gross_value = gross
		self.total_deductions = ded
		self.net_value = gross - ded
