# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, get_last_day
from datetime import datetime, timedelta


def _report_settings_has_field(fieldname):
	"""Safe field check for sites that have not migrated NDS Report Settings yet."""
	return frappe.get_meta("NDS Report Settings").has_field(fieldname)


@frappe.whitelist()
def get_daily_pnl(branch, date=None):
	"""
	Compute Daily P&L for a branch with full structure.
	
	P9-T5: Full P&L structure with:
	- Gross Sales (pre-discount, pre-tax)
	- Discounts
	- Net Sales
	- COGS
	- Gross Profit = Net Sales - COGS
	- Direct Expenses (burning materials + direct fixed)
	- Contribution Margin = Gross Profit - Direct
	- Indirect Expenses (electricity + indirect fixed + monthly/days + percentage)
	- Operating Profit = Contribution Margin - Indirect
	- Employee Expenses (attendance-based + employee fixed)
	- Profit Before Depreciation = Operating Profit - Employee
	- Depreciation
	- Net Profit = PBD - Depreciation
	"""
	# Permission check: management roles only (not POS operators with Report Settings read)
	if not (
		frappe.session.user == "Administrator"
		or "System Manager" in frappe.get_roles()
		or "NDS Manager" in frappe.get_roles()
	):
		frappe.throw(_("Not permitted to view Daily P&L reports"), frappe.PermissionError)
	
	date = getdate(date) if date else getdate()
	settings_name = frappe.db.exists("NDS Report Settings", {"branch": branch})
	if not settings_name:
		frappe.throw(_("Create NDS Report Settings for branch {0}").format(branch))

	settings = frappe.get_doc("NDS Report Settings", settings_name)
	
	# P9-T1: Warn if buying price list is missing, but don't hard-fail
	if not settings.buying_price_list:
		frappe.msgprint(
			_("Warning: Buying Price List is not set in Report Settings for branch {0}. COGS calculation will use valuation rates or may be incomplete.").format(branch),
			indicator="orange"
		)
	
	restaurant = frappe.db.get_value("NDS Restaurant", {"branch": branch}, "name")

	profiles = frappe.get_all(
		"POS Profile",
		filters={"custom_restaurant": restaurant} if restaurant else {},
		pluck="name",
	)
	
	# P9-T3: Extended hours sales window
	invoices = _get_invoices_for_period(date, profiles, settings)

	# Calculate gross sales (total before discounts/taxes)
	gross_sales = sum(flt(i.total) for i in invoices)
	
	# P9-T5: Discounts line
	discounts = sum(flt(i.discount_amount) for i in invoices)
	
	# Net sales (after discounts, before taxes)
	net_sales = sum(flt(i.net_total) for i in invoices)

	# P9-T4: COGS with BOM fallback
	cogs = _calculate_cogs(invoices, settings.buying_price_list)
	
	# Gross Profit
	gross_profit = net_sales - cogs

	# Direct Expenses = burning materials (fixed daily, not in recipes) + direct fixed
	burning = _calculate_burning_materials(settings)
	direct_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Direct")
	direct_expenses = burning + direct_fixed
	
	# P9-T5: Contribution Margin
	contribution_margin = gross_profit - direct_expenses

	# P9-T5: Indirect Expenses = electricity + indirect fixed + monthly/days + percentage
	electricity = _calculate_electricity(settings)
	indirect_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Indirect")
	
	days_in_month = (get_last_day(date) - get_first_day(date)).days + 1
	monthly = sum(flt(r.monthly_amount) for r in (settings.variable_expenses or []))
	monthly_daily = monthly / days_in_month if days_in_month else 0
	
	percentage = _calculate_percentage_expenses(settings, gross_sales, net_sales)
	
	indirect_expenses = electricity + indirect_fixed + monthly_daily + percentage
	
	# P9-T5: Operating Profit
	operating_profit = contribution_margin - indirect_expenses

	# P9-T2 & P9-T5: Employee Expenses = attendance-based + employee fixed
	employee_hr = _employee_cost(date, branch)
	employee_fixed = _sum_fixed_expenses(settings.fixed_expenses, "Employee")
	employee_total = employee_hr + employee_fixed
	
	# P9-T5: Profit Before Depreciation
	profit_before_depreciation = operating_profit - employee_total

	# P9-T5: Depreciation
	depreciation = _sum_fixed_expenses(settings.fixed_expenses, "Depreciation")
	
	# P9-T5: Net Profit
	net_profit = profit_before_depreciation - depreciation

	return {
		"branch": branch,
		"date": str(date),
		"gross_sales": gross_sales,
		"discounts": discounts,
		"net_sales": net_sales,
		"cogs": cogs,
		"gross_profit": gross_profit,
		"burning_materials": burning,
		"direct_fixed": direct_fixed,
		"direct_expenses": direct_expenses,
		"contribution_margin": contribution_margin,
		"electricity": electricity,
		"indirect_fixed": indirect_fixed,
		"monthly_expenses": monthly_daily,
		"percentage_expenses": percentage,
		"indirect_expenses": indirect_expenses,
		"operating_profit": operating_profit,
		"employee_hr": employee_hr,
		"employee_fixed": employee_fixed,
		"employee_total": employee_total,
		"profit_before_depreciation": profit_before_depreciation,
		"depreciation": depreciation,
		"net_profit": net_profit,
		"invoice_count": len(invoices),
	}


