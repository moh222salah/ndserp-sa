import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ""
	if filters.get("project"):
		conditions += " and contract = %(contract)s"
	if filters.get("status"):
		conditions += " and status = %(status)s"

	columns = [
		{"label": "IPC", "fieldname": "name", "fieldtype": "Link", "options": "Client IPC", "width": 130},
		{"label": "Project", "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 90},
		{"label": "Gross Valuation", "fieldname": "gross_valuation", "fieldtype": "Currency", "width": 130},
		{"label": "Net (current)", "fieldname": "net_current", "fieldtype": "Currency", "width": 120},
		{"label": "Total Net", "fieldname": "total_net", "fieldtype": "Currency", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 90},
	]
	rows = frappe.db.sql(f"""
		select name, contract, customer, date, gross_valuation, net_current, total_net, status
		from `tabClient IPC` where 1=1 {conditions} order by date desc
	""", filters, as_dict=True)
	return columns, rows
