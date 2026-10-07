"""Core engine tests (Project-rooted architecture).

Run: bench --site <site> run-tests --app contracting
"""
import frappe
from frappe.tests.utils import FrappeTestCase
from contracting.services.measurement_service import item_value


class TestMeasurement(FrappeTestCase):
	def test_item_value(self):
		self.assertAlmostEqual(item_value(10, 150), 1500.0)
		self.assertAlmostEqual(item_value(0, 150), 0.0)


class TestBudgetGoldenRecord(FrappeTestCase):
	def test_budget_boq_item_exists(self):
		meta = frappe.get_meta("Budget BOQ Item")
		names = {df.fieldname for df in meta.fields}
		self.assertTrue({"budget", "project", "boq_no", "quantity", "unit",
			"cost_amount", "selling_amount"}.issubset(names))


class TestIPCArithmetic(FrappeTestCase):
	def test_ipc_prev_curr_total(self):
		meta = frappe.get_meta("Client IPC")
		names = {df.fieldname for df in meta.fields}
		self.assertTrue({"net_current", "previous_net", "total_net"}.issubset(names))


class TestProjectRoot(FrappeTestCase):
	def test_project_contract_fields(self):
		meta = frappe.get_meta("Project")
		names = {df.fieldname for df in meta.fields}
		self.assertTrue({"original_contract_value", "current_contract_value"}.issubset(names))
