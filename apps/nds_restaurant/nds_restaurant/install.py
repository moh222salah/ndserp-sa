import frappe


def after_install():
	create_roles()
	create_custom_fields()
	ensure_pos_operator_permissions()
	ensure_cncl_kot_naming_series_option()
	frappe.clear_cache()


def after_migrate():
	create_roles()
	create_custom_fields()
	ensure_pos_operator_permissions()
	ensure_cncl_kot_naming_series_option()


def ensure_pos_operator_permissions():
	from nds_restaurant.role_permissions import ensure_pos_operator_permissions as _ensure

	_ensure()


def ensure_cncl_kot_naming_series_option():
	from nds_restaurant.kot_naming import ensure_cncl_kot_naming_series_option as _ensure

	_ensure()


def create_custom_fields():
	"""Create custom fields for NDS Restaurant."""
	from nds_restaurant.patches.v1_0.create_custom_fields import get_custom_fields, get_p9_employee_custom_fields
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create
	
	_create(get_custom_fields(), update=True)
	_create(get_p9_employee_custom_fields(), update=True)


def create_roles():
	for role_name in ("NDS Manager", "NDS Cashier", "NDS Captain", "NDS Kitchen"):
		if not frappe.db.exists("Role", role_name):
			doc = frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}
			)
			doc.insert(ignore_permissions=True)
