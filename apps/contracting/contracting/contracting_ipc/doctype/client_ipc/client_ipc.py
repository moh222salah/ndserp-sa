import frappe
from frappe import _
from frappe.model.document import Document
from contracting.services.ipc_valuation_service import compute_ipc


class ClientIPC(Document):
	def validate(self):
		if self.from_date and self.to_date and self.to_date < self.from_date:
			frappe.throw(_("To Date cannot be before From Date."))
		compute_ipc(self, item_table="Client IPC Item", parent_table="Client IPC",
			boq_field="boq_item", scope_field="project", scope_value=self.project)
		self.net_receivable = self.net_current
