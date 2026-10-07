"""Demo data for the Gas Station app.

Everything the simulator produces flows through the SAME integration pipeline as
a real PTS-2 (MockPTSProvider -> dispatch.receive -> handlers). Demo history is
therefore indistinguishable in shape from production data.

Run:
    bench --site <site> execute gas_station.demo.seed.seed_demo_data
    bench --site <site> execute gas_station.demo.seed.reset_demo_data

Optional kwargs (seed_demo_data): days=3, txns_per_day=24
"""
import random
import frappe
from frappe.utils import add_days, add_to_date, get_datetime, nowdate

from gas_station.gas_station.simulator import engine as sim

COMPANY = "Saudi Demo Fuel Operations"
ABBR = "SDFO"
UOM = "Litre"
PRICE_LIST = "Standard Selling"
ITEM_GROUP = "Products"

FUELS = [("Gasoline 91", 2.18), ("Gasoline 95", 2.33), ("Diesel", 1.66)]

STATIONS = [
    ("RYD-N", "Riyadh North Station", "Riyadh"),
    ("JED-C", "Jeddah Corniche Station", "Jeddah"),
    ("DMM-P", "Dammam Port Station", "Dammam"),
    ("MEC-R", "Mecca Road Station", "Mecca"),
    ("MED-G", "Medina Gate Station", "Medina"),
]


# ============================================================ ERPNext masters
def _ensure_uom():
    if not frappe.db.exists("UOM", UOM):
        frappe.get_doc({"doctype": "UOM", "uom_name": UOM}).insert(ignore_permissions=True)


def _ensure_company():
    if frappe.db.exists("Company", COMPANY):
        return COMPANY
    frappe.get_doc({
        "doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
        "default_currency": "SAR", "country": "Saudi Arabia",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return COMPANY


def _default_warehouse():
    return (frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0,
                                              "warehouse_name": "Stores"})
            or frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0}))


def _default_cost_center():
    return frappe.db.get_value("Company", COMPANY, "cost_center") \
        or frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 0})


def _ensure_items():
    _ensure_uom()
    warehouse = _default_warehouse()
    items = {}
    for name, price in FUELS:
        code = f"FUEL-{name.replace(' ', '')}"
        if not frappe.db.exists("Item", code):
            frappe.get_doc({
                "doctype": "Item", "item_code": code, "item_name": name,
                "item_group": ITEM_GROUP if frappe.db.exists("Item Group", ITEM_GROUP)
                else "All Item Groups",
                "stock_uom": UOM, "is_stock_item": 1,
            }).insert(ignore_permissions=True)
        items[name] = code
        if not frappe.db.exists("Item Price",
                                {"item_code": code, "price_list": PRICE_LIST, "selling": 1}):
            frappe.get_doc({
                "doctype": "Item Price", "item_code": code, "price_list": PRICE_LIST,
                "selling": 1, "price_list_rate": price, "currency": "SAR",
            }).insert(ignore_permissions=True)
    frappe.db.commit()
    return items, warehouse


