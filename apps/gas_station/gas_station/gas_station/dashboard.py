"""Dashboard data. KPIs read from the correct source: operational metrics from
the Gas Station app's current-state/history; revenue is the summed transaction
amount (swap to linked Sales Invoice grand_total if you prefer ERPNext totals)."""
import frappe
from frappe.utils import flt, get_datetime, now_datetime, today, add_days, nowdate


def _station_filter(station):
    return {"station": station} if station else {}


def _date_range(from_date, to_date, all_time=False):
    """Default to the last 7 days so the dashboard always shows something.
    to_date is inclusive of the whole day. all_time removes the bounds."""
    if all_time:
        return None, None
    if not to_date:
        to_date = nowdate()
    if not from_date:
        from_date = add_days(to_date, -6)
    return str(from_date) + " 00:00:00", str(to_date) + " 23:59:59"


@frappe.whitelist()
def get_dashboard_data(station=None, from_date=None, to_date=None, all_time=0):
    frappe.has_permission("Pump State", throw=True)
    all_time = frappe.utils.cint(all_time)
    start, end = _date_range(from_date, to_date, all_time)
    return {
        "generated_at": str(now_datetime()),
        "range": {"from": start, "to": end, "all_time": all_time},
        "kpis": _kpis(station, start, end),
        "pumps": _pumps(station),
        "tanks": _tanks(station),
        "alerts": _alerts(station),
        "transactions": _latest_txns(station, start, end),
        "controllers": _controllers(station),
        "demo": bool(frappe.db.get_single_value("Gas Station Settings", "demo_mode")),
    }


def _kpis(station, start, end):
    sf = _station_filter(station)
    where_conditions = []
    params = []
    
    if station:
        where_conditions.append("station = %s")
        params.append(station)
        
    if start and end:
        where_conditions.append("start_datetime BETWEEN %s AND %s")
        params.extend([start, end])
        
    where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""
    
    # Direct SQL execution to comply with Frappe v16 QueryBuilder constraints
    query = f"""
        SELECT 
            COALESCE(SUM(amount), 0) as amount,
            COALESCE(SUM(volume), 0) as volume,
            COUNT(name) as n
        FROM `tabPTS Pump Transaction`
        {where_clause}
    """
    res = frappe.db.sql(query, tuple(params), as_dict=True)
    txn = res[0] if res else {"amount": 0, "volume": 0, "n": 0}

    active = frappe.db.count("Pump State", {**sf, "communication_status": "Live"})
    open_alerts = frappe.db.count("Station Alert", {**sf, "status": "Open"})
    
    tank_query = f"""
        SELECT COALESCE(SUM(product_volume), 0) as v 
        FROM `tabTank State`
        {"WHERE station = %s" if station else ""}
    """
    tank_res = frappe.db.sql(tank_query, (station,) if station else (), as_dict=True)
    tank_stock = tank_res[0].v if tank_res else 0

    ctrl_filter = _station_filter(station)
    total_ctrl = frappe.db.count("PTS Controller", {**ctrl_filter, "enabled": 1})
    connected = frappe.db.count("PTS Controller",
                                {**ctrl_filter, "enabled": 1, "connection_status": "Connected"})
    return {
        "revenue": flt(txn.get("amount")),
        "fuel_sold": flt(txn.get("volume")),
        "transactions": txn.get("n") or 0,
        "active_pumps": active,
        "open_alerts": open_alerts,
        "tank_stock": flt(tank_stock),
        "integration": f"{connected}/{total_ctrl}",
        "integration_ok": connected == total_ctrl and total_ctrl > 0,
    }


def _pumps(station):
    return frappe.get_all(
        "Pump State", filters=_station_filter(station),
        fields=["pump", "station", "status", "communication_status",
                "current_fuel_grade", "current_nozzle", "current_volume",
                "current_amount", "flow_rate", "totalizer_volume", "last_updated_at"],
        order_by="pump asc")


def _tanks(station):
    return frappe.get_all(
        "Tank State", filters=_station_filter(station),
        fields=["tank", "station", "status", "communication_status",
                "product_volume", "fill_percentage", "temperature", "water_level",
                "last_updated_at"], order_by="tank asc")


def _alerts(station):
    sf = _station_filter(station)
    return {
        "critical": frappe.db.count("Station Alert", {**sf, "status": "Open", "severity": "Critical"}),
        "warning": frappe.db.count("Station Alert", {**sf, "status": "Open", "severity": "Warning"}),
        "recent": frappe.get_all("Station Alert", filters={**sf, "status": ["!=", "Cleared"]},
                                 fields=["name", "alert_type", "severity", "message",
                                         "occurred_at", "equipment_reference"],
                                 order_by="occurred_at desc", limit=8),
    }


def _latest_txns(station, start=None, end=None):
    filters = _station_filter(station)
    if start and end:
        filters["start_datetime"] = ["between", [start, end]]
    return frappe.get_all(
        "PTS Pump Transaction", filters=filters,
        fields=["name", "station", "pump", "nozzle", "fuel_grade", "volume",
                "amount", "start_datetime", "processing_status"],
        order_by="start_datetime desc", limit=12)


def _controllers(station):
    filt = _station_filter(station)
    rows = frappe.get_all("PTS Controller", filters={**filt, "enabled": 1},
                          fields=["name", "controller_name", "station",
                                  "connection_status", "last_communication_at"])
    for r in rows:
        cs = frappe.db.get_value("Controller Connection State", {"controller": r.name},
                                 ["latency_ms", "last_status_received_at"], as_dict=True)
        r["latency_ms"] = cs.latency_ms if cs else None
        r["last_status_received_at"] = cs.last_status_received_at if cs else None
    return rows
