import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters, date_field="received_at")
    for k in ("status", "event_type"):
        if (filters or {}).get(k):
            conds[k] = filters[k]
    rows = frappe.db.get_all("Integration Event", filters=conds,
        fields=["name", "received_at", "pts_controller", "event_type", "status",
                "processing_duration", "error_message"],
        order_by="received_at desc", limit=2000)
    columns = [col("Event", "name", "Link", 150, "Integration Event"),
               col("Received", "received_at", "Datetime", 150),
               col("Controller", "pts_controller", "Link", 140, "PTS Controller"),
               col("Type", "event_type", "Data", 170),
               col("Status", "status", "Data", 100),
               col("Duration (ms)", "processing_duration", "Float", 120),
               col("Error", "error_message", "Data", 240)]
    return columns, rows
