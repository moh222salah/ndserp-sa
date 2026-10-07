import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters, date_field="measurement_datetime")
    if (filters or {}).get("tank"):
        conds["tank"] = filters["tank"]
    rows = frappe.db.get_all("Tank Measurement", filters=conds,
        fields=["measurement_datetime", "station", "tank", "product_volume",
                "product_level", "water_level", "temperature", "ullage"],
        order_by="measurement_datetime desc", limit=2000)
    columns = [col("Measured At", "measurement_datetime", "Datetime", 160),
               col("Station", "station", "Link", 140, "Gas Station"),
               col("Tank", "tank", "Link", 130, "Gas Station Tank"),
               col("Volume (L)", "product_volume", "Float", 120),
               col("Level (mm)", "product_level", "Float", 110),
               col("Water (mm)", "water_level", "Float", 110),
               col("Temp (°C)", "temperature", "Float", 100),
               col("Ullage (L)", "ullage", "Float", 110)]
    return columns, rows
