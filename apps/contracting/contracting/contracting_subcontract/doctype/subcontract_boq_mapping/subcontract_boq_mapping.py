import frappe
from frappe import _
from frappe.model.document import Document


class SubcontractBOQMapping(Document):
	def validate(self):
		sb_parent = frappe.db.get_value("Subcontract BOQ Item", self.subcontract_boq_item, "subcontract")
		if sb_parent and sb_parent != self.subcontract:
			frappe.throw(_("Subcontract BOQ Item does not belong to the selected Subcontract."))
		proj = frappe.db.get_value("Subcontract", self.subcontract, "project")
		cproj = frappe.db.get_value("Budget BOQ Item", self.client_boq_item, "project")
		if proj and cproj and proj != cproj:
			frappe.throw(_("Client BOQ Item and Subcontract are in different Projects."))
