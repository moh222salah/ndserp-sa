import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    rows = frappe.db.get_all("Tank Delivery", filters=conds,
        fields=["name", "start_datetime", "station", "tank", "delivery_id",
                "opening_volume", "delivery_volume", "closing_volume", "status",
                "reconciliation_status"], order_by="start_datetime desc")
    columns = [col("Delivery", "name", "Link", 130, "Tank Delivery"),
               col("Start", "start_datetime", "Datetime", 150),
               col("Station", "station", "Link", 140, "Gas Station"),
               col("Tank", "tank", "Link", 120, "Gas Station Tank"),
               col("Opening (L)", "opening_volume", "Float", 110),
               col("Delivered (L)", "delivery_volume", "Float", 120),
               col("Closing (L)", "closing_volume", "Float", 110),
               col("Status", "status", "Data", 100),
               col("Recon", "reconciliation_status", "Data", 100)]
    return columns, rows
