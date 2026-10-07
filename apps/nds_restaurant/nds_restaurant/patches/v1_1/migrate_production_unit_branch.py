import frappe
from nds_restaurant.patches.v1_0.create_custom_fields import execute as create_custom_fields


def execute():
	"""
	Migrate Production Unit branch field:
	1. Create Branch records for distinct invalid branch values (don't throw away user data)
	2. Populate branch from POS Profile when empty
	"""
	# Ensure custom fields exist before trying to set values
	create_custom_fields()
	
	frappe.reload_doctype("NDS Production Unit")
	
	# Step 1: Create missing Branch records from distinct invalid values
	# Get distinct branch values that aren't valid Branch names
	invalid_branches = frappe.db.sql("""
		SELECT DISTINCT pu.branch
		FROM `tabNDS Production Unit` pu
		LEFT JOIN `tabBranch` b ON pu.branch = b.name
		WHERE pu.branch IS NOT NULL
		AND pu.branch != ''
		AND b.name IS NULL
	""", as_dict=True)
	
	for row in invalid_branches:
		branch_name = row.branch
		if branch_name and not frappe.db.exists("Branch", branch_name):
			# Create the Branch record
			branch_doc = frappe.new_doc("Branch")
			branch_doc.branch = branch_name
			branch_doc.flags.ignore_permissions = True
			branch_doc.insert()
			frappe.db.commit()
	
	# Step 2: Populate branch from POS Profile's custom_branch when empty
	frappe.db.sql("""
		UPDATE `tabNDS Production Unit` pu
		INNER JOIN `tabPOS Profile` pp ON pu.pos_profile = pp.name
		SET pu.branch = pp.custom_branch
		WHERE pu.pos_profile IS NOT NULL
		AND pu.pos_profile != ''
		AND (pu.branch IS NULL OR pu.branch = '')
		AND pp.custom_branch IS NOT NULL
		AND pp.custom_branch != ''
	""")
