import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from optical.setup.custom_fields import CUSTOM_FIELDS

ROLES = [
    "Optical Manager", "Optical Branch Manager", "Optical Cashier",
    "Optician", "Optical Lab Technician", "Optical Warehouse User",
]

# Role Profiles bundle the optical role with the standard ERPNext roles it needs.
ROLE_PROFILES = {
    "Optical Cashier": ["Optical Cashier", "Sales User", "Accounts User"],
    "Optician": ["Optician", "Sales User"],
    "Optical Lab Technician": ["Optical Lab Technician", "Purchase User"],
    "Optical Warehouse User": ["Optical Warehouse User", "Stock User", "Stock Manager", "Purchase User"],
    "Optical Branch Manager": [
        "Optical Branch Manager", "Sales Manager", "Stock Manager", "Purchase Manager", "Accounts User",
    ],
    "Optical Manager": [
        "Optical Manager", "Optical Branch Manager", "Sales Manager", "Stock Manager",
        "Purchase Manager", "Accounts Manager",
    ],
}


def after_install():
    _setup()


def after_migrate():
    _setup()  # idempotent, repairs missing roles/custom fields after upgrades


def _setup():
    create_roles()
    create_custom_fields(CUSTOM_FIELDS, update=True)
    create_role_profiles()
    create_service_items()


def create_roles():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                ignore_permissions=True
            )


def create_role_profiles():
    for name, roles in ROLE_PROFILES.items():
        if frappe.db.exists("Role Profile", name):
            continue
        doc = frappe.new_doc("Role Profile")
        doc.role_profile = name
        for role in roles:
            if frappe.db.exists("Role", role):
                doc.append("roles", {"role": role})
        doc.insert(ignore_permissions=True)


def _service_item(code, name):
    if frappe.db.exists("Item", code):
        return code
    group = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"
    frappe.get_doc({
        "doctype": "Item", "item_code": code, "item_name": name, "item_group": group,
        "stock_uom": "Nos", "is_stock_item": 0, "include_item_in_manufacturing": 0,
    }).insert(ignore_permissions=True)
    return code


def create_service_items():
    settings = frappe.get_single("Optical Settings")
    changed = False
    if not settings.insurance_service_item:
        settings.insurance_service_item = _service_item("OPT-INSURANCE", "Insurance Coverage")
        changed = True
    if not settings.lab_service_item:
        settings.lab_service_item = _service_item("OPT-LAB-SERVICE", "Optical Laboratory Service")
        changed = True
    if changed:
        settings.flags.ignore_permissions = True
        settings.save()
