import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ""
	if filters.get("project"):
		conditions += " and b.project = %(project)s"
	columns = [
		{"label": "BOQ Item", "fieldname": "name", "fieldtype": "Link", "options": "Budget BOQ Item", "width": 130},
		{"label": "BOQ No", "fieldname": "boq_no", "fieldtype": "Data", "width": 90},
		{"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 220},
		{"label": "Unit", "fieldname": "unit", "fieldtype": "Data", "width": 70},
		{"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{"label": "Cost Amount", "fieldname": "cost_amount", "fieldtype": "Currency", "width": 130},
		{"label": "Selling Amount", "fieldname": "selling_amount", "fieldtype": "Currency", "width": 130},
		{"label": "Executed Qty", "fieldname": "executed_qty", "fieldtype": "Float", "width": 110},
		{"label": "Execution %", "fieldname": "progress", "fieldtype": "Percent", "width": 100},
	]
	rows = frappe.db.sql(f"""
		select b.name, b.boq_no, b.description, b.unit, b.quantity, b.cost_amount, b.selling_amount,
		       (select coalesce(sum(eq.quantity),0) from `tabExecuted Quantity` eq
		          where eq.boq_item=b.name and eq.status='Approved') as executed_qty
		from `tabBudget BOQ Item` b where 1=1 {conditions} order by b.boq_no
	""", filters, as_dict=True)
	for r in rows:
		r["progress"] = (r["executed_qty"] / r["quantity"] * 100) if r["quantity"] else 0
	return columns, rows
