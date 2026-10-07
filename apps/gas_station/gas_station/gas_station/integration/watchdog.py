"""Scheduled: flag controllers/equipment as Stale when no packet has arrived
within the configured window. Never resets values to zero — only marks staleness."""
import frappe


def mark_stale_controllers():
    now = frappe.utils.now_datetime()
    for c in frappe.get_all("PTS Controller",
                            filters={"enabled": 1},
                            fields=["name", "station", "last_communication_at",
                                    "stale_after_seconds", "connection_status"]):
        window = c.stale_after_seconds or 120
        last = c.last_communication_at
        stale = (not last) or (now - last).total_seconds() > window
        new_status = "Stale" if stale else "Connected"
        if new_status != c.connection_status:
            frappe.db.set_value("PTS Controller", c.name, "connection_status",
                                new_status, update_modified=False)
            _mark_equipment(c.station, c.name, stale)
    frappe.db.commit()


def _mark_equipment(station, controller, stale):
    comm = "Stale" if stale else "Live"
    for dt, link in (("Pump State", "pts_controller"), ("Tank State", "pts_controller")):
        for name in frappe.get_all(dt, filters={link: controller}, pluck="name"):
            frappe.db.set_value(dt, name, "communication_status", comm,
                                update_modified=False)
