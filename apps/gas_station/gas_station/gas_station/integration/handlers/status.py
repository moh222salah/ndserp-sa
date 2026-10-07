import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler


class StatusHandler(BaseHandler):
    """Controller heartbeat / equipment status snapshot."""
    operation = "UploadStatus"

    def persist(self):
        # StatusHandler updates state only; the raw event is already stored by
        # dispatch as an Integration Event. Return None (no history doctype).
        return None

    def update_state(self, doc):
        self.controller.mark_seen(self.data.get("firmware_version"))
        # optionally reflect per-pump status if provided
        for p in (self.data.get("pumps") or []):
            pump_name = frappe.db.get_value(
                "Gas Station Pump",
                {"station": self.station, "pump_number": str(p.get("pump"))})
            if pump_name and frappe.db.exists("Pump State", pump_name):
                frappe.db.set_value("Pump State", pump_name, {
                    "status": p.get("status") or "Idle",
                    "communication_status": "Live",
                    "last_updated_at": frappe.utils.now_datetime(),
                }, update_modified=False)
