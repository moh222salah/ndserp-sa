import frappe


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True
	roles = frappe.get_roles()
	return any(role in roles for role in ("System Manager", "NDS Manager", "NDS Cashier", "NDS Captain"))
