import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class WBS(NestedSet):
	nsm_parent_field = "parent_wbs"

	def validate(self):
		if self.parent_wbs == self.name:
			frappe.throw(_("WBS cannot be its own parent."))
		self._validate_project_scope()
		self._set_level()
		self._enforce_unique_code()

	def _validate_project_scope(self):
		if self.parent_wbs:
			pp = frappe.db.get_value("WBS", self.parent_wbs, "project")
			if pp and pp != self.project:
				frappe.throw(_("Parent WBS must belong to the same Project."))

	def _set_level(self):
		if self.parent_wbs:
			parent_level = frappe.db.get_value("WBS", self.parent_wbs, "level") or 0
			self.level = parent_level + 1
		else:
			self.level = 0

	def _enforce_unique_code(self):
		dup = frappe.db.exists("WBS", {"project": self.project, "wbs_code": self.wbs_code,
			"name": ("!=", self.name)})
		if dup:
			frappe.throw(_("WBS Code {0} already exists in this Project.").format(self.wbs_code))
