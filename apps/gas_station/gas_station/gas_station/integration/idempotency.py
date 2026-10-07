"""Deduplication + DB-level uniqueness. Python checks are a first line; the real
guarantee is the unique indexes created by ensure_unique_indexes()."""
import frappe

# (table, [columns], index_name)
UNIQUE_INDEXES = [
    ("tabPTS Pump Transaction", ["pts_controller", "pts_transaction_id"], "uniq_pts_txn"),
    ("tabTank Delivery", ["pts_controller", "delivery_id"], "uniq_tank_delivery"),
]


def duplicate_key(operation, controller, data):
    if operation == "UploadPumpTransaction":
        return {"pts_controller": controller.name,
                "pts_transaction_id": str(data.get("transaction_id"))}
    if operation == "UploadInTankDelivery":
        return {"pts_controller": controller.name,
                "delivery_id": str(data.get("delivery_id"))}
    return None


def is_duplicate(operation, controller, data):
    key = duplicate_key(operation, controller, data)
    if not key:
        return False
    doctype = {"UploadPumpTransaction": "PTS Pump Transaction",
               "UploadInTankDelivery": "Tank Delivery"}[operation]
    return bool(frappe.db.exists(doctype, key))


def ensure_unique_indexes():
    """Idempotently add composite unique indexes. Safe to run every migrate."""
    for table, cols, idx in UNIQUE_INDEXES:
        exists = frappe.db.sql(
            """select 1 from information_schema.statistics
               where table_schema = database() and table_name = %s
               and index_name = %s limit 1""", (table, idx))
        if exists:
            continue
        collist = ", ".join(f"`{c}`" for c in cols)
        try:
            frappe.db.sql_ddl(
                f"alter table `{table}` add unique index `{idx}` ({collist})")
            frappe.logger().info(f"[gas_station] created unique index {idx}")
        except Exception as e:  # duplicates already present, or race
            frappe.log_error(f"Could not create {idx}: {e}", "gas_station idempotency")
