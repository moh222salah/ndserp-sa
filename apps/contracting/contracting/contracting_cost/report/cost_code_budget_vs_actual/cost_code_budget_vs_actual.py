import frappe
from contracting.services.actual_cost import actual_by


def execute(filters=None):
	filters = filters or {}
	project = filters.get("project")
	columns = [
		{"label": "Cost Code", "fieldname": "cost_code", "fieldtype": "Link", "options": "Cost Code", "width": 160},
		{"label": "Description", "fieldname": "cc_name", "fieldtype": "Data", "width": 200},
		{"label": "Budget", "fieldname": "budget", "fieldtype": "Currency", "width": 130},
		{"label": "Actual", "fieldname": "actual", "fieldtype": "Currency", "width": 130},
		{"label": "Variance", "fieldname": "variance", "fieldtype": "Currency", "width": 130},
		{"label": "Variance %", "fieldname": "variance_pct", "fieldtype": "Percent", "width": 100},
	]
	if not project:
		return columns, []
	budget = dict(frappe.db.sql("""
		select i.cost_code, coalesce(sum(i.budget_amount),0)
		from `tabBudget Per Cost Code Item` i
		inner join `tabBudget Per Cost Code` b on i.parent=b.name
		where b.project=%s and b.status in ('Approved','Submitted') group by i.cost_code
	""", project))
	actual = actual_by(project, "cost_code")
	rows = []
	for code in sorted(set(list(budget) + list(actual))):
		b = budget.get(code, 0) or 0
		a = actual.get(code, 0) or 0
		rows.append({"cost_code": code,
			"cc_name": frappe.db.get_value("Cost Code", code, "cost_code_name"),
			"budget": b, "actual": a, "variance": a - b,
			"variance_pct": ((a - b) / b * 100) if b else 0})
	return columns, rows
