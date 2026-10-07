import frappe
from frappe import _
from frappe.model.document import Document


class ExecutedQuantity(Document):
	def validate(self):
		wp = frappe.db.get_value("WBS", self.wbs, "project") if self.wbs else None
		if wp and wp != self.project:
			frappe.throw(_("WBS is not in the selected Project."))
		bp = frappe.db.get_value("Budget BOQ Item", self.boq_item, "project")
		if bp and bp != self.project:
			frappe.throw(_("Budget BOQ Item is not in the selected Project."))
		if (self.quantity or 0) < 0:
			frappe.throw(_("Quantity cannot be negative."))
		self._over_execution()

	def _over_execution(self):
		budget_qty = frappe.db.get_value("Budget BOQ Item", self.boq_item, "quantity") or 0
		if not budget_qty:
			return
		prior = frappe.db.sql("""select coalesce(sum(quantity),0) from `tabExecuted Quantity`
			where boq_item=%s and status='Approved' and name!=%s""",
			(self.boq_item, self.name or ""))[0][0] or 0
		if prior + (self.quantity or 0) > budget_qty:
			frappe.msgprint(_("Cumulative executed quantity ({0}) exceeds the Budget BOQ quantity ({1}).")
				.format(prior + (self.quantity or 0), budget_qty), indicator="orange", alert=True)
