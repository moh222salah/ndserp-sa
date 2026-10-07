from gas_station.gas_station.reconciliation import engine
from gas_station.gas_station.report.gas_report_utils import col


def execute(filters=None):
    filters = filters or {}
    rows = []
    if filters.get("station") and filters.get("from_date") and filters.get("to_date"):
        rows = engine._pts_vs_sales(filters["station"], filters["from_date"],
                                    filters["to_date"])
    columns = [col("Transaction", "reference", "Data", 200),
               col("PTS Amount", "expected", "Currency", 130),
               col("ERPNext Amount", "actual", "Currency", 140),
               col("Variance", "variance", "Currency", 120),
               col("Status", "status", "Data", 160)]
    return columns, rows
