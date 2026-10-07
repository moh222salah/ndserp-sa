"""Maps a processed PTS Pump Transaction to ERPNext (POS/Sales + stock).
Reuses ERPNext Sales Invoice; never creates duplicate item/customer masters.

NOTE: field names for Sales Invoice are stable across v15/v16, but confirm your
POS setup (POS Profile / walk-in customer) before enabling auto-invoicing."""
import frappe
from frappe.utils import getdate


def process_pump_transaction(txn_name):
    doc = frappe.get_doc("PTS Pump Transaction", txn_name)
    if doc.processing_status in ("Processed", "Duplicate", "Ignored"):
        return
    doc.db_set("processing_status", "Processing", update_modified=False)
    try:
        settings = frappe.get_single("Gas Station Settings")
        if settings.auto_create_sales_invoice and not doc.is_test:
            ref = _create_sales_invoice(doc, settings)
            if ref:
                doc.db_set("erpnext_doctype", "Sales Invoice", update_modified=False)
                doc.db_set("erpnext_reference", ref, update_modified=False)
        doc.db_set("processing_status", "Processed", update_modified=False)
        doc.db_set("processed_at", frappe.utils.now_datetime(), update_modified=False)
        doc.db_set("error_message", None, update_modified=False)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        doc.reload()
        doc.db_set("processing_status", "Failed", update_modified=False)
        doc.db_set("retry_count", (doc.retry_count or 0) + 1, update_modified=False)
        doc.db_set("error_message", str(e)[:1000], update_modified=False)
        frappe.db.commit()
        raise


def _create_sales_invoice(doc, settings):
    if not (doc.erpnext_item and doc.volume and doc.amount):
        return None
    station = frappe.get_doc("Gas Station", doc.station)
    customer = settings.default_customer
    if not customer:
        frappe.throw("Set a Walk-in Customer in Gas Station Settings to auto-invoice.")

    si = frappe.new_doc("Sales Invoice")
    si.customer = customer
    si.company = station.company
    si.is_pos = 1
    si.update_stock = 1 if settings.update_stock_on_sale else 0
    si.set_posting_time = 1
    si.posting_date = getdate(doc.start_datetime)
    if station.default_pos_profile:
        si.pos_profile = station.default_pos_profile
    if settings.selling_price_list:
        si.selling_price_list = settings.selling_price_list
    if station.default_cost_center:
        si.cost_center = station.default_cost_center

    rate = doc.price or (doc.amount / doc.volume if doc.volume else 0)
    si.append("items", {
        "item_code": doc.erpnext_item,
        "qty": doc.volume,
        "rate": rate,
        "warehouse": station.default_warehouse,
        "cost_center": station.default_cost_center,
    })
    # cash payment so the POS invoice balances
    if si.is_pos:
        si.append("payments", {"mode_of_payment": _cash_mode(station.company),
                               "amount": doc.amount})
    si.flags.ignore_permissions = True
    si.insert()
    si.submit()
    return si.name


def _cash_mode(company):
    return frappe.db.get_value("Mode of Payment", {"type": "Cash"}) or "Cash"


def retry_failed(limit=50):
    """Requeue failed transactions (call from a report action or scheduler)."""
    for name in frappe.get_all("PTS Pump Transaction",
                               filters={"processing_status": "Failed"},
                               pluck="name", limit=limit):
        frappe.enqueue(process_pump_transaction, queue="long", txn_name=name)
