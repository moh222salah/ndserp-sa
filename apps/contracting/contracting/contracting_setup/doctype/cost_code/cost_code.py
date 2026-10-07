import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class CostCode(NestedSet):
	nsm_parent_field = "parent_cost_code"

	def validate(self):
		if self.parent_cost_code == self.name:
			frappe.throw(_("Cost Code cannot be its own parent."))