def _get_invoices_for_period(date, profiles, settings):
	"""
	P9-T3: Extended hours sales window.
	When extended_hours is on and no_of_hours is set, 
	select invoices with TIMESTAMP(posting_date, posting_time) 
	in [D 00:00 + N h, D+1 00:00 + N h).
	Otherwise use posting_date = D.
	"""
	filters = {"docstatus": 1}
	if profiles:
		filters["pos_profile"] = ["in", profiles]
	
	if settings.get("extended_hours") and settings.get("no_of_hours"):
		# Safe check for no_of_hours field existence
		hours = int(settings.no_of_hours or 0)
		if hours > 0:
			# Calculate the timestamp window
			# [date 00:00 + hours, date+1 00:00 + hours)
			start_dt = datetime.combine(date, datetime.min.time()) + timedelta(hours=hours)
			end_dt = start_dt + timedelta(days=1)
			
			# Calculate posting_date bounds for index usage
			date_start = start_dt.date()
			date_end = end_dt.date()
			
			# Use SQL for timestamp comparison with named placeholders
			invoices = frappe.db.sql("""
				SELECT name, grand_total, total, net_total, discount_amount, 
					   total_taxes_and_charges
				FROM `tabPOS Invoice`
				WHERE docstatus = 1
				AND posting_date BETWEEN %(d)s AND %(d1)s
				AND TIMESTAMP(posting_date, posting_time) >= %(start)s
				AND TIMESTAMP(posting_date, posting_time) < %(end)s
				{profile_filter}
			""".format(
				profile_filter="AND pos_profile IN %(profiles)s" if profiles else ""
			), {
				"d": date_start,
				"d1": date_end,
				"start": start_dt,
				"end": end_dt,
				"profiles": profiles
			}, as_dict=True)
			return invoices
	
	# Default: use posting_date = date
	filters["posting_date"] = date
	return frappe.get_all(
		"POS Invoice",
		filters=filters,
		fields=["name", "grand_total", "total", "net_total", "discount_amount", 
				"total_taxes_and_charges"],
	)


def _calculate_burning_materials(settings):
	"""
	Fixed daily amount for burning materials not captured in recipes/BOMs.
	Added once per Daily P&L report date (not per item sold).
	Charcoal etc. on a recipe flows through COGS instead.
	"""
	if _report_settings_has_field("burning_materials_daily_amount"):
		return flt(settings.get("burning_materials_daily_amount"))

	# Legacy: cost_per_unit × units_per_day child table (pre-migration sites)
	if _report_settings_has_field("burning_materials"):
		total = 0
		for row in settings.get("burning_materials") or []:
			cost = flt(getattr(row, "cost_per_unit", None) or 0)
			units = flt(getattr(row, "units_per_day", None) or 1)
			total += cost * units
		return total

	return 0


