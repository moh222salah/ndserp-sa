import json
import frappe
from gas_station.gas_station.integration.handlers.base import BaseHandler
from gas_station.gas_station.realtime import publish_pump


class PumpTransactionHandler(BaseHandler):
    operation = "UploadPumpTransaction"

    def _resolve_nozzle_item(self):
        """Find the ERPNext Item for the pump/nozzle so state + mapping have it."""
        pump_no = self._s("pump")
        nozzle_no = self._s("nozzle")
        pump_name = frappe.db.get_value(
            "Gas Station Pump", {"station": self.station, "pump_number": pump_no})
        item = fuel = None
        if pump_name and nozzle_no:
            row = frappe.db.get_value(
                "Gas Station Nozzle",
                {"parent": pump_name, "nozzle_number": nozzle_no},
                ["erpnext_item", "fuel_grade_name"], as_dict=True)
            if row:
                item, fuel = row.erpnext_item, row.fuel_grade_name
        return pump_name, item, fuel

    def persist(self):
        pump_name, item, fuel = self._resolve_nozzle_item()
        doc = frappe.get_doc({
            "doctype": "PTS Pump Transaction",
            "station": self.station,
            "pts_controller": self.controller.name,
            "pts_transaction_id": self._s("transaction_id"),
            "pts_packet_id": self._s("packet_id"),
            "pump": self._s("pump"),
            "nozzle": self._s("nozzle"),
            "tank": self._s("tank"),
            "fuel_grade": fuel or self._s("fuel_grade"),
            "erpnext_item": item,
            "start_datetime": self._dt("start_datetime") or frappe.utils.now_datetime(),
            "end_datetime": self._dt("end_datetime"),
            "volume": self._num("volume"),
            "temperature_compensated_volume": self._num("tc_volume"),
            "price": self._num("price"),
            "amount": self._num("amount"),
            "flow_rate": self._num("flow_rate"),
            "total_volume": self._num("total_volume"),
            "total_amount": self._num("total_amount"),
            "tag": self._s("tag"),
            "user_id": self._s("user_id"),
            "shift_number": self._s("shift_number"),
            "is_offline": 1 if self.data.get("is_offline") else 0,
            "is_paid": 1 if self.data.get("is_paid") else 0,
            "is_test": 1 if self.data.get("is_test") else 0,
            "received_at": frappe.utils.now_datetime(),
            "processing_status": "Received",
            "custom_data": json.dumps(self.data.get("custom_data") or {}),
            "raw_payload": json.dumps(self.raw_payload)[:130000],
        })
        doc.insert(ignore_permissions=True)
        self._pump_name = pump_name
        return doc

    def update_state(self, doc):
        pump_name = getattr(self, "_pump_name", None)
        if not pump_name:
            return
        state = _get_or_new("Pump State", "pump", pump_name,
                            {"station": self.station,
                             "pts_controller": self.controller.name})
        state.status = "Idle"
        state.communication_status = "Live"
        state.current_nozzle = doc.nozzle
        state.current_fuel_grade = doc.fuel_grade
        state.last_transaction_id = doc.pts_transaction_id
        state.last_updated_at = frappe.utils.now_datetime()
        if doc.total_volume is not None:
            state.totalizer_volume = doc.total_volume
        if doc.total_amount is not None:
            state.totalizer_amount = doc.total_amount
        state.current_volume = doc.volume
        state.current_amount = doc.amount
        state.save(ignore_permissions=True)
        publish_pump(self.station, pump_name, state)

    def enqueue_business(self, doc):
        frappe.enqueue(
            "gas_station.gas_station.erpnext_integration.mapping.process_pump_transaction",
            queue="long", txn_name=doc.name, enqueue_after_commit=True)


def _get_or_new(doctype, key, value, defaults):
    name = frappe.db.get_value(doctype, {key: value})
    if name:
        return frappe.get_doc(doctype, name)
    d = frappe.get_doc({"doctype": doctype, key: value, **defaults})
    d.insert(ignore_permissions=True)
    return d
