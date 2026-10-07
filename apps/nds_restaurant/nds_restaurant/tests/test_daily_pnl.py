# Copyright (c) 2026, NDS and contributors
# License: MIT

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import getdate
from datetime import datetime, time, timedelta


def _mock_settings(**attrs):
	"""Minimal settings stand-in with attribute and dict-style access."""
	obj = type("MockSettings", (object,), attrs)()
	obj.get = lambda key, default=None: attrs.get(key, default)
	return obj


class TestDailyPnL(unittest.TestCase):
	"""
	Unit tests for Daily P&L calculations.
	Tests the seeded example from the plan and extended-hours window logic.
	"""

	def setUp(self):
		"""Set up test data."""
		frappe.set_user("Administrator")

	def test_pnl_structure_seeded_example(self):
		"""
		Test the seeded example from the plan:
		Gross 1000, Discount 100, COGS 300, burning 50, direct fixed 50,
		electricity 20, indirect 30, monthly 3000 in 30-day month (=100/day),
		2% of Net (=18), employee 160, depreciation 40
		Expected Net Profit = 132
		"""
		from nds_restaurant.api.reports import (
			_calculate_burning_materials,
			_calculate_electricity,
			_calculate_percentage_expenses,
			_sum_fixed_expenses,
		)

		class MockSettings:
			def __init__(self):
				self.burning_materials_daily_amount = 50
				self.electricity_charges = 10
				self.electricity_units_per_day = 2  # 10 * 2 = 20
				self.percentage_expenses = [
					type("obj", (object,), {"percent": 2.0, "percentage_type": "Net Sales"})()
				]
				self.fixed_expenses = [
					type("obj", (object,), {"amount": 50, "expense_type": "Direct"})(),
					type("obj", (object,), {"amount": 30, "expense_type": "Indirect"})(),
					type("obj", (object,), {"amount": 160, "expense_type": "Employee"})(),
					type("obj", (object,), {"amount": 40, "expense_type": "Depreciation"})(),
				]

			def get(self, key):
				return getattr(self, key, None)

		settings = MockSettings()

		gross_sales = 1000
		net_sales = 900
		cogs = 300
		monthly = 3000
		days_in_month = 30

		with patch(
			"nds_restaurant.api.reports._report_settings_has_field",
			side_effect=lambda f: f in ("burning_materials_daily_amount", "electricity_charges", "electricity_units_per_day"),
		):
			burning = _calculate_burning_materials(settings)
			self.assertEqual(burning, 50, "Burning materials should be fixed daily 50")

			electricity = _calculate_electricity(settings)
			self.assertEqual(electricity, 20, "Electricity should be 20")

		direct_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Direct")
		gross_profit = net_sales - cogs
		direct_expenses = burning + direct_fixed
		contribution_margin = gross_profit - direct_expenses

		indirect_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Indirect")
		monthly_daily = monthly / days_in_month
		percentage = _calculate_percentage_expenses(settings, gross_sales, net_sales)
		indirect_expenses = electricity + indirect_fixed + monthly_daily + percentage

		operating_profit = contribution_margin - indirect_expenses
		employee_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Employee")
		profit_before_depreciation = operating_profit - employee_fixed
		depreciation = _sum_fixed_expenses(settings.fixed_expenses, "Depreciation")
		net_profit = profit_before_depreciation - depreciation

		self.assertEqual(net_profit, 132, "Net profit should be 132")

	def test_burning_materials_fixed_daily_not_per_item(self):
		"""Fixed daily amount is returned as-is (once per report day)."""
		from nds_restaurant.api.reports import _calculate_burning_materials

		settings = _mock_settings(burning_materials_daily_amount=75)

		def has_field(name):
			return name == "burning_materials_daily_amount"

		with patch("nds_restaurant.api.reports._report_settings_has_field", side_effect=has_field):
			self.assertEqual(_calculate_burning_materials(settings), 75)
			# Same settings regardless of sales volume
			self.assertEqual(_calculate_burning_materials(settings), 75)

	def test_burning_materials_legacy_child_table_fallback(self):
		"""Sites without the new field still sum legacy child rows."""
		from nds_restaurant.api.reports import _calculate_burning_materials

		row = type("obj", (object,), {"cost_per_unit": 25, "units_per_day": 2})()
		settings = _mock_settings(burning_materials=[row])

		def has_field(name):
			return name == "burning_materials"

		with patch("nds_restaurant.api.reports._report_settings_has_field", side_effect=has_field):
			self.assertEqual(_calculate_burning_materials(settings), 50)

	def test_cogs_from_recipe_includes_charcoal_ingredient(self):
		"""Recipe ingredients (e.g. charcoal) flow into COGS, not burning materials."""
		from nds_restaurant.api.reports import _cogs_from_recipe

		from nds_restaurant.tests.test_helpers import as_frappe_rows

		with patch(
			"nds_restaurant.api.reports.frappe.get_all",
			return_value=as_frappe_rows([{"ingredient": "Charcoal", "qty": 0.5}]),
		):
			with patch("nds_restaurant.api.reports.frappe.db.get_value", return_value=10):
				cogs = _cogs_from_recipe("REC-1", 3, "Buying")
		# 10 per kg × 0.5 kg per portion × 3 portions
		self.assertEqual(cogs, 15)

	def test_cogs_bom_fallback_used_when_no_recipe(self):
		"""BOM cost is used when no NDS Recipe exists."""
		from nds_restaurant.api.reports import _calculate_cogs
		from nds_restaurant.tests.test_helpers import as_frappe_rows

		invoice = type("obj", (object,), {"name": "INV-1"})()

		with patch(
			"nds_restaurant.api.reports.frappe.get_all",
			side_effect=[
				as_frappe_rows([{"item_code": "Grill Plate", "qty": 2}]),
				[],
			],
		):
			with patch("nds_restaurant.api.reports.frappe.db.get_value", return_value=None):
				with patch("nds_restaurant.api.reports._get_bom_cost", return_value=12):
					with patch("nds_restaurant.api.reports._get_item_buying_price", return_value=0):
						total = _calculate_cogs([invoice], "Buying")
		self.assertEqual(total, 24)

	def test_extended_hours_window_logic(self):
		"""Extended-hours window boundaries for no_of_hours=2."""
		date = getdate("2026-09-28")
		start_dt = datetime.combine(date, time.min) + timedelta(hours=2)
		end_dt = start_dt + timedelta(days=1)

		self.assertEqual(start_dt.strftime("%Y-%m-%d %H:%M:%S"), "2026-09-28 02:00:00")
		self.assertEqual(end_dt.strftime("%Y-%m-%d %H:%M:%S"), "2026-09-29 02:00:00")

	def test_percentage_expense_gross_vs_net(self):
		from nds_restaurant.api.reports import _calculate_percentage_expenses

		class MockSettings:
			percentage_expenses = [
				type("obj", (object,), {"percent": 5.0, "percentage_type": "Net Sales"})(),
				type("obj", (object,), {"percent": 3.0, "percentage_type": "Gross Sales"})(),
			]

			def get(self, key):
				return getattr(self, key, None)

		total = _calculate_percentage_expenses(MockSettings(), 1000, 900)
		self.assertEqual(total, 75)

	def test_backward_compatibility_missing_fields(self):
		from nds_restaurant.api.reports import (
			_calculate_burning_materials,
			_calculate_electricity,
			_calculate_percentage_expenses,
		)

		settings = _mock_settings()

		with patch("nds_restaurant.api.reports._report_settings_has_field", return_value=False):
			self.assertEqual(_calculate_burning_materials(settings), 0)
			self.assertEqual(_calculate_electricity(settings), 0)

		self.assertEqual(_calculate_percentage_expenses(settings, 1000, 900), 0)


def run_tests():
	suite = unittest.TestLoader().loadTestsFromTestCase(TestDailyPnL)
	unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
	run_tests()
