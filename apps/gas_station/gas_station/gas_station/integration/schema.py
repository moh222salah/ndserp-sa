"""jsonPTS payload validation. Uses jsonschema when available, else a light
required-keys fallback so the app still works if the dep isn't installed."""
import frappe

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover
    _HAS_JSONSCHEMA = False

_NUM = {"type": ["number", "string", "null"]}

ENVELOPE = {
    "type": "object",
    "required": ["controller", "operation", "data"],
    "properties": {
        "controller": {"type": "string"},
        "operation": {"type": "string"},
        "packet_id": {"type": ["string", "number", "null"]},
        "data": {"type": "object"},
    },
}

DATA_SCHEMAS = {
    "UploadPumpTransaction": {
        "type": "object",
        "required": ["transaction_id", "pump", "volume", "amount"],
        "properties": {
            "transaction_id": {"type": ["string", "number"]},
            "pump": {"type": ["string", "number"]},
            "nozzle": {"type": ["string", "number", "null"]},
            "volume": _NUM, "amount": _NUM, "price": _NUM,
        },
    },
    "UploadTankMeasurement": {
        "type": "object",
        "required": ["tank"],
        "properties": {"tank": {"type": ["string", "number"]}},
    },
    "UploadInTankDelivery": {
        "type": "object",
        "required": ["tank", "delivery_id"],
        "properties": {"tank": {"type": ["string", "number"]}},
    },
    "UploadAlertRecord": {
        "type": "object",
        "required": ["alert_type"],
        "properties": {"alert_type": {"type": "string"}},
    },
    "UploadStatus": {"type": "object"},
    "UploadConfiguration": {"type": "object"},
}


class SchemaError(frappe.ValidationError):
    pass


def validate(envelope: dict):
    operation = envelope.get("operation")
    if _HAS_JSONSCHEMA:
        try:
            jsonschema.validate(envelope, ENVELOPE)
            if operation in DATA_SCHEMAS:
                jsonschema.validate(envelope.get("data") or {}, DATA_SCHEMAS[operation])
        except jsonschema.ValidationError as e:
            raise SchemaError(f"Schema validation failed: {e.message}")
    else:
        for k in ENVELOPE["required"]:
            if k not in envelope:
                raise SchemaError(f"Missing envelope key: {k}")
        for k in DATA_SCHEMAS.get(operation, {}).get("required", []):
            if k not in (envelope.get("data") or {}):
                raise SchemaError(f"Missing data key for {operation}: {k}")
    return True
