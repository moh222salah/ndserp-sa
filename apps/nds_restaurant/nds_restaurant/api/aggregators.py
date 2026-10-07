# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P8: aggregator (delivery platform) orders driven by Branch > Aggregator Settings.

Branch lookup and price-list helpers are salvaged from PR #10; settlement (paid vs Keep Unpaid)
is new. Every entry point tolerates sites without the P8 schema (shared bench with unmigrated sites).
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from nds_restaurant.utils.access import assert_can_bill

AGGREGATOR = "Aggregator"


def branch_has_aggregator_table():
	try:
		return frappe.get_meta("Branch").has_field("nds_aggregator_settings")
	except Exception:
		return False


def get_branch_aggregators(branch):
	"""Configured rows for a Branch: customer, customer_name, price_list, mode_of_payment, keep_unpaid, without_tax."""
	if not branch or not branch_has_aggregator_table() or not frappe.db.exists("Branch", branch):
		return []
	rows = []
	for row in frappe.get_doc("Branch", branch).get("nds_aggregator_settings") or []:
		if not row.customer:
			continue
		rows.append(
			{
				"name": row.name,
				"customer": row.customer,
				"customer_name": frappe.db.get_value("Customer", row.customer, "customer_name") or row.customer,
				"price_list": row.price_list,
				"mode_of_payment": row.mode_of_payment,
				"keep_unpaid": cint(row.keep_unpaid),
				"without_tax": cint(row.without_tax),
			}
		)
	return rows


def get_aggregator_settings(branch, customer):
	if not customer:
		return None
	for row in get_branch_aggregators(branch):
		if row["customer"] == customer:
			return row
	return None


def assert_aggregator_configured(branch, customer):
	settings = get_aggregator_settings(branch, customer)
	if not settings:
		frappe.throw(
			_("Aggregator {0} is not configured on Branch {1}").format(frappe.bold(customer or ""), frappe.bold(branch or ""))
		)
	return settings


def price_list_rates(price_list, item_codes):
	"""{item_code: selling rate} from Item Price for the items that have one in the price list."""
	item_codes = [c for c in set(item_codes or []) if c]
	if not price_list or not item_codes:
		return {}
	rates = {}
	for row in frappe.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ["in", item_codes], "selling": 1},
		fields=["item_code", "price_list_rate"],
		order_by="valid_from asc",
	):
		rates[row.item_code] = flt(row.price_list_rate)
	return rates


def context_aggregators(branch, item_codes):
	"""Branch aggregators for the POS context, each with its price-list rates for the menu items."""
	rows = get_branch_aggregators(branch)
	for row in rows:
		row["rates"] = price_list_rates(row.get("price_list"), item_codes)
	return rows


def apply_to_order(doc, settings, item_rates):
	"""P8-T1 on a draft POS Invoice: aggregator customer, its price list and (optionally) no tax.

	`item_rates` maps item_code -> the menu rate; aggregator Item Prices override it.
	"""
	doc.customer = settings["customer"]
	if doc.meta.has_field("custom_aggregator"):
		doc.custom_aggregator = settings["customer"]
	if settings.get("price_list"):
		rates = price_list_rates(settings["price_list"], [r.item_code for r in doc.items])
		for row in doc.items:
			if row.item_code in rates:
				row.rate = rates[row.item_code]
				item_rates[row.item_code] = rates[row.item_code]
		doc.selling_price_list = settings["price_list"]
	if settings.get("without_tax"):
		doc.taxes_and_charges = None
		doc.set("taxes", [])


def order_settings(doc):
	"""Aggregator settings for an invoice (None when it isn't an aggregator order)."""
	if doc.get("custom_nds_order_type") != AGGREGATOR or not doc.get("custom_aggregator"):
		return None
	profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
	restaurant = profile.get("custom_restaurant")
	branch = frappe.db.get_value("NDS Restaurant", restaurant, "branch") if restaurant else None
	return get_aggregator_settings(branch, doc.custom_aggregator)


# ---------------------------------------------------------------------------
# P8-T2: settlement
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def settle_aggregator(invoice, mode_of_payment=None):
	"""Settle a draft aggregator order.

	Keep Unpaid off: submit the POS Invoice with one payment on the aggregator's mode of payment.
	Keep Unpaid on: a POS Invoice can't stay unpaid, so it becomes a receivable Sales Invoice for the
	aggregator customer (same items/taxes, update_stock, ingredients issued), the draft is deleted and
	its KOTs point to the Sales Invoice.
	"""
	from nds_restaurant.api.pos import _assert_pos_profile_access

	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice))
	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	assert_can_bill(doc.pos_profile)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft orders can be settled"))
	settings = order_settings(doc)
	if not settings:
		frappe.throw(_("{0} is not an aggregator order").format(invoice))

	if settings.get("keep_unpaid"):
		sales_invoice = convert_to_sales_invoice(doc, settings)
		return {"invoice": invoice, "sales_invoice": sales_invoice, "settled": True, "keep_unpaid": 1}

	from nds_restaurant.api.pos import submit_payment

	mop = mode_of_payment or settings.get("mode_of_payment") or _default_mop(doc.pos_profile)
	if not mop:
		frappe.throw(_("No Mode of Payment on the aggregator settings or the POS Profile"))
	amount = doc.rounded_total or doc.grand_total
	res = submit_payment(invoice=invoice, payments=json.dumps([{"mode_of_payment": mop, "amount": amount}]))
	return {
		"invoice": invoice,
		"settled": True,
		"keep_unpaid": 0,
		"mode_of_payment": mop,
		"grand_total": (res or {}).get("grand_total", doc.grand_total),
	}


