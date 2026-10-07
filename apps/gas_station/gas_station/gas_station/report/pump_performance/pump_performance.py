import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    rows = frappe.db.get_all("PTS Pump Transaction", filters=conds,
        fields=["station", "pump", "count(name) as txns", "volume",
                "amount", "flow_rate"],
        group_by="station, pump", order_by="amount desc")
    columns = [col("Station", "station", "Link", 160, "Gas Station"),
               col("Pump", "pump", "Data", 100),
               col("Transactions", "txns", "Int", 110),
               col("Volume (L)", "volume", "Float", 120),
               col("Amount", "amount", "Currency", 120),
               col("Avg Flow", "avg_flow", "Float", 110)]
    return columns, rows
