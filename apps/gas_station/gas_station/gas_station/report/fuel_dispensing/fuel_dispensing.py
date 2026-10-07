import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    rows = frappe.db.get_all("PTS Pump Transaction", filters=conds,
        fields=["erpnext_item", "fuel_grade", "count(name) as txns",
                "volume", "amount",
                "avg(price) as avg_price"],
        group_by="erpnext_item", order_by="volume desc")
    columns = [col("Fuel Item", "erpnext_item", "Link", 160, "Item"),
               col("Grade", "fuel_grade", "Data", 120),
               col("Transactions", "txns", "Int", 110),
               col("Volume (L)", "volume", "Float", 130),
               col("Amount", "amount", "Currency", 130),
               col("Avg Price", "avg_price", "Float", 110)]
    return columns, rows
