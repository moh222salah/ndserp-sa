# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from nds_restaurant.api.reports import get_daily_pnl


def execute(filters=None):
	"""
	P9-T5: Full P&L structure with indented tree and bold subtotals.
	
	Structure:
	- Gross Sales
	- Discounts
	= Net Sales
	- COGS
	= Gross Profit
	- Direct Expenses (burning + direct fixed)
	= Contribution Margin
	- Indirect Expenses (electricity + indirect fixed + monthly + percentage)
	= Operating Profit
	- Employee Expenses (attendance + employee fixed)
	= Profit Before Depreciation
	- Depreciation
	= Net Profit
	"""
	filters = filters or {}
	branch = filters.get("branch")
	date = filters.get("date")
	if not branch:
		return [], []

	data = get_daily_pnl(branch, date)
	
	columns = [
		{"label": "Metric", "fieldname": "metric", "fieldtype": "Data", "width": 280},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 160},
	]
	
	# P9-T5: Build indented tree structure
	rows = []
	
	# Revenue section
	rows.append({"metric": "Gross Sales", "amount": data["gross_sales"], "indent": 0})
	rows.append({"metric": "  Less: Discounts", "amount": data["discounts"], "indent": 1})
	rows.append({"metric": "Net Sales", "amount": data["net_sales"], "indent": 0, "bold": 1})
	
	# COGS
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "Cost of Goods Sold", "amount": data["cogs"], "indent": 0})
	rows.append({"metric": "Gross Profit", "amount": data["gross_profit"], "indent": 0, "bold": 1})
	
	# Direct Expenses
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "Direct Expenses:", "amount": None, "indent": 0})
	rows.append({
		"metric": "  Burning Materials (not in recipes)",
		"amount": data["burning_materials"],
		"indent": 1,
	})
	rows.append({"metric": "  Direct Fixed", "amount": data["direct_fixed"], "indent": 1})
	rows.append({"metric": "  Total Direct", "amount": data["direct_expenses"], "indent": 1})
	rows.append({"metric": "Contribution Margin", "amount": data["contribution_margin"], "indent": 0, "bold": 1})
	
	# Indirect Expenses
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "Indirect Expenses:", "amount": None, "indent": 0})
	rows.append({"metric": "  Electricity", "amount": data["electricity"], "indent": 1})
	rows.append({"metric": "  Indirect Fixed", "amount": data["indirect_fixed"], "indent": 1})
	rows.append({"metric": "  Monthly (prorated)", "amount": data["monthly_expenses"], "indent": 1})
	rows.append({"metric": "  Percentage", "amount": data["percentage_expenses"], "indent": 1})
	rows.append({"metric": "  Total Indirect", "amount": data["indirect_expenses"], "indent": 1})
	rows.append({"metric": "Operating Profit", "amount": data["operating_profit"], "indent": 0, "bold": 1})
	
	# Employee Expenses
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "Employee Expenses:", "amount": None, "indent": 0})
	rows.append({"metric": "  Attendance-based", "amount": data["employee_hr"], "indent": 1})
	rows.append({"metric": "  Employee Fixed", "amount": data["employee_fixed"], "indent": 1})
	rows.append({"metric": "  Total Employee", "amount": data["employee_total"], "indent": 1})
	rows.append({"metric": "Profit Before Depreciation", "amount": data["profit_before_depreciation"], "indent": 0, "bold": 1})
	
	# Depreciation
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "Depreciation", "amount": data["depreciation"], "indent": 0})
	rows.append({"metric": "Net Profit", "amount": data["net_profit"], "indent": 0, "bold": 1})
	
	# Summary
	rows.append({"metric": "", "amount": None})  # Blank line
	rows.append({"metric": "--- Summary ---", "amount": None, "indent": 0})
	rows.append({"metric": "Invoice Count", "amount": data["invoice_count"], "indent": 0})
	
	return columns, rows
