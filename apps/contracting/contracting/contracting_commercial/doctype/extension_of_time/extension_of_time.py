import frappe
from frappe.utils import add_days
from frappe.model.document import Document


class ExtensionofTime(Document):
	def validate(self):
		if self.from_date and self.approved_days:
			self.new_end_date = add_days(self.from_date, self.approved_days)

	def on_update(self):
		# EOT changes time entitlement only; update the Project expected end date.
		if self.status == "Approved" and self.new_end_date:
			frappe.db.set_value("Project", self.project, "expected_end_date",
				self.new_end_date, update_modified=False)
