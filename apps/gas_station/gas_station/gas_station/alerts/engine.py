"""Rule-based alerting. Evaluates enabled Alert Rules against fresh state and
raises Station Alerts (deduped while an equivalent alert stays Open)."""
import frappe

_OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b}


def _rules(station, equipment_type):
    return frappe.get_all(
        "Alert Rule",
        filters={"enabled": 1, "equipment_type": equipment_type},
        or_filters=[["station", "=", station], ["station", "is", "not set"]],
        fields=["name", "station", "parameter", "operator", "threshold",
                "severity", "alert_type", "message_template"])


def _raise(station, rule, equipment, value):
    dup = frappe.db.exists("Station Alert", {
        "station": station, "alert_type": rule.get("alert_type") or rule["parameter"],
        "equipment_reference": equipment, "status": "Open"})
    if dup:
        return
    msg = (rule.get("message_template") or "{equipment}: {value} vs {threshold}") \
        .format(equipment=equipment, value=value, threshold=rule["threshold"])
    frappe.get_doc({
        "doctype": "Station Alert", "station": station, "source": "Rule",
        "alert_type": rule.get("alert_type") or rule["parameter"],
        "severity": rule.get("severity") or "Warning", "status": "Open",
        "occurred_at": frappe.utils.now_datetime(),
        "equipment_reference": equipment, "message": msg,
    }).insert(ignore_permissions=True)


def evaluate_tank(state):
    values = {"fill_percentage": state.fill_percentage,
              "product_level": state.product_level,
              "water_level": state.water_level,
              "temperature": state.temperature,
              "density": state.density}
    for rule in _rules(state.station, "Tank"):
        v = values.get(rule["parameter"])
        thr = rule.get("threshold")
        if v is None or thr is None:
            continue
        if _OPS[rule["operator"]](v, thr):
            _raise(state.station, rule, state.tank, v)
