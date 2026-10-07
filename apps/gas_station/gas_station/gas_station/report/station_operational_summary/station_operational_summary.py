import frappe
from gas_station.gas_station.report.gas_report_utils import base_filters, col


def execute(filters=None):
    conds = base_filters(filters)
    txn = frappe.db.get_all("PTS Pump Transaction", filters=conds,
        fields=["station", "count(name) as txns", "volume",
                "amount"], group_by="station")
    by_station = {r.station: r for r in txn}
    rows = []
    for st in frappe.get_all("Gas Station", filters=(
            {"name": filters["station"]} if (filters or {}).get("station") else {}),
            fields=["name", "city"]):
        t = by_station.get(st.name)
        alerts = frappe.db.count("Station Alert", {"station": st.name, "status": "Open"})
        tanks = frappe.db.get_all("Tank State", filters={"station": st.name},
                                  fields=["sum(product_volume) as v"])
        rows.append({
            "station": st.name, "city": st.city,
            "transactions": t.txns if t else 0,
            "volume": t.volume if t else 0, "amount": t.amount if t else 0,
            "open_alerts": alerts, "tank_stock": (tanks[0].v if tanks else 0)})
    columns = [col("Station", "station", "Link", 170, "Gas Station"),
               col("City", "city", "Data", 110),
               col("Transactions", "transactions", "Int", 110),
               col("Volume (L)", "volume", "Float", 120),
               col("Revenue", "amount", "Currency", 120),
               col("Open Alerts", "open_alerts", "Int", 100),
               col("Tank Stock (L)", "tank_stock", "Float", 130)]
    return columns, rows
