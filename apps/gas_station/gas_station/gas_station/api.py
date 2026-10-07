"""Public jsonPTS ingestion endpoints. A physical controller POSTs without a
Frappe session, so these allow guests but authenticate inside dispatch/auth
(controller credentials + optional HMAC). One endpoint per jsonPTS operation."""
import json
import frappe
from gas_station.gas_station.integration import dispatch


def _body_and_sig():
    raw = frappe.request.get_data(as_text=True) if getattr(frappe, "request", None) else None
    sig = None
    if getattr(frappe, "request", None):
        sig = frappe.request.headers.get("X-PTS-Signature")
    return raw, sig


def _ingest(operation):
    raw, sig = _body_and_sig()
    try:
        envelope = json.loads(raw) if raw else (frappe.local.form_dict or {})
    except json.JSONDecodeError as e:
        frappe.local.response["http_status_code"] = 400
        return {"ack": "rejected", "error": f"Malformed JSON: {e}"}
    if isinstance(envelope, dict):
        envelope.setdefault("operation", operation)
    ack = dispatch.receive(envelope, raw_body=raw, signature=sig)
    if ack.get("ack") in ("rejected",):
        frappe.local.response["http_status_code"] = 400
    return ack


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_pump_transaction():
    return _ingest("UploadPumpTransaction")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_tank_measurement():
    return _ingest("UploadTankMeasurement")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_in_tank_delivery():
    return _ingest("UploadInTankDelivery")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_alert_record():
    return _ingest("UploadAlertRecord")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_status():
    return _ingest("UploadStatus")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_configuration():
    return _ingest("UploadConfiguration")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload():
    """Generic endpoint: operation is read from the envelope body."""
    return _ingest(None)
