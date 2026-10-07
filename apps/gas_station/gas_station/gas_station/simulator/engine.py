"""Mock PTS-2 simulator. Generates realistic Saudi station telemetry and feeds it
through the SAME dispatch pipeline as real PTS data (spec §18/§41/§42).
No fake dashboard rows — everything goes through MockPTSProvider -> dispatch."""
import random
import time
import frappe
from frappe.utils import now_datetime, flt, add_to_date
from gas_station.gas_station.integration.providers.mock import MockPTSProvider

_PROVIDER = MockPTSProvider()

DEMO_PRICES = {"Gasoline 91": 2.18, "Gasoline 95": 2.33, "Diesel": 1.66}


# --------------------------------------------------------------------------- helpers
def _mock(mock_name):
    return frappe.get_doc("Mock PTS Controller", mock_name)


def _controller_code(mock):
    return frappe.db.get_value("PTS Controller", mock.pts_controller, "controller_code")


def _station(mock):
    return frappe.db.get_value("PTS Controller", mock.pts_controller, "station")


def _price(item):
    if not item:
        return None
    p = frappe.db.get_value("Item Price",
                            {"item_code": item, "selling": 1}, "price_list_rate")
    if p:
        return flt(p)
    name = frappe.db.get_value("Item", item, "item_name") or ""
    for k, v in DEMO_PRICES.items():
        if k in name:
            return v
    return 2.0


def _pick_pump_nozzle(station):
    pumps = frappe.get_all("Gas Station Pump",
                           filters={"station": station, "enabled": 1}, pluck="name")
    if not pumps:
        return None
    pump = frappe.get_doc("Gas Station Pump", random.choice(pumps))
    nozzles = [n for n in pump.nozzles if n.enabled]
    if not nozzles:
        return None
    return pump, random.choice(nozzles)


def _submit(mock, controller_code, operation, data, force_duplicate=False):
    # fault injection
    if mock.simulate_transaction_failures and random.random() < 0.05:
        data["amount"] = None  # will fail schema -> stays as failed Integration Event
    if mock.simulate_delayed_packets and random.random() < 0.1:
        time.sleep(0.2)
    ack = _PROVIDER.submit(operation, controller_code, dict(data))
    if (force_duplicate or (mock.simulate_duplicate_packets and random.random() < 0.05)):
        _PROVIDER.submit(operation, controller_code, dict(data))  # retry same id
    return ack


# --------------------------------------------------------------------------- generators
def generate_transaction(mock_name, when=None):
    mock = _mock(mock_name)
    station = _station(mock)
    code = _controller_code(mock)
    pick = _pick_pump_nozzle(station)
    if not pick:
        return "No enabled pump/nozzle at this station."
    pump, nozzle = pick

    volume = round(random.uniform(8, 60), 2)
    price = _price(nozzle.erpnext_item)
    amount = round(volume * price, 2)

    # coherent monotonic totalizer from current Pump State
    ps = frappe.db.get_value("Pump State", pump.name,
                             ["totalizer_volume", "totalizer_amount"], as_dict=True)
    tot_v = flt(ps.totalizer_volume) + volume if ps else volume
    tot_a = flt(ps.totalizer_amount) + amount if ps else amount

    start = when or now_datetime()
    txn_id = f"PTS-{start.strftime('%Y%m%d')}-{random.randint(1, 999999):06d}"
    data = {
        "transaction_id": txn_id, "pump": pump.pump_number,
        "nozzle": nozzle.nozzle_number, "tank": nozzle.tank,
        "fuel_grade": nozzle.fuel_grade_name, "volume": volume, "price": price,
        "amount": amount, "total_volume": round(tot_v, 2), "total_amount": round(tot_a, 2),
        "flow_rate": round(random.uniform(30, 45), 1),
        "start_datetime": str(start), "end_datetime": str(add_to_date(start, minutes=2)),
        "is_paid": 1, "shift_number": "1",
    }
    return _submit(mock, code, "UploadPumpTransaction", data)


