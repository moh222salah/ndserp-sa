import json
import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler
from gas_station.gas_station.integration.handlers.tank_measurement import TankMeasurementHandler


class TankDeliveryHandler(BaseHandler):
    operation = "UploadInTankDelivery"

    def persist(self):
        tno = self._s("tank")
        tank = frappe.db.get_value(
            "Gas Station Tank", {"station": self.station, "tank_number": tno}) \
            or frappe.db.get_value("Gas Station Tank", tno)
        doc = frappe.get_doc({
            "doctype": "Tank Delivery",
            "station": self.station,
            "tank": tank,
            "pts_controller": self.controller.name,
            "delivery_id": self._s("delivery_id"),
            "start_datetime": self._dt("start_datetime"),
            "end_datetime": self._dt("end_datetime"),
            "opening_volume": self._num("opening_volume"),
            "delivery_volume": self._num("delivery_volume"),
            "closing_volume": self._num("closing_volume"),
            "temperature": self._num("temperature"),
            "temperature_compensated_volume": self._num("tc_volume"),
            "status": self._s("status") or "Completed",
            "raw_payload": json.dumps(self.raw_payload)[:130000],
        })
        if not doc.tank:
            frappe.throw(f"Unknown tank: {tno}")
        doc.insert(ignore_permissions=True)
        return doc