def _default_mop(pos_profile):
	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	mop = next((p.mode_of_payment for p in profile.payments if p.default), None)
	if not mop and profile.payments:
		mop = profile.payments[0].mode_of_payment
	return mop


SI_COPY_FIELDS = (
	"company",
	"customer",
	"currency",
	"conversion_rate",
	"selling_price_list",
	"price_list_currency",
	"plc_conversion_rate",
	"taxes_and_charges",
	"set_warehouse",
	"cost_center",
	"update_stock",
	"additional_discount_percentage",
	"discount_amount",
	"apply_discount_on",
)
SI_ITEM_FIELDS = (
	"item_code",
	"item_name",
	"description",
	"qty",
	"uom",
	"stock_uom",
	"conversion_factor",
	"rate",
	"price_list_rate",
	"discount_percentage",
	"warehouse",
	"income_account",
	"expense_account",
	"cost_center",
)
SI_TAX_FIELDS = ("charge_type", "account_head", "description", "rate", "cost_center", "included_in_print_rate", "row_id", "tax_amount")


def convert_to_sales_invoice(pos_doc, settings):
	"""Keep Unpaid: the draft POS Invoice becomes a submitted, unpaid Sales Invoice."""
	si_meta = frappe.get_meta("Sales Invoice")
	if not si_meta.has_field("custom_source_pos_invoice"):
		frappe.throw(_("Aggregator Sales Invoice fields are not installed on this site (run migrate)"))
	si = frappe.new_doc("Sales Invoice")
	for field in SI_COPY_FIELDS:
		if pos_doc.get(field) is not None and si_meta.has_field(field):
			si.set(field, pos_doc.get(field))
	si.is_pos = 0
	si.update_stock = cint(pos_doc.update_stock)
	si.posting_date = frappe.utils.nowdate()
	si.due_date = si.posting_date
	if si_meta.has_field("pos_profile"):
		# not a POS sale (is_pos=0); kept so the order can be traced to its till
		si.pos_profile = pos_doc.pos_profile
	si.custom_source_pos_invoice = pos_doc.name
	si.custom_aggregator = settings["customer"]
	si.custom_aggregator_order_id = pos_doc.get("custom_aggregator_order_id")
	if si_meta.has_field("custom_daily_order_no"):
		si.custom_daily_order_no = pos_doc.get("custom_daily_order_no")
	si.remarks = _("Aggregator order {0} ({1})").format(pos_doc.name, settings.get("customer_name") or settings["customer"])
	for row in pos_doc.items:
		si.append("items", {f: row.get(f) for f in SI_ITEM_FIELDS if row.get(f) is not None})
	if not settings.get("without_tax"):
		for tax in pos_doc.get("taxes") or []:
			si.append("taxes", {f: tax.get(f) for f in SI_TAX_FIELDS if tax.get(f) is not None})
	else:
		si.taxes_and_charges = None
	si.flags.ignore_permissions = True
	si.insert()
	si.submit()

	# KOTs follow the order; the kitchen keeps the tickets it already has
	if frappe.get_meta("NDS KOT").has_field("sales_invoice"):
		for kot in frappe.get_all("NDS KOT", filters={"pos_invoice": pos_doc.name}, pluck="name"):
			frappe.db.set_value("NDS KOT", kot, "sales_invoice", si.name, update_modified=False)
	# delete the draft without sending Cancelled KOTs (P5-T2 trash hook)
	frappe.flags.nds_skip_trash_kots = pos_doc.name
	try:
		frappe.delete_doc("POS Invoice", pos_doc.name, ignore_permissions=True, force=True)
	finally:
		frappe.flags.nds_skip_trash_kots = None
	return si.name


# ---------------------------------------------------------------------------
# P8-T2: recipe stock on aggregator Sales Invoices
# ---------------------------------------------------------------------------


def is_aggregator_sales_invoice(doc):
	return bool(doc.meta.has_field("custom_source_pos_invoice") and doc.get("custom_source_pos_invoice"))


def on_sales_invoice_submit(doc, method=None):
	if not is_aggregator_sales_invoice(doc):
		return
	from nds_restaurant.api.recipe import issue_recipe_stock

	issue_recipe_stock(doc)


def before_sales_invoice_cancel(doc, method=None):
	"""KOTs keep their history; unlink them so the Sales Invoice can be cancelled."""
	if not is_aggregator_sales_invoice(doc) or not frappe.get_meta("NDS KOT").has_field("sales_invoice"):
		return
	frappe.db.sql("UPDATE `tabNDS KOT` SET sales_invoice=NULL WHERE sales_invoice=%s", doc.name)


def on_sales_invoice_cancel(doc, method=None):
	if not is_aggregator_sales_invoice(doc):
		return
	from nds_restaurant.api.recipe import cancel_recipe_stock

	cancel_recipe_stock(doc)
