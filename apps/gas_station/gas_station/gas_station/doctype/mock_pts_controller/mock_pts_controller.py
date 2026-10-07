import frappe
from frappe.model.document import Document
from gas_station.gas_station.simulator import engine as sim


class MockPTSController(Document):
    def validate(self):
        provider = frappe.db.get_value("PTS Controller", self.pts_controller, "provider")
        if provider != "Mock":
            frappe.msgprint(
                f"Controller {self.pts_controller} has provider '{provider}'. "
                "Set it to 'Mock' for the simulator to drive it.",
                indicator="orange", alert=True,
            )

    @frappe.whitelist()
    def start(self):
        self.db_set("is_running", 1)
        return "Simulator started."

    @frappe.whitelist()
    def stop(self):
        self.db_set("is_running", 0)
        return "Simulator stopped."

    @frappe.whitelist()
    def generate_transaction(self):
        return sim.generate_transaction(self.name)

    @frappe.whitelist()
    def generate_measurement(self):
        return sim.generate_measurement(self.name)

    @frappe.whitelist()
    def generate_alert(self):
        return sim.generate_alert(self.name)

    @frappe.whitelist()
    def generate_delivery(self):
        return sim.generate_delivery(self.name)

    @frappe.whitelist()
    def simulate_connection_loss(self):
        return sim.set_connection(self.pts_controller, up=False)

    @frappe.whitelist()
    def restore_connection(self):
        return sim.set_connection(self.pts_controller, up=True)
