import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ""
	if filters.get("project"):
		conditions += " and project = %(project)s"
	if filters.get("status"):
		conditions += " and status = %(status)s"
	columns = [
		{"label": "Variation", "fieldname": "name", "fieldtype": "Link", "options": "Contract Variation", "width": 130},
		{"label": "Project", "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": "Type", "fieldname": "variation_type", "fieldtype": "Data", "width": 120},
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 90},
		{"label": "Value", "fieldname": "variation_value", "fieldtype": "Currency", "width": 130},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
	]
	rows = frappe.db.sql(f"""select name, project, variation_type, date, variation_value, status
		from `tabContract Variation` where 1=1 {conditions} order by date desc""", filters, as_dict=True)
	return columns, rows
