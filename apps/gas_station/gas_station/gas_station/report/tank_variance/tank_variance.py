from gas_station.gas_station.reconciliation import engine
from gas_station.gas_station.report.gas_report_utils import col


def execute(filters=None):
    filters = filters or {}
    rows = []
    if filters.get("station") and filters.get("from_date") and filters.get("to_date"):
        rows = engine._tank_balance(filters["station"], filters["from_date"],
                                    filters["to_date"])
    columns = [col("Tank", "reference", "Data", 130),
               col("Expected (L)", "expected", "Float", 130),
               col("Actual (L)", "actual", "Float", 130),
               col("Variance (L)", "variance", "Float", 130),
               col("Var %", "variance_pct", "Percent", 100),
               col("Status", "status", "Data", 140)]
    return columns, rows
