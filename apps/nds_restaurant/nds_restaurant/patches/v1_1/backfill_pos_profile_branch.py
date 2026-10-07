import frappe
from nds_restaurant.patches.v1_0.create_custom_fields import execute as create_custom_fields


def execute():
	"""Set custom_branch from the restaurant on existing POS Profiles."""
	# Ensure custom fields exist before trying to set values
	create_custom_fields()
	
	frappe.reload_doctype("POS Profile")
	
	# Use set-based UPDATE joining POS Profile to NDS Restaurant
	frappe.db.sql("""
		UPDATE `tabPOS Profile` pp
		INNER JOIN `tabNDS Restaurant` nr ON pp.custom_restaurant = nr.name
		SET pp.custom_branch = nr.branch
		WHERE pp.custom_restaurant IS NOT NULL
		AND pp.custom_restaurant != ''
		AND (pp.custom_branch IS NULL OR pp.custom_branch = '')
		AND nr.branch IS NOT NULL
		AND nr.branch != ''
	""")
