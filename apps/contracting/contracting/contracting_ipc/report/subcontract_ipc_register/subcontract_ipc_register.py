import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ""
	if filters.get("subcontract"):
		conditions += " and subcontract = %(subcontract)s"
	if filters.get("status"):
		conditions += " and status = %(status)s"

	columns = [
		{"label": "IPC", "fieldname": "name", "fieldtype": "Link", "options": "Subcontract IPC", "width": 130},
		{"label": "Subcontract", "fieldname": "subcontract", "fieldtype": "Link", "options": "Subcontract", "width": 130},
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 90},
		{"label": "Net (current)", "fieldname": "net_current", "fieldtype": "Currency", "width": 120},
		{"label": "Total Net", "fieldname": "total_net", "fieldtype": "Currency", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
	]
	rows = frappe.db.sql(f"""
		select name, subcontract, supplier, date, net_current, total_net, status
		from `tabSubcontract IPC` where 1=1 {conditions} order by date desc
	""", filters, as_dict=True)
	return columns, rows