# ============================================================ station equipment
def _ensure_station(code, name, city, items, warehouse):
    if not frappe.db.exists("Gas Station", code):
        frappe.get_doc({
            "doctype": "Gas Station", "station_code": code, "station_name": name,
            "enabled": 1, "is_demo": 1, "company": COMPANY, "city": city,
            "default_warehouse": warehouse, "default_cost_center": _default_cost_center(),
        }).insert(ignore_permissions=True)

    ctrl_code = f"CTRL-{code}"
    if not frappe.db.exists("PTS Controller", ctrl_code):
        frappe.get_doc({
            "doctype": "PTS Controller", "controller_code": ctrl_code,
            "controller_name": f"{name} PTS-2", "station": code, "enabled": 1,
            "is_demo": 1, "provider": "Mock", "connection_status": "Connected",
            "configuration_id": ctrl_code, "stale_after_seconds": 120,
            "last_communication_at": frappe.utils.now_datetime(),
        }).insert(ignore_permissions=True)

    # tanks (one per fuel)
    tank_by_fuel = {}
    for i, (fuel, _price) in enumerate(FUELS, start=1):
        tname = f"{code}-T{i}"
        if not frappe.db.exists("Gas Station Tank", tname):
            frappe.get_doc({
                "doctype": "Gas Station Tank", "station": code, "tank_number": str(i),
                "tank_name": f"{fuel} Tank", "pts_controller": ctrl_code, "enabled": 1,
                "erpnext_item": items[fuel], "warehouse": warehouse,
                "capacity": 30000,
            }).insert(ignore_permissions=True)
        tank_by_fuel[fuel] = tname

    # probes (one per tank)
    for i, (fuel, _price) in enumerate(FUELS, start=1):
        pid = f"P{i}"
        pname = f"{code}-PR-{pid}"
        if not frappe.db.exists("Gas Station Probe", pname):
            frappe.get_doc({
                "doctype": "Gas Station Probe", "station": code, "probe_id": pid,
                "probe_type": "Multi Parameter", "tank": tank_by_fuel[fuel],
                "pts_controller": ctrl_code, "enabled": 1, "status": "Online",
                "supports_level": 1, "supports_water": 1, "supports_temperature": 1,
                "supports_density": 1,
            }).insert(ignore_permissions=True)

    # pumps (2) with nozzles for each fuel
    for pnum in range(1, 3):
        pname = f"{code}-P{pnum}"
        if not frappe.db.exists("Gas Station Pump", pname):
            pump = frappe.get_doc({
                "doctype": "Gas Station Pump", "station": code, "pump_number": str(pnum),
                "pts_controller": ctrl_code, "enabled": 1,
                "description": f"Dispenser {pnum}",
            })
            for nz, (fuel, _price) in enumerate(FUELS, start=1):
                pump.append("nozzles", {
                    "nozzle_number": nz, "erpnext_item": items[fuel],
                    "fuel_grade_name": fuel, "tank": tank_by_fuel[fuel], "enabled": 1,
                })
            pump.insert(ignore_permissions=True)

    # mock controller
    mock_name = f"MOCK-{code}"
    if not frappe.db.exists("Mock PTS Controller", mock_name):
        frappe.get_doc({
            "doctype": "Mock PTS Controller", "mock_name": mock_name,
            "pts_controller": ctrl_code, "enabled": 1, "is_running": 0,
            "transaction_frequency_seconds": 20, "measurement_frequency_seconds": 60,
            "alert_probability": 3,
        }).insert(ignore_permissions=True)
    frappe.db.commit()
    return mock_name


# ============================================================ history via pipeline
def seed_demo_data(days=3, txns_per_day=24):
    days = int(days); txns_per_day = int(txns_per_day)
    frappe.flags.in_demo = True
    print(f"[gas_station] seeding demo: company + {len(STATIONS)} stations, "
          f"{days} days x ~{txns_per_day} txns/station/day")

    _ensure_company()
    items, warehouse = _ensure_items()

    mocks = []
    for code, name, city in STATIONS:
        mocks.append(_ensure_station(code, name, city, items, warehouse))

    # seed an opening tank measurement so state exists and totalizers start clean
    for m in mocks:
        sim.generate_measurement(m)

    total = 0
    for d in range(days, 0, -1):
        day = get_datetime(add_days(nowdate(), -d) + " 06:00:00")
        for m in mocks:
            # a delivery every couple of days keeps tank balances realistic
            if d % 2 == 0:
                sim.generate_delivery(m, when=day)
            for t in range(txns_per_day):
                when = add_to_date(day, minutes=int(t * (16 * 60 / txns_per_day)))
                sim.generate_transaction(m, when=when)
                total += 1
            # a few measurements through the day
            for h in (0, 6, 12):
                sim.generate_measurement(m, when=add_to_date(day, hours=h))
        frappe.db.commit()

    # occasional alerts
    for m in mocks[:3]:
        sim.generate_alert(m)
    frappe.db.commit()

    _seed_reconciliation_examples()
    print(f"[gas_station] done. ~{total} transactions across {len(STATIONS)} stations. "
          "Open the Gas Station Dashboard.")


