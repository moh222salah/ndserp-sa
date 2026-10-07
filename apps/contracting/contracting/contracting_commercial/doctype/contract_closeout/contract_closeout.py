import frappe
from frappe import _
from frappe.model.document import Document

DEFAULT_CHECKLIST = [
	"Final Client IPC approved", "Final variations and claims resolved",
	"Advance / retention / tax reconciled", "Client invoices and payments reconciled",
	"Subcontract final accounts reconciled", "Open commitments reviewed",
	"Actual cost reconciled", "Final Account approved",
]


class ContractCloseout(Document):
	def validate(self):
		if not self.checklist:
			for item in DEFAULT_CHECKLIST:
				self.append("checklist", {"checklist_item": item, "is_mandatory": 1})
		self.can_close = all(c.is_done for c in self.checklist if c.is_mandatory)
		if self.status == "Closed" and not self.can_close:
			frappe.throw(_("All mandatory checklist items must be done before closing."))

	def on_update(self):
		if self.status == "Closed" and self.can_close:
			frappe.db.set_value("Project", self.project, "status", "Completed", update_modified=False)
