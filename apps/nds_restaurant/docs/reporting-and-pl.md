# Reporting & Daily P&L

Create **NDS Report Settings** per Branch:

- **Buying Price List** (required for COGS calculation)
- **Extended Hours** (optional): Count post-midnight hours in previous day
  - **No Of Hours**: Hours past midnight to include (0-12)
- **Burning Materials (Daily)**: Fixed currency amount per day for fuel/consumables **not** already on item recipes/BOMs (e.g. extra charcoal, LPG overhead). Charcoal that is a recipe ingredient is counted in **COGS**, not here.
- **Electricity**: Charges per unit and units per day
- **Fixed Daily Expenses**: Categorized by type (Direct / Indirect / Employee / Depreciation)
- **Monthly Expenses**: Divided by days in month
- **Percentage Expenses**: Calculated as % of Net Sales or Gross Sales

Open report **NDS Daily P and L** and select Branch + Date.

## Structure

The Daily P&L report shows a complete income statement with the following structure:

```
Gross Sales (pre-discount, pre-tax)
  Less: Discounts
= Net Sales

  Less: Cost of Goods Sold (COGS)
= Gross Profit

Direct Expenses:
  - Burning Materials (fixed daily amount, not in recipes)
  - Direct Fixed Expenses
= Contribution Margin

Indirect Expenses:
  - Electricity (charges × units)
  - Indirect Fixed Expenses
  - Monthly Expenses (prorated daily)
  - Percentage Expenses (% of sales)
= Operating Profit

Employee Expenses:
  - Attendance-based (see below)
  - Employee Fixed Expenses
= Profit Before Depreciation

  Less: Depreciation
= Net Profit
```

## Employee Cost Calculation

Employee daily cost is calculated from attendance records:

1. If **Employee Payment Type** is set:
   - **Salary**: Payment Amount ÷ days in month
   - **Daily Wage**: Payment Amount directly
2. Otherwise, falls back to **Salary Structure Assignment** base ÷ 30
3. Half Day attendance gets 50% of the daily cost
4. Only employees from the branch are included

## COGS Calculation

COGS uses a 3-tier fallback:

1. **Recipe**: Cost of ingredients from buying price list
2. **BOM**: Bill of Materials cost (if no recipe exists)
3. **Item Buying Price**: Direct item cost (if no recipe or BOM)

## Extended Hours

When **Extended Hours** is enabled with **No Of Hours** set to N:

- Invoices posted between 00:00 and N hours on day D+1 are counted in day D's report
- Example: With No Of Hours = 2, an invoice at 01:30 on Sep 29 counts as Sep 28

This is useful for restaurants operating past midnight.

## Percentage Expenses

Percentage expenses can be based on:

- **Net Sales**: After discounts, before taxes
- **Gross Sales**: Before discounts and taxes

Example: Platform fees at 2% of Net Sales

## Permissions

Daily P&L reports require:

- System Manager role
- NDS Manager role
- OR read permission on NDS Report Settings

## Backward Compatibility

All new P9 fields include safe fallbacks:

- Missing **Buying Price List**: Uses valuation rates with a warning
- Missing **Employee Payment Fields**: Falls back to Salary Structure Assignment
- Missing **Burning Materials** / **Electricity**: Returns 0
- Missing **Percentage Expenses**: Returns 0

The report will not crash on production sites that haven't been updated yet.
