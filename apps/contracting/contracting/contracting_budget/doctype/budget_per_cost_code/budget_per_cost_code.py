import frappe
from frappe import _
from frappe.model.document import Document


class BudgetPerCostCode(Document):
    def validate(self):
        seen = set()
        total = 0.0
        for row in self.items:
            if row.cost_code in seen:
                frappe.throw(_("Cost Code {0} is entered more than once.").format(row.cost_code))
            seen.add(row.cost_code)
            if frappe.db.get_value("Cost Code", row.cost_code, "is_group"):
                frappe.throw(_("Cost Code {0} is a group; budget only against leaf cost codes.").format(row.cost_code))
            if (row.budget_amount or 0) < 0:
                frappe.throw(_("Budget Amount cannot be negative."))
            total += row.budget_amount or 0
        self.total_budget = total
