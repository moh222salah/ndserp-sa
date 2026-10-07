import json
import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler
from gas_station.gas_station.integration.handlers.pump_transaction import _get_or_new
from gas_station.gas_station.realtime import publish_tank
from gas_station.gas_station.alerts.engine import evaluate_tank


class TankMeasurementHandler(BaseHandler):
    operation = "UploadTankMeasurement"

    def _tank(self):
        tno = self._s("tank")
        return frappe.db.get_value(
            "Gas Station Tank", {"station": self.station, "tank_number": tno}) \
            or frappe.db.get_value("Gas Station Tank", tno)

    def persist(self):
        tank = self._tank()
        self._tank_name = tank
        doc = frappe.get_doc({
            "doctype": "Tank Measurement",
            "station": self.station,
            "tank": tank,
            "probe": self._s("probe"),
            "pts_controller": self.controller.name,
            "measurement_datetime": self._dt("measurement_datetime") or frappe.utils.now_datetime(),
            "received_at": frappe.utils.now_datetime(),
            "product_level": self._num("product_level"),
            "water_level": self._num("water_level"),
            "product_volume": self._num("product_volume"),
            "water_volume": self._num("water_volume"),
            "temperature": self._num("temperature"),
            "density": self._num("density"),
            "mass": self._num("mass"),
            "ullage": self._num("ullage"),
            "temperature_compensated_volume": self._num("tc_volume"),
            "alarms": self._s("alarms"),
            "raw_payload": json.dumps(self.raw_payload)[:130000],
        })
        if not doc.tank:
            frappe.throw(f"Unknown tank: {self._s('tank')}")
        doc.insert(ignore_permissions=True)
        return doc

    def update_state(self, doc):
        if not doc.tank:
            return
        capacity = frappe.db.get_value("Gas Station Tank", doc.tank, "capacity") or 0
        state = _get_or_new("Tank State", "tank", doc.tank,
                            {"station": self.station,
                             "pts_controller": self.controller.name})
        state.product_level = doc.product_level
        state.water_level = doc.water_level
        state.product_volume = doc.product_volume
        state.water_volume = doc.water_volume
        state.temperature = doc.temperature
        state.density = doc.density
        state.mass = doc.mass
        state.ullage = doc.ullage
        state.temperature_compensated_volume = doc.temperature_compensated_volume
        if capacity and doc.product_volume is not None:
            state.fill_percentage = round(doc.product_volume / capacity * 100, 2)
        state.communication_status = "Live"
        state.status = "Normal"
        state.last_updated_at = frappe.utils.now_datetime()
        state.save(ignore_permissions=True)
        publish_tank(self.station, doc.tank, state)
        evaluate_tank(state)
