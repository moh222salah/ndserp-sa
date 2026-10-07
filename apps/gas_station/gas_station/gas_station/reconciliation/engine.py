"""Reconciliation as an operational control layer.
A) PTS Transaction vs ERPNext Sales   B) Pump Totalizer   C) Tank Balance."""
import frappe
from frappe.utils import flt


def run_reconciliation(recon_type, station, from_date, to_date):
    if recon_type == "PTS vs ERPNext Sales":
        return _pts_vs_sales(station, from_date, to_date)
    if recon_type == "Pump Totalizer":
        return _pump_totalizer(station, from_date, to_date)
    if recon_type == "Tank Balance":
        return _tank_balance(station, from_date, to_date)
    return []


def _line(category, ref, expected, actual, status):
    expected, actual = flt(expected), flt(actual)
    var = actual - expected
    pct = (var / expected * 100) if expected else 0
    return {"category": category, "reference": ref, "expected": expected,
            "actual": actual, "variance": var, "variance_pct": pct, "status": status}


def _pts_vs_sales(station, from_date, to_date):
    """Compare processed PTS transactions to their linked Sales Invoices."""
    rows = []
    txns = frappe.get_all(
        "PTS Pump Transaction",
        filters={"station": station, "start_datetime": ["between", [from_date, to_date]]},
        fields=["name", "pts_transaction_id", "amount", "volume", "processing_status",
                "erpnext_reference", "erpnext_doctype"])
    for t in txns:
        if t.processing_status in ("Duplicate", "Ignored", "Test"):
            continue
        if not t.erpnext_reference:
            status = "Missing in ERPNext" if t.processing_status == "Processed" else "Pending"
            rows.append(_line("Transaction", t.pts_transaction_id, t.amount, 0, status))
            frappe.db.set_value("PTS Pump Transaction", t.name, "reconciliation_status",
                                "Missing in ERPNext", update_modified=False)
            continue
        si_total = frappe.db.get_value(t.erpnext_doctype, t.erpnext_reference, "grand_total") or 0
        status = "Matched" if abs(flt(si_total) - flt(t.amount)) < 0.01 else "Amount Mismatch"
        rows.append(_line("Transaction", t.pts_transaction_id, t.amount, si_total, status))
        frappe.db.set_value("PTS Pump Transaction", t.name, "reconciliation_status",
                            status, update_modified=False)
    frappe.db.commit()
    return rows


def _pump_totalizer(station, from_date, to_date):
    """Opening vs closing totalizer vs summed transaction volume, per pump."""
    rows = []
    pumps = frappe.get_all("Gas Station Pump", filters={"station": station}, pluck="pump_number")
    for pump in pumps:
        txns = frappe.get_all(
            "PTS Pump Transaction",
            filters={"station": station, "pump": pump,
                     "start_datetime": ["between", [from_date, to_date]]},
            fields=["volume", "total_volume"], order_by="start_datetime asc")
        if not txns:
            continue
        summed = sum(flt(t.volume) for t in txns)
        tot_first = flt(txns[0].total_volume)
        tot_last = flt(txns[-1].total_volume)
        totalizer_delta = tot_last - tot_first + flt(txns[0].volume)
        status = "Matched" if abs(totalizer_delta - summed) < 0.5 else "Volume Mismatch"
        rows.append(_line("Pump", pump, summed, totalizer_delta, status))
    return rows


def _tank_balance(station, from_date, to_date):
    """opening + deliveries - dispensed ~= closing (physical sensor reading)."""
    rows = []
    tanks = frappe.get_all("Gas Station Tank", filters={"station": station},
                           fields=["name", "tank_number", "erpnext_item"])
    for tk in tanks:
        opening = _tank_volume_at(tk.name, from_date)
        closing_actual = _tank_volume_at(tk.name, to_date)
        deliveries = sum(flt(d.delivery_volume) for d in frappe.get_all(
            "Tank Delivery",
            filters={"tank": tk.name, "start_datetime": ["between", [from_date, to_date]]},
            fields=["delivery_volume"]))
        dispensed = sum(flt(t.volume) for t in frappe.get_all(
            "PTS Pump Transaction",
            filters={"station": station, "erpnext_item": tk.erpnext_item,
                     "start_datetime": ["between", [from_date, to_date]]},
            fields=["volume"]))
        expected_closing = flt(opening) + deliveries - dispensed
        status = "Matched" if abs(expected_closing - flt(closing_actual)) < \
            max(50, flt(closing_actual) * 0.01) else "Volume Mismatch"
        rows.append(_line("Tank", tk.tank_number, expected_closing, closing_actual, status))
    return rows


def _tank_volume_at(tank, when):
    row = frappe.get_all("Tank Measurement",
                         filters={"tank": tank, "measurement_datetime": ["<=", when]},
                         fields=["product_volume"],
                         order_by="measurement_datetime desc", limit=1)
    return row[0].product_volume if row else 0
