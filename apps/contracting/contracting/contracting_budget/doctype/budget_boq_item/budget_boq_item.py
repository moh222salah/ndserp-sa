import frappe
from frappe import _
from frappe.model.document import Document
from contracting.contracting_budget.doctype.project_budget.project_budget import update_budget_totals


class BudgetBOQItem(Document):
    def validate(self):
        bp = frappe.db.get_value("Project Budget", self.budget, "project")
        if bp and self.project and bp != self.project:
            frappe.throw(_("Budget BOQ Item project must match its Project Budget."))
        if (self.quantity or 0) <= 0:
            frappe.throw(_("Quantity must be greater than zero."))
        self._compute()

    def _compute(self):
        direct = 0.0
        for t in (self.materials, self.labour, self.equipment, self.subcontracts):
            for r in t:
                r.amount = (r.quantity or 0) * (r.rate or 0)
                direct += r.amount or 0
        for r in self.expenses:
            direct += r.amount or 0
        self.direct_cost = direct
        if self.pricing_mode == "Detailed Breakdown":
            self.cost_amount = direct
            self.cost_rate = (direct / self.quantity) if self.quantity else 0
        else:
            self.cost_amount = (self.quantity or 0) * (self.cost_rate or 0)
        self.selling_amount = (self.quantity or 0) * (self.selling_rate or 0)
        self.planned_profit = (self.selling_amount or 0) - (self.cost_amount or 0)
        self.planned_margin = ((self.planned_profit / self.selling_amount) * 100) if self.selling_amount else 0

    def on_update(self):
        update_budget_totals(self.budget)

    def on_trash(self):
        update_budget_totals(self.budget)
