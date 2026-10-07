import frappe
from frappe import _
from frappe.model.document import Document
from contracting.services.ipc_valuation_service import compute_ipc


class SubcontractIPC(Document):
    def validate(self):
        if self.from_date and self.to_date and self.to_date < self.from_date:
            frappe.throw(_("To Date cannot be before From Date."))
        compute_ipc(self, item_table="Subcontract IPC Item", parent_table="Subcontract IPC",
            boq_field="subcontract_boq_item", scope_field="subcontract", scope_value=self.subcontract)
        self.net_payable = self.net_current
