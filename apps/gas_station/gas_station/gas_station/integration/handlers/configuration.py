import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler


class ConfigurationHandler(BaseHandler):
    """Controller announces its configuration. We record firmware/version;
    equipment provisioning stays a deliberate admin action, not auto-created."""
    operation = "UploadConfiguration"

    def persist(self):
        return None

    def update_state(self, doc):
        self.controller.mark_seen(self.data.get("firmware_version"))
        if self.data.get("configuration_id"):
            self.controller.db_set(
                "configuration_id", str(self.data["configuration_id"]),
                update_modified=False)
