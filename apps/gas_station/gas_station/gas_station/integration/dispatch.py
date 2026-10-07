"""Central receive pipeline. Separates ACK (persist + dedupe) from business
processing (enqueued). A PTS transaction is never lost on ERPNext failure."""
import json
import time
import frappe

from gas_station.gas_station.integration import schema, auth, idempotency
from gas_station.gas_station.integration.handlers.pump_transaction import PumpTransactionHandler
from gas_station.gas_station.integration.handlers.tank_measurement import TankMeasurementHandler
from gas_station.gas_station.integration.handlers.tank_delivery import TankDeliveryHandler
from gas_station.gas_station.integration.handlers.alert import AlertHandler
from gas_station.gas_station.integration.handlers.status import StatusHandler
from gas_station.gas_station.integration.handlers.configuration import ConfigurationHandler

HANDLERS = {
    "UploadPumpTransaction": PumpTransactionHandler,
    "UploadTankMeasurement": TankMeasurementHandler,
    "UploadInTankDelivery": TankDeliveryHandler,
    "UploadAlertRecord": AlertHandler,
    "UploadStatus": StatusHandler,
    "UploadConfiguration": ConfigurationHandler,
}


def receive(envelope: dict, raw_body: str = None, signature: str = None):
    """Entry point for both Mock and Real providers. Returns an ACK dict."""
    t0 = time.time()
    operation = (envelope or {}).get("operation")
    data = (envelope or {}).get("data") or {}

    event = frappe.get_doc({
        "doctype": "Integration Event",
        "event_type": operation if operation in HANDLERS else None,
        "direction": "Inbound",
        "status": "Received",
        "packet_id": str(envelope.get("packet_id")) if envelope.get("packet_id") else None,
        "transaction_id": str(data.get("transaction_id")) if data.get("transaction_id") else None,
        "received_at": frappe.utils.now_datetime(),
        "payload": json.dumps(envelope)[:130000],
    })
    event.insert(ignore_permissions=True)

    try:
        schema.validate(envelope)
        if operation not in HANDLERS:
            raise schema.SchemaError(f"Unsupported operation: {operation}")

        controller = auth.identify_controller(envelope)
        auth.verify(controller, raw_body, signature)
        event.db_set("station", controller.station, update_modified=False)
        event.db_set("pts_controller", controller.name, update_modified=False)

        if idempotency.is_duplicate(operation, controller, data):
            event.db_set("status", "Duplicate", update_modified=False)
            _finish(event, t0)
            return _ack("duplicate", operation, event.name)

        handler = HANDLERS[operation](controller, data, envelope)
        doc = handler.persist()
        handler.update_state(doc)
        controller.mark_seen(data.get("firmware_version"))
        _touch_connection(controller, success=True, latency=(time.time() - t0) * 1000)

        # ACK now; business (ERPNext) runs in the background.
        handler.enqueue_business(doc)

        event.db_set("status", "Processed", update_modified=False)
        _finish(event, t0)
        return _ack("ok", operation, event.name, doc.name if doc else None)

    except (auth.UnknownController, auth.AuthError, schema.SchemaError) as e:
        _fail(event, t0, str(e), code="VALIDATION")
        return _ack("rejected", operation, event.name, error=str(e))
    except Exception as e:  # keep the raw event; nothing is lost
        frappe.db.rollback()
        event.reload()
        _fail(event, t0, frappe.get_traceback(limit=5) or str(e), code="ERROR")
        return _ack("error", operation, event.name, error=str(e))


def _touch_connection(controller, success, latency=None, error=None):
    name = frappe.db.get_value("Controller Connection State", {"controller": controller.name})
    vals = {"connection_status": "Connected" if success else "Disconnected"}
    now = frappe.utils.now_datetime()
    if success:
        vals.update({"last_success_at": now, "last_status_received_at": now,
                     "consecutive_failures": 0})
        if latency is not None:
            vals["latency_ms"] = round(latency, 1)
    else:
        vals.update({"last_failure_at": now, "last_error": (error or "")[:500]})
    if name:
        cs = frappe.get_doc("Controller Connection State", name)
        if not success:
            vals["consecutive_failures"] = (cs.consecutive_failures or 0) + 1
        frappe.db.set_value("Controller Connection State", name, vals, update_modified=False)
    else:
        frappe.get_doc({"doctype": "Controller Connection State",
                        "controller": controller.name, "station": controller.station,
                        **vals}).insert(ignore_permissions=True)


def _finish(event, t0):
    event.db_set("processed_at", frappe.utils.now_datetime(), update_modified=False)
    event.db_set("processing_duration", round((time.time() - t0) * 1000, 1),
                 update_modified=False)


def _fail(event, t0, message, code=None):
    event.db_set("status", "Failed", update_modified=False)
    event.db_set("error_code", code, update_modified=False)
    event.db_set("error_message", message[:1000], update_modified=False)
    _finish(event, t0)
    frappe.db.commit()


def _ack(status, operation, event, ref=None, error=None):
    ack = {"ack": status, "operation": operation, "event": event}
    if ref:
        ack["reference"] = ref
    if error:
        ack["error"] = error
    return ack
