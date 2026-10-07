import frappe
from frappe.model.document import Document


class FinalAccount(Document):
	def validate(self):
		self._pull_position()
		if not self.lines:
			self._build_lines()

	def _pull_position(self):
		original = frappe.db.get_value("Project", self.project, "original_contract_value") or 0
		self.original_contract_value = original
		self.approved_variations = frappe.db.sql("""select coalesce(sum(variation_value),0)
			from `tabContract Variation` where project=%s and status='Approved'""", self.project)[0][0] or 0
		self.approved_claims = frappe.db.sql("""select coalesce(sum(approved_amount),0)
			from `tabContract Claim` where project=%s and status='Approved'""", self.project)[0][0] or 0
		self.final_contract_value = ((self.original_contract_value or 0) + (self.approved_variations or 0)
			+ (self.approved_claims or 0) - (self.applicable_deductions or 0))
		self.certified_to_date = frappe.db.sql("""select coalesce(max(total_net),0)
			from `tabClient IPC` where project=%s and status in ('Approved','Posted')""", self.project)[0][0] or 0
		self.retention_held = frappe.db.sql("""select coalesce(sum(retention_current),0)
			from `tabClient IPC` where project=%s and status in ('Approved','Posted')""", self.project)[0][0] or 0
		self.advance_outstanding = frappe.db.sql("""select coalesce(sum(advance_recovery_current),0)
			from `tabClient IPC` where project=%s and status in ('Approved','Posted')""", self.project)[0][0] or 0
		self.outstanding_receivable = (self.final_contract_value or 0) - (self.certified_to_date or 0)

	def _build_lines(self):
		for b in frappe.get_all("Budget BOQ Item", filters={"project": self.project},
				fields=["name", "description", "unit", "quantity", "selling_rate", "selling_amount"]):
			self.append("lines", {"boq_item": b.name, "description": b.description, "unit": b.unit,
				"current_qty": b.quantity, "current_rate": b.selling_rate, "current_amount": b.selling_amount})
