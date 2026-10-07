import frappe
from frappe import _
from frappe.utils import flt

from optical.utils.insurance import split_amounts
from optical.utils.profile import ensure_profile

ROLE_BY_TYPE = {
    "Frame": "Frame",
    "Contact Lens": "Contact Lens",
    "Accessory": "Accessory",
    "Service": "Service",
}


@frappe.whitelist()
def get_item_price(item_code):
    frappe.has_permission("Item", "read", throw=True)
    item = frappe.db.get_value(
        "Item", item_code, ["item_name", "standard_rate", "optical_item_type"], as_dict=True
    )
    if not item:
        frappe.throw(_("Item {0} not found").format(item_code))
    rate = 0
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    if price_list:
        prices = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list, "selling": 1},
            fields=["price_list_rate"],
            order_by="valid_from desc",
            limit=1,
        )
        if prices:
            rate = prices[0].price_list_rate
    return {
        "item_name": item.item_name,
        "rate": flt(rate) or flt(item.standard_rate),
        "role": ROLE_BY_TYPE.get(item.optical_item_type),
    }


@frappe.whitelist()
def estimate_insurance(net_total, plan):
    plan = frappe.db.get_value(
        "Insurance Plan", plan, ["coverage_percent", "max_coverage", "deductible"], as_dict=True
    )
    if not plan:
        return {"insurer_amount": 0, "customer_amount": flt(net_total)}
    insurer, customer = split_amounts(
        flt(net_total), plan.coverage_percent, plan.max_coverage, plan.deductible
    )
    return {"insurer_amount": insurer, "customer_amount": customer}


@frappe.whitelist()
def open_profile(customer):
    frappe.has_permission("Optical Profile", "read", throw=True)
    return ensure_profile(customer)


@frappe.whitelist()
def get_profile_defaults(customer):
    if not frappe.db.exists("Optical Profile", customer):
        return {}
    profile = frappe.db.get_value(
        "Optical Profile",
        customer,
        ["default_insurance_plan", "insurance_valid_till", "last_prescription"],
        as_dict=True,
    )
    return profile
