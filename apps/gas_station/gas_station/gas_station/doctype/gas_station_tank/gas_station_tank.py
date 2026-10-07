import frappe
from frappe.model.document import Document


class GasStationTank(Document):
    def validate(self):
        if self.capacity is not None and self.capacity < 0:
            frappe.throw("Tank capacity cannot be negative.")
        dupe = frappe.db.exists(
            "Gas Station Tank",
            {"station": self.station, "tank_number": self.tank_number,
             "name": ("!=", self.name)},
        )
        if dupe:
            frappe.throw(
                f"Tank {self.tank_number} already exists at station {self.station}."
            )
