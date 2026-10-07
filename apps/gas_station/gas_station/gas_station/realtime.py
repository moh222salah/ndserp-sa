"""Realtime push helpers. Browsers never talk to the PTS controller directly;
they receive updates the app publishes."""
import frappe

EVENT = "gas_station_update"


def _emit(station, kind, payload):
    try:
        frappe.publish_realtime(EVENT, {"kind": kind, "station": station,
                                        "payload": payload}, after_commit=True)
    except Exception:
        pass  # realtime is best-effort; never break ingestion


def publish_pump(station, pump, state):
    _emit(station, "pump", {"pump": pump, "status": state.status,
                            "volume": state.current_volume,
                            "amount": state.current_amount})


def publish_tank(station, tank, state):
    _emit(station, "tank", {"tank": tank, "fill": state.fill_percentage,
                            "volume": state.product_volume,
                            "temperature": state.temperature})


def publish_alert(station, alert):
    _emit(station, "alert", {"name": alert.name, "severity": alert.severity,
                             "type": alert.alert_type, "message": alert.message})
