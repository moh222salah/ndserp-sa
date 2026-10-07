import frappe
from frappe import _
from frappe.model.document import Document

APPROVED = ("Approved","Closed")


class ProjectBudget(Document):
    def validate(self):
        self.set_totals()

    def set_totals(self):
        if self.is_new():
            return
        row = frappe.db.sql("""select coalesce(sum(cost_amount),0), coalesce(sum(selling_amount),0)
            from `tabBudget BOQ Item` where budget=%s""", self.name)[0]
        self.total_cost_amount, self.total_selling_amount = row[0] or 0, row[1] or 0
        self.planned_profit = (self.total_selling_amount or 0) - (self.total_cost_amount or 0)
        self.planned_margin = ((self.planned_profit/self.total_selling_amount)*100) if self.total_selling_amount else 0


def update_budget_totals(budget):
    if not budget or not frappe.db.exists("Project Budget", budget):
        return
    row = frappe.db.sql("""select coalesce(sum(cost_amount),0), coalesce(sum(selling_amount),0)
        from `tabBudget BOQ Item` where budget=%s""", budget)[0]
    cost, sell = row[0] or 0, row[1] or 0
    profit = sell - cost
    frappe.db.set_value("Project Budget", budget, {
        "total_cost_amount": cost, "total_selling_amount": sell,
        "planned_profit": profit,
        "planned_margin": (profit/sell*100) if sell else 0}, update_modified=False)