def _seed_reconciliation_examples():
    """Best-effort: create Sales Invoices for a subset (so reconciliation has
    matches) and force one amount mismatch. Skipped cleanly if POS masters are
    missing on this bench."""
    try:
        from gas_station.gas_station.erpnext_integration import mapping
        settings = frappe.get_single("Gas Station Settings")
        cust = _ensure_walkin_customer()
        settings.default_customer = cust
        settings.selling_price_list = PRICE_LIST
        settings.auto_create_sales_invoice = 1
        settings.update_stock_on_sale = 0  # avoid stock-availability failures in demo
        settings.save(ignore_permissions=True)
        frappe.db.commit()

        names = frappe.get_all("PTS Pump Transaction",
                               filters={"processing_status": "Received"},
                               pluck="name", limit=30)
        made = 0
        for n in names:
            try:
                mapping.process_pump_transaction(n)
                made += 1
            except Exception:
                frappe.db.rollback()
        # force one mismatch
        linked = frappe.get_all("PTS Pump Transaction",
                                filters={"erpnext_doctype": "Sales Invoice"},
                                fields=["name", "erpnext_reference"], limit=1)
        if linked:
            frappe.db.set_value("PTS Pump Transaction", linked[0].name,
                                "reconciliation_status", "Pending")
        frappe.db.commit()
        print(f"[gas_station] created {made} demo Sales Invoices for reconciliation.")
    except Exception:
        print("[gas_station] skipped Sales Invoice demo (POS masters not present). "
              "Operational demo is fully seeded.")
        frappe.db.rollback()


def _ensure_walkin_customer():
    name = "Walk-in Customer (Demo)"
    if not frappe.db.exists("Customer", name):
        frappe.get_doc({
            "doctype": "Customer", "customer_name": name,
            "customer_group": frappe.db.get_value("Customer Group",
                {"is_group": 0}) or "All Customer Groups",
            "territory": frappe.db.get_value("Territory", {"is_group": 0})
            or "All Territories",
        }).insert(ignore_permissions=True)
    return name


# ============================================================ reset
def reset_demo_data():
    """Delete demo stations and everything generated for them. Leaves the demo
    Company/Items/Prices in place (reusable, harmless)."""
    stations = frappe.get_all("Gas Station", filters={"is_demo": 1}, pluck="name")
    if not stations:
        print("[gas_station] no demo stations found.")
        return
    controllers = frappe.get_all("PTS Controller", filters={"station": ["in", stations]},
                                 pluck="name")

    # history + state first (FK-free, but order keeps logs clean)
    for dt in ("PTS Pump Transaction", "Tank Measurement", "Tank Delivery",
               "Station Alert", "Integration Event", "Pump State", "Tank State"):
        for n in frappe.get_all(dt, filters={"station": ["in", stations]}, pluck="name"):
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
    for n in frappe.get_all("Controller Connection State",
                            filters={"controller": ["in", controllers]}, pluck="name"):
        frappe.delete_doc("Controller Connection State", n, force=1, ignore_permissions=True)
    for dt in ("Mock PTS Controller",):
        for n in frappe.get_all(dt, filters={"pts_controller": ["in", controllers]},
                                pluck="name"):
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
    for dt in ("Gas Station Pump", "Gas Station Probe", "Gas Station Tank"):
        for n in frappe.get_all(dt, filters={"station": ["in", stations]}, pluck="name"):
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
    for c in controllers:
        frappe.delete_doc("PTS Controller", c, force=1, ignore_permissions=True)
    for s in stations:
        frappe.delete_doc("Gas Station", s, force=1, ignore_permissions=True)
    frappe.db.commit()
    print(f"[gas_station] removed {len(stations)} demo stations and their data.")
