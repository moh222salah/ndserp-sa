import frappe
from contracting.services.actual_cost import actual_by


def execute(filters=None):
	filters = filters or {}
	project = filters.get("project")
	columns = [
		{"label": "BOQ Item", "fieldname": "boq_item", "fieldtype": "Link", "options": "Budget BOQ Item", "width": 130},
		{"label": "BOQ No", "fieldname": "boq_no", "fieldtype": "Data", "width": 90},
		{"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 220},
		{"label": "Budget Cost", "fieldname": "budget", "fieldtype": "Currency", "width": 130},
		{"label": "Actual Cost", "fieldname": "actual", "fieldtype": "Currency", "width": 130},
		{"label": "Variance", "fieldname": "variance", "fieldtype": "Currency", "width": 130},
		{"label": "Variance %", "fieldname": "variance_pct", "fieldtype": "Percent", "width": 100},
	]
	if not project:
		return columns, []
	actual = actual_by(project, "boq_item")
	rows = []
	for b in frappe.get_all("Budget BOQ Item", filters={"project": project},
			fields=["name", "boq_no", "description", "cost_amount"], order_by="boq_no"):
		a = actual.get(b.name, 0) or 0
		bc = b.cost_amount or 0
		rows.append({"boq_item": b.name, "boq_no": b.boq_no, "description": b.description,
			"budget": bc, "actual": a, "variance": a - bc,
			"variance_pct": ((a - bc) / bc * 100) if bc else 0})
	return columns, rows
