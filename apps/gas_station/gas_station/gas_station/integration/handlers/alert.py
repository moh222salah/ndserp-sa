import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler
from gas_station.gas_station.realtime import publish_alert


class AlertHandler(BaseHandler):
    operation = "UploadAlertRecord"

    def persist(self):
        doc = frappe.get_doc({
            "doctype": "Station Alert",
            "station": self.station,
            "pts_controller": self.controller.name,
            "alert_type": self._s("alert_type"),
            "severity": self._s("severity") or "Warning",
            "status": "Open",
            "source": "PTS",
            "occurred_at": self._dt("occurred_at") or frappe.utils.now_datetime(),
            "equipment_type": self._s("equipment_type"),
            "equipment_reference": self._s("equipment_reference"),
            "pts_alert_id": self._s("alert_id"),
            "message": self._s("message"),
        })
        doc.insert(ignore_permissions=True)
        publish_alert(self.station, doc)
        return doc
