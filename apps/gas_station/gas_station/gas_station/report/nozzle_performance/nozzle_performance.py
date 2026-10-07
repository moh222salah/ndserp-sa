import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    rows = frappe.db.get_all("PTS Pump Transaction", filters=conds,
        fields=["station", "pump", "nozzle", "fuel_grade", "count(name) as txns",
                "volume", "amount"],
        group_by="station, pump, nozzle", order_by="volume desc")
    columns = [col("Station", "station", "Link", 150, "Gas Station"),
               col("Pump", "pump", "Data", 90), col("Nozzle", "nozzle", "Data", 90),
               col("Fuel", "fuel_grade", "Data", 120),
               col("Transactions", "txns", "Int", 110),
               col("Volume (L)", "volume", "Float", 120),
               col("Amount", "amount", "Currency", 120)]
    return columns, rows
