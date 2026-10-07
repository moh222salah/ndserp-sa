import frappe
from frappe import _
from frappe.model.document import Document


class ConstructionMaterialRequirement(Document):
	def validate(self):
		for row in self.items:
			if row.wbs:
				wp = frappe.db.get_value("WBS", row.wbs, "project")
				if wp and wp != self.project:
					frappe.throw(_("Row {0}: WBS is not in the selected Project.").format(row.idx))
			if row.boq_item:
				bp = frappe.db.get_value("Budget BOQ Item", row.boq_item, "project")
				if bp and bp != self.project:
					frappe.throw(_("Row {0}: BOQ Item is not in the selected Project.").format(row.idx))