def _calculate_electricity(settings):
	"""
	Daily electricity expense = charges per unit × units per day.
	Kept as unit-based (not a single fixed lump sum) so operators can
	adjust units when usage varies; burning materials use a fixed daily
	lump sum because unmodeled fuel is harder to meter per unit.
	"""
	if not _report_settings_has_field("electricity_charges"):
		return 0

	charges = flt(settings.get("electricity_charges") or 0)
	units = flt(settings.get("electricity_units_per_day") or 0) if _report_settings_has_field(
		"electricity_units_per_day"
	) else 0
	return charges * units


def _calculate_percentage_expenses(settings, gross_sales, net_sales):
	"""
	P9-T5: Percentage expenses = Σ(percent × base)
	Base is either Net Sales or Gross Sales depending on percentage_type.
	Safe field access for backward compatibility.
	"""
	if not hasattr(settings, 'percentage_expenses'):
		return 0
	
	total = 0
	for row in (settings.percentage_expenses or []):
		if not hasattr(row, 'percent') or not hasattr(row, 'percentage_type'):
			continue
		
		percent = flt(row.percent) / 100.0
		base = gross_sales if row.percentage_type == "Gross Sales" else net_sales
		total += base * percent
	return total


def _sum_fixed_expenses(expenses, expense_type):
	"""Sum fixed expenses of a given type."""
	if not expenses:
		return 0
	return sum(flt(row.amount) for row in expenses if row.expense_type == expense_type)


def _calculate_cogs(invoices, buying_price_list):
	"""
	P9-T4: COGS fallback to BOM.
	Priority: Recipe → BOM → Item buying price.
	
	BOM cost per unit = Σ(BOM Item qty × buying price-list rate, 
	                       falling back to BOM Item.rate) ÷ BOM.quantity
	"""
	total = 0
	bom_cache = {}  # Memoization per item within a run
	
	for inv in invoices:
		items = frappe.get_all(
			"POS Invoice Item",
			filters={"parent": inv.name},
			fields=["item_code", "qty"],
		)
		for it in items:
			item_code = it.item_code
			qty = flt(it.qty)
			
			# Try Recipe first
			recipe = frappe.db.get_value("NDS Recipe", {"item": item_code, "enabled": 1}, "name")
			if recipe:
				total += _cogs_from_recipe(recipe, qty, buying_price_list)
			else:
				# P9-T4: Fallback to BOM
				if item_code not in bom_cache:
					bom_cache[item_code] = _get_bom_cost(item_code, buying_price_list)
				
				bom_cost = bom_cache[item_code]
				if bom_cost > 0:
					total += bom_cost * qty
				else:
					# Final fallback: item buying price
					total += _get_item_buying_price(item_code, buying_price_list) * qty
	
	return total


def _cogs_from_recipe(recipe, qty, buying_price_list):
	"""Calculate COGS from a recipe."""
	total = 0
	for row in frappe.get_all(
		"NDS Recipe Item",
		filters={"parent": recipe},
		fields=["ingredient", "qty"],
	):
		rate = 0
		if buying_price_list:
			rate = flt(
				frappe.db.get_value(
					"Item Price",
					{
						"item_code": row.ingredient,
						"price_list": buying_price_list,
						"buying": 1,
					},
					"price_list_rate",
				)
				or 0
			)
		if not rate:
			rate = flt(frappe.db.get_value("Bin", {"item_code": row.ingredient}, "valuation_rate") or 0)
		total += rate * flt(row.qty) * qty
	return total


