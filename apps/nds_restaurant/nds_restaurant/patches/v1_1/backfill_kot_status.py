import frappe


def execute():
	"""Set order_status='Served' for KOTs where served=1."""
	frappe.reload_doctype("NDS KOT")
	
	if not frappe.db.has_column("NDS KOT", "order_status"):
		return
	
	frappe.db.sql("""
		UPDATE `tabNDS KOT`
		SET order_status = 'Served'
		WHERE served = 1 AND (order_status IS NULL OR order_status = 'Ready For Prepare')
	""")
