import frappe
from frappe.model.document import Document


class GasStationPump(Document):
    def validate(self):
        self._unique_pump_within_station()
        self._nozzle_numbers_unique()

    def _unique_pump_within_station(self):
        dupe = frappe.db.exists(
            "Gas Station Pump",
            {"station": self.station, "pump_number": self.pump_number,
             "name": ("!=", self.name)},
        )
        if dupe:
            frappe.throw(
                f"Pump {self.pump_number} already exists at station {self.station}."
            )

    def _nozzle_numbers_unique(self):
        seen = set()
        for row in self.nozzles:
            if row.nozzle_number in seen:
                frappe.throw(f"Nozzle number {row.nozzle_number} is duplicated on this pump.")
            seen.add(row.nozzle_number)