def _get_bom_cost(item_code, buying_price_list):
	"""
	P9-T4: Get cost from default active submitted BOM.
	BOM cost per unit = Σ(BOM Item qty × buying price-list rate, 
	                       falling back to BOM Item.rate) ÷ BOM.quantity
	Returns 0 if no BOM found.
	"""
	bom = frappe.db.get_value(
		"BOM",
		{
			"item": item_code,
			"is_active": 1,
			"is_default": 1,
			"docstatus": 1,
		},
		["name", "quantity"],
		as_dict=True
	)
	
	if not bom:
		return 0
	
	bom_items = frappe.get_all(
		"BOM Item",
		filters={"parent": bom.name},
		fields=["item_code", "qty", "rate"],
	)
	
	total_cost = 0
	for bi in bom_items:
		# Try buying price list first
		rate = 0
		if buying_price_list:
			rate = flt(
				frappe.db.get_value(
					"Item Price",
					{
						"item_code": bi.item_code,
						"price_list": buying_price_list,
						"buying": 1,
					},
					"price_list_rate",
				)
				or 0
			)
		
		# Fallback to BOM Item's rate
		if not rate:
			rate = flt(bi.rate)
		
		total_cost += rate * flt(bi.qty)
	
	# Return cost per unit
	bom_qty = flt(bom.quantity) or 1
	return total_cost / bom_qty


def _get_item_buying_price(item_code, buying_price_list):
	"""
	Get item's buying price from price list.
	Falls back to valuation rate if price list not available.
	"""
	rate = 0
	
	# Try buying price list first
	if buying_price_list:
		rate = flt(
			frappe.db.get_value(
				"Item Price",
				{"item_code": item_code, "price_list": buying_price_list, "buying": 1},
				"price_list_rate",
			)
			or 0
		)
	
	# Fallback to valuation rate
	if not rate:
		rate = flt(
			frappe.db.get_value("Bin", {"item_code": item_code}, "valuation_rate")
			or 0
		)
	
	# Final fallback to item's standard_rate
	if not rate:
		rate = flt(
			frappe.db.get_value("Item", item_code, "standard_rate")
			or 0
		)
	
	return rate


def _employee_cost(date, branch):
	"""
	P9-T2: Attendance-based employee cost with Payment Type and Payment Amount.
	
	- Filter employees by branch
	- For each present/half-day employee:
	  - If custom_nds_payment_type is set:
	    - Salary: custom_nds_payment_amount ÷ days in month
	    - Daily Wage: custom_nds_payment_amount (× 0.5 for half day)
	  - Else fallback to Salary Structure Assignment base ÷ days in month
	"""
	try:
		attendance = frappe.get_all(
			"Attendance",
			filters={"attendance_date": date, "docstatus": 1, "status": ["in", ["Present", "Half Day"]]},
			fields=["employee", "status"],
		)
	except Exception:
		return 0

	total = 0
	days_in_month = (get_last_day(date) - get_first_day(date)).days + 1
	
	for row in attendance:
		# P9-T2: Branch filter
		emp_branch = frappe.db.get_value("Employee", row.employee, "branch")
		if emp_branch != branch:
			continue
		
		# Check for custom fields (safe access for backward compatibility)
		payment_type = None
		payment_amount = None
		
		if frappe.db.exists("Custom Field", {"dt": "Employee", "fieldname": "custom_nds_payment_type"}):
			payment_type = frappe.db.get_value("Employee", row.employee, "custom_nds_payment_type")
			payment_amount = flt(frappe.db.get_value("Employee", row.employee, "custom_nds_payment_amount") or 0)
		
		# Calculate cost based on payment type
		if payment_type and payment_amount:
			if payment_type == "Salary":
				# Monthly salary: divide by days in month
				daily_cost = payment_amount / days_in_month if days_in_month else 0
			else:  # Daily Wage
				# Daily wage: use amount directly
				daily_cost = payment_amount
			
			# Half day adjustment
			if row.status == "Half Day":
				daily_cost *= 0.5
			
			total += daily_cost
		else:
			# P9-T2: Fallback to Salary Structure Assignment
			salary = frappe.db.get_value(
				"Salary Structure Assignment",
				{"employee": row.employee, "docstatus": 1},
				"base",
				order_by="from_date desc",
			)
			if salary:
				daily_cost = flt(salary) / days_in_month if days_in_month else 0
				if row.status == "Half Day":
					daily_cost *= 0.5
				total += daily_cost
	
	return total
