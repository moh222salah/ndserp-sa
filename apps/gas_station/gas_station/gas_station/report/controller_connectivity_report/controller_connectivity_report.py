import frappe
from gas_station.gas_station.report.gas_report_utils import col


def execute(filters=None):
    conds = {}
    if (filters or {}).get("station"):
        conds["station"] = filters["station"]
    rows = frappe.db.get_all("Controller Connection State", filters=conds,
        fields=["controller", "station", "connection_status", "consecutive_failures",
                "latency_ms", "last_success_at", "last_failure_at",
                "last_status_received_at"], order_by="connection_status asc")
    columns = [col("Controller", "controller", "Link", 160, "PTS Controller"),
               col("Station", "station", "Link", 140, "Gas Station"),
               col("Status", "connection_status", "Data", 110),
               col("Failures", "consecutive_failures", "Int", 90),
               col("Latency (ms)", "latency_ms", "Float", 110),
               col("Last Success", "last_success_at", "Datetime", 160),
               col("Last Failure", "last_failure_at", "Datetime", 160)]
    return columns, rows
