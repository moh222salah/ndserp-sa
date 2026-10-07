import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    if (filters or {}).get("processing_status"):
        conds["processing_status"] = filters["processing_status"]
    rows = frappe.db.get_all("PTS Pump Transaction", filters=conds,
        fields=["name", "start_datetime", "station", "pump", "nozzle", "fuel_grade",
                "volume", "amount", "processing_status", "reconciliation_status",
                "pts_transaction_id"], order_by="start_datetime desc", limit=2000)
    columns = [col("Txn", "name", "Link", 150, "PTS Pump Transaction"),
               col("Time", "start_datetime", "Datetime", 150),
               col("Station", "station", "Link", 130, "Gas Station"),
               col("Pump", "pump", "Data", 70), col("Nozzle", "nozzle", "Data", 70),
               col("Fuel", "fuel_grade", "Data", 110),
               col("Volume (L)", "volume", "Float", 100),
               col("Amount", "amount", "Currency", 110),
               col("Status", "processing_status", "Data", 100),
               col("Recon", "reconciliation_status", "Data", 120)]
    return columns, rows