def generate_measurement(mock_name, when=None):
    mock = _mock(mock_name)
    station = _station(mock)
    code = _controller_code(mock)
    tanks = frappe.get_all("Gas Station Tank",
                           filters={"station": station, "enabled": 1},
                           fields=["name", "tank_number", "capacity"])
    if not tanks:
        return "No tanks."
    tk = random.choice(tanks)
    ts = frappe.db.get_value("Tank State", tk.name,
                             ["product_volume", "water_volume", "temperature"], as_dict=True)
    cap = flt(tk.capacity) or 30000
    prod = flt(ts.product_volume) if ts and ts.product_volume else cap * 0.6
    prod = max(cap * 0.1, prod - random.uniform(0, 80))  # drifts down between deliveries
    data = {
        "tank": tk.tank_number,
        "measurement_datetime": str(when or now_datetime()),
        "product_volume": round(prod, 1),
        "product_level": round(prod / cap * 2000, 1),
        "water_volume": round(random.uniform(0, 40), 1),
        "water_level": round(random.uniform(0, 20), 1),
        "temperature": round(random.uniform(24, 34), 1),
        "density": round(random.uniform(720, 760), 1),
        "ullage": round(cap - prod, 1),
    }
    return _submit(mock, code, "UploadTankMeasurement", data)


def generate_alert(mock_name):
    mock = _mock(mock_name)
    code = _controller_code(mock)
    kind = random.choice([
        ("Tank Low Level", "Warning", "Tank"), ("High Water", "Critical", "Tank"),
        ("Pump Offline", "Critical", "Pump"), ("High Temperature", "Warning", "Tank"),
        ("Probe Failure", "Warning", "Probe")])
    data = {"alert_type": kind[0], "severity": kind[1], "equipment_type": kind[2],
            "message": f"{kind[0]} detected by simulator.",
            "occurred_at": str(now_datetime())}
    return _submit(mock, code, "UploadAlertRecord", data)


def generate_delivery(mock_name, when=None):
    mock = _mock(mock_name)
    station = _station(mock)
    code = _controller_code(mock)
    tanks = frappe.get_all("Gas Station Tank",
                           filters={"station": station, "enabled": 1},
                           fields=["name", "tank_number", "capacity"])
    if not tanks:
        return "No tanks."
    tk = random.choice(tanks)
    ts = frappe.db.get_value("Tank State", tk.name, "product_volume")
    opening = flt(ts) or flt(tk.capacity) * 0.3
    delivered = round(random.uniform(5000, 15000), 1)
    start = when or now_datetime()
    data = {"tank": tk.tank_number, "delivery_id": f"DEL-{random.randint(1, 999999):06d}",
            "start_datetime": str(start), "end_datetime": str(add_to_date(start, minutes=40)),
            "opening_volume": round(opening, 1), "delivery_volume": delivered,
            "closing_volume": round(opening + delivered, 1),
            "temperature": round(random.uniform(24, 30), 1)}
    return _submit(mock, code, "UploadInTankDelivery", data)


def set_connection(controller, up=True):
    status = "Connected" if up else "Disconnected"
    frappe.db.set_value("PTS Controller", controller, "connection_status", status)
    if not up:
        for dt in ("Pump State", "Tank State"):
            for n in frappe.get_all(dt, filters={"pts_controller": controller}, pluck="name"):
                frappe.db.set_value(dt, n, "communication_status", "Offline",
                                    update_modified=False)
    else:
        frappe.db.set_value("PTS Controller", controller,
                            "last_communication_at", now_datetime())
    frappe.db.commit()
    return f"Connection {'restored' if up else 'lost'} for {controller}."


# --------------------------------------------------------------------------- scheduler
def tick():
    """Runs every minute. For each running mock, emits due packets. Controlled:
    one bounded batch per tick, never an unbounded job storm."""
    running = frappe.get_all("Mock PTS Controller",
                             filters={"enabled": 1, "is_running": 1},
                             fields=["name", "transaction_frequency_seconds",
                                     "measurement_frequency_seconds", "alert_probability",
                                     "last_tick_at", "simulate_connection_failures"])
    now = now_datetime()
    for m in running:
        try:
            _tick_one(m, now)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "gas_station simulator tick")
    frappe.db.commit()


def _tick_one(m, now):
    txn_freq = max(5, m.transaction_frequency_seconds or 20)
    # emit a bounded number of transactions for the elapsed minute
    n_txn = min(12, max(1, int(60 / txn_freq)))
    for _ in range(n_txn):
        generate_transaction(m.name)
    # one measurement round per due interval
    if (m.measurement_frequency_seconds or 60) <= 60:
        generate_measurement(m.name)
    if random.random() < flt(m.alert_probability) / 100.0:
        generate_alert(m.name)
    if m.simulate_connection_failures and random.random() < 0.02:
        code = frappe.db.get_value("Mock PTS Controller", m.name, "pts_controller")
        set_connection(code, up=False)
    frappe.db.set_value("Mock PTS Controller", m.name, "last_tick_at", now,
                        update_modified=False)
