import frappe
from frappe import _
from frappe.model.document import Document


class WBSAllocation(Document):
	def validate(self):
		wp = frappe.db.get_value("WBS", self.wbs, "project")
		if wp and wp != self.project:
			frappe.throw(_("Selected WBS does not belong to the selected Project."))
		if self.boq_item:
			bp = frappe.db.get_value("Budget BOQ Item", self.boq_item, "project")
			if bp and bp != self.project:
				frappe.throw(_("Selected BOQ Item does not belong to the selected Project."))
