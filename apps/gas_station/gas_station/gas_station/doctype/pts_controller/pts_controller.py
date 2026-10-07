import frappe
from frappe.model.document import Document


class PTSController(Document):
    def validate(self):
        if self.provider == "Real" and not (self.hostname and self.port):
            frappe.throw("A Real PTS provider requires a hostname and port.")

    def mark_seen(self, firmware_version=None):
        """Called by the integration layer whenever a valid packet arrives."""
        self.db_set("last_communication_at", frappe.utils.now_datetime(),
                    update_modified=False)
        self.db_set("connection_status", "Connected", update_modified=False)
        if firmware_version:
            self.db_set("firmware_version", firmware_version, update_modified=False)
