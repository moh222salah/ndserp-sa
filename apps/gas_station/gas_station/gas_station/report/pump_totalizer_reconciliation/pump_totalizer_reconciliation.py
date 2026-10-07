from gas_station.gas_station.reconciliation import engine
from gas_station.gas_station.report.gas_report_utils import col


def execute(filters=None):
    filters = filters or {}
    rows = []
    if filters.get("station") and filters.get("from_date") and filters.get("to_date"):
        rows = engine._pump_totalizer(filters["station"], filters["from_date"],
                                      filters["to_date"])
    columns = [col("Pump", "reference", "Data", 120),
               col("Summed Txn Vol (L)", "expected", "Float", 160),
               col("Totalizer Delta (L)", "actual", "Float", 160),
               col("Variance (L)", "variance", "Float", 130),
               col("Var %", "variance_pct", "Percent", 100),
               col("Status", "status", "Data", 140)]
    return columns, rows
