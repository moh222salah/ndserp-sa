# NDS Restaurant Setup Guide

Follow these steps in order.

## Prerequisites

- ERPNext + HRMS + NDS Restaurant installed ([INSTALLATION.md](../INSTALLATION.md))
- Site migrated and assets built

## Step 1: Company Setup

Complete the ERPNext setup wizard (Company, Warehouse, Cost Center, Chart of Accounts, Fiscal Year).

## Step 2: Users and Roles

Create users and assign:

- **NDS Manager** — full access
- **NDS Cashier** — billing / open-close
- **NDS Captain** — order taking

## Step 3: Branch

1. Create a **Branch**
2. In **NDS Users**, add each POS user (optional Room for multi-cashier)
3. Optionally configure **Aggregator Settings**

Only users listed on the Branch can use that branch’s POS.

## Step 4: Financial Setup

Create/verify:

- Cost Center
- Modes of Payment (with accounts)
- Sales Taxes and Charges Template
- Walk-in **Customer** with **Mobile Number** filled
- **POS Settings**: Go to Setup > Point of Sale > POS Settings and set **Invoice Type** to **POS Invoice** (required for NDS Restaurant POS)
- Run `bench --site yoursites build-search-index`

## Step 5–6: Item Groups & Items

Create Item Groups (Starters, Main Course, Beverages, Raw Materials, …) and Items (menu dishes + raw materials).

## Step 7: NDS Recipe (optional)

For ingredient tracking: create raw materials with Maintain Stock, stock receipt, buying prices, then **NDS Recipe** per menu item.

## Step 8: NDS Menu Course

Create courses with Serving Priority (and Indicate In KDS if needed).

## Step 9: NDS Restaurant

Link Company, Branch, Invoice Series Prefix, Default Room, Default Menu, tax template.

## Step 10: NDS Room

Create rooms (Indoor / Outdoor / VIP). Optionally add printer settings. Set Default Room on the restaurant.

## Step 11: NDS Menu

Add items with rates and courses. A Selling Price List is auto-created (`NDS-<menu name>`).

## Step 12: NDS Table

Create tables linked to Restaurant + Room (shape, seats, layout).

## Step 13: POS Profile

Must set: Company, Warehouse, Cost Center, Selling Price List (= menu price list), Payments, Restaurant, users, Role Allowed For Billing, **KOT Naming Series** (e.g. `KOT-.#####`).

## Step 14: NDS Production Unit

One per kitchen station; assign Item Groups for KOT routing. KDS URL: `/kotdisplay/<Production Unit>`.

## Step 15: User Permissions

Restrict users to the correct POS Profile / Branch if needed.

## Step 16–17: Printers & Report Settings

See [printing-setup.md](printing-setup.md) and [reporting-and-pl.md](reporting-and-pl.md).

## Step 18: Verify

1. Create POS Opening Entry
2. Open `/restaurant-pos`, place an order, pay
3. Confirm KOT on `/kotdisplay/...`
