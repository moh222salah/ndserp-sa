"""End-to-end tests for the Gas Station integration pipeline.

Run: bench --site <site> run-tests --app gas_station --module \
     gas_station.gas_station.tests.test_integration
"""
import frappe
from frappe.tests.utils import FrappeTestCase

from gas_station.gas_station.integration import dispatch
from gas_station.gas_station.integration.providers.mock import MockPTSProvider

STATION = "TST-1"
CTRL = "CTRL-TST-1"
ITEM = "TEST-FUEL-95"


def _envelope(operation, data, controller=CTRL):
    return {"controller": controller, "operation": operation,
            "packet_id": frappe.generate_hash(length=8), "data": data}


class TestGasStationIntegration(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = frappe.db.get_value("Company", {}, "name")

        if not frappe.db.exists("Item", ITEM):
            frappe.get_doc({"doctype": "Item", "item_code": ITEM,
                            "item_name": "Test Fuel 95",
                            "item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
                            "stock_uom": frappe.db.get_value("UOM", {}) or "Nos",
                            "is_stock_item": 0}).insert(ignore_permissions=True)

        if not frappe.db.exists("Gas Station", STATION):
            frappe.get_doc({"doctype": "Gas Station", "station_code": STATION,
                            "station_name": "Test Station", "enabled": 1, "is_demo": 1,
                            "company": company}).insert(ignore_permissions=True)

        if not frappe.db.exists("PTS Controller", CTRL):
            frappe.get_doc({"doctype": "PTS Controller", "controller_code": CTRL,
                            "controller_name": "Test PTS", "station": STATION,
                            "enabled": 1, "provider": "Mock",
                            "configuration_id": CTRL,
                            "stale_after_seconds": 120}).insert(ignore_permissions=True)

        if not frappe.db.exists("Gas Station Tank", f"{STATION}-T1"):
            frappe.get_doc({"doctype": "Gas Station Tank", "station": STATION,
                            "tank_number": "1", "tank_name": "T1",
                            "pts_controller": CTRL, "enabled": 1,
                            "erpnext_item": ITEM, "capacity": 30000}
                           ).insert(ignore_permissions=True)

        if not frappe.db.exists("Gas Station Pump", f"{STATION}-P1"):
            pump = frappe.get_doc({"doctype": "Gas Station Pump", "station": STATION,
                                   "pump_number": "1", "pts_controller": CTRL,
                                   "enabled": 1})
            pump.append("nozzles", {"nozzle_number": 1, "erpnext_item": ITEM,
                                    "fuel_grade_name": "Gasoline 95",
                                    "tank": f"{STATION}-T1", "enabled": 1})
            pump.insert(ignore_permissions=True)
        frappe.db.commit()

    # ---------------------------------------------------------------- helpers
    def _txn_data(self, txn_id="TST-TXN-1", **over):
        d = {"transaction_id": txn_id, "pump": "1", "nozzle": "1",
             "tank": f"{STATION}-T1", "volume": 40, "price": 2.33, "amount": 93.2,
             "total_volume": 1040, "total_amount": 2423.2}
        d.update(over)
        return d

    # ---------------------------------------------------------------- tests
    def test_normal_transaction(self):
        ack = dispatch.receive(_envelope("UploadPumpTransaction",
                                         self._txn_data("TST-TXN-NORMAL")))
        self.assertEqual(ack["ack"], "ok")
        self.assertTrue(frappe.db.exists(
            "PTS Pump Transaction",
            {"pts_controller": CTRL, "pts_transaction_id": "TST-TXN-NORMAL"}))
        # current state updated + item resolved from nozzle
        ps = frappe.get_doc("Pump State", f"{STATION}-P1")
        self.assertEqual(ps.communication_status, "Live")
        self.assertEqual(ps.last_transaction_id, "TST-TXN-NORMAL")

    def test_duplicate_transaction_is_rejected(self):
        env = _envelope("UploadPumpTransaction", self._txn_data("TST-TXN-DUP"))
        first = dispatch.receive(env)
        self.assertEqual(first["ack"], "ok")
        env2 = _envelope("UploadPumpTransaction", self._txn_data("TST-TXN-DUP"))
        second = dispatch.receive(env2)
        self.assertEqual(second["ack"], "duplicate")
        count = frappe.db.count("PTS Pump Transaction",
                                {"pts_controller": CTRL, "pts_transaction_id": "TST-TXN-DUP"})
        self.assertEqual(count, 1)

    def test_unknown_controller_rejected(self):
        ack = dispatch.receive(_envelope("UploadPumpTransaction",
                                         self._txn_data("X"), controller="NOPE-999"))
        self.assertEqual(ack["ack"], "rejected")

    def test_malformed_missing_required_field(self):
        bad = self._txn_data("TST-BAD")
        del bad["amount"]  # required by schema
        ack = dispatch.receive(_envelope("UploadPumpTransaction", bad))
        self.assertEqual(ack["ack"], "rejected")

    def test_tank_measurement_updates_state(self):
        data = {"tank": "1", "product_volume": 18000, "temperature": 29.5}
        ack = dispatch.receive(_envelope("UploadTankMeasurement", data))
        self.assertEqual(ack["ack"], "ok")
        ts = frappe.get_doc("Tank State", f"{STATION}-T1")
        self.assertAlmostEqual(ts.product_volume, 18000, places=1)
        self.assertAlmostEqual(ts.fill_percentage, 60.0, places=1)

    def test_missing_value_stays_none_not_zero(self):
        data = {"tank": "1", "product_volume": 12000}  # no water_level provided
        dispatch.receive(_envelope("UploadTankMeasurement", data))
        ts = frappe.get_doc("Tank State", f"{STATION}-T1")
        self.assertIsNone(ts.water_level)

    def test_alert_created(self):
        data = {"alert_type": "High Water", "severity": "Critical",
                "equipment_type": "Tank", "message": "test alert"}
        ack = dispatch.receive(_envelope("UploadAlertRecord", data))
        self.assertEqual(ack["ack"], "ok")
        self.assertTrue(frappe.db.exists(
            "Station Alert", {"station": STATION, "alert_type": "High Water",
                              "status": "Open"}))

    def test_integration_event_recorded_for_every_request(self):
        before = frappe.db.count("Integration Event", {"pts_controller": CTRL})
        dispatch.receive(_envelope("UploadPumpTransaction",
                                   self._txn_data("TST-TXN-EVT")))
        after = frappe.db.count("Integration Event", {"pts_controller": CTRL})
        self.assertEqual(after, before + 1)

    def test_mock_provider_uses_same_pipeline(self):
        provider = MockPTSProvider()
        ack = provider.submit("UploadPumpTransaction", CTRL,
                              self._txn_data("TST-TXN-MOCK"))
        self.assertEqual(ack["ack"], "ok")
        self.assertTrue(frappe.db.exists(
            "PTS Pump Transaction", {"pts_transaction_id": "TST-TXN-MOCK"}))

    def test_reconciliation_flags_missing_in_erpnext(self):
        from gas_station.gas_station.reconciliation import engine
        dispatch.receive(_envelope("UploadPumpTransaction",
                                   self._txn_data("TST-TXN-RECON")))
        txn = frappe.get_doc("PTS Pump Transaction",
                             {"pts_transaction_id": "TST-TXN-RECON"})
        txn.db_set("processing_status", "Processed", update_modified=False)
        rows = engine._pts_vs_sales(
            STATION, frappe.utils.add_days(frappe.utils.nowdate(), -1),
            frappe.utils.add_days(frappe.utils.nowdate(), 1))
        statuses = {r["reference"]: r["status"] for r in rows}
        self.assertEqual(statuses.get("TST-TXN-RECON"), "Missing in ERPNext")
