import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters, date_field="occurred_at")
    for k in ("severity", "status"):
        if (filters or {}).get(k):
            conds[k] = filters[k]
    rows = frappe.db.get_all("Station Alert", filters=conds,
        fields=["name", "occurred_at", "station", "alert_type", "severity", "status",
                "equipment_reference", "message"], order_by="occurred_at desc", limit=2000)
    columns = [col("Alert", "name", "Link", 140, "Station Alert"),
               col("Occurred", "occurred_at", "Datetime", 150),
               col("Station", "station", "Link", 130, "Gas Station"),
               col("Type", "alert_type", "Data", 130),
               col("Severity", "severity", "Data", 90),
               col("Status", "status", "Data", 100),
               col("Equipment", "equipment_reference", "Data", 120),
               col("Message", "message", "Data", 220)]
    return columns, rows
