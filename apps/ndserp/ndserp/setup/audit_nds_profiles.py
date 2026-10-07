"""Deep-audit NDS module Role Profiles against workspace DocTypes."""

from __future__ import annotations

from collections import defaultdict

import frappe

MODULE_WS = {
	"المبيعات NDS ERP": ("Sales Manager NDS", "Sales User NDS"),
	"حسابات NDS ERP": ("Accounts Manager NDS", "Accounts User NDS"),
	"مخازن NDS ERP": ("Stock Manager NDS", "Stock User NDS"),
	"المشتريات NDS ERP": ("Purchase Manager NDS", "Purchase User NDS"),
	"الاصول NDS ERP": ("Assets Manager NDS", "Assets User NDS"),
	"HR NDS": ("HR Manager NDS", "HR User NDS"),
	"نقاط البيع NDS ERP": ("POS Manager NDS", "POS User NDS"),
}

EXTRA = {
	"المبيعات NDS ERP": [
		"Customer",
		"Sales Invoice",
		"Sales Order",
		"Quotation",
		"Delivery Note",
		"Pick List",
		"Payment Entry",
		"Payment Request",
		"Blanket Order",
		"Dunning",
		"Sales Partner",
		"Sales Person",
		"Item",
		"Item Group",
		"Price List",
		"Item Price",
		"Product Bundle",
		"Pricing Rule",
		"Promotional Scheme",
		"Shipping Rule",
		"Coupon Code",
		"Territory",
		"Address",
		"Contact",
		"Mode of Payment",
		"Sales Taxes and Charges Template",
		"Terms and Conditions",
		"Campaign",
	],
	"حسابات NDS ERP": [
		"Account",
		"Journal Entry",
		"Payment Entry",
		"Sales Invoice",
		"Purchase Invoice",
		"Cost Center",
		"Fiscal Year",
		"Company",
		"Mode of Payment",
		"Payment Term",
		"Bank Account",
		"Bank Transaction",
		"Period Closing Voucher",
	],
	"مخازن NDS ERP": [
		"Item",
		"Warehouse",
		"Stock Entry",
		"Material Request",
		"Delivery Note",
		"Purchase Receipt",
		"Pick List",
		"Stock Reconciliation",
		"Batch",
		"Serial No",
		"Item Group",
		"UOM",
		"Brand",
	],
	"المشتريات NDS ERP": [
		"Supplier",
		"Purchase Order",
		"Purchase Invoice",
		"Purchase Receipt",
		"Material Request",
		"Item",
		"Request for Quotation",
		"Supplier Quotation",
		"Address",
		"Contact",
	],
	"الاصول NDS ERP": [
		"Asset",
		"Asset Category",
		"Asset Movement",
		"Asset Repair",
		"Asset Maintenance",
		"Location",
		"Company",
		"Item",
	],
	"HR NDS": [
		"Employee",
		"Attendance",
		"Leave Application",
		"Leave Type",
		"Expense Claim",
		"Salary Slip",
		"Payroll Entry",
		"Salary Structure",
		"Salary Structure Assignment",
		"Employee Checkin",
		"Shift Type",
		"Holiday List",
		"Department",
		"Designation",
	],
	"نقاط البيع NDS ERP": [
		"POS Profile",
		"POS Settings",
		"POS Opening Shift",
		"POS Closing Shift",
		"POS Offer",
		"POS Coupon",
		"Item",
		"Sales Invoice",
		"Customer",
		"Mode of Payment",
		"Payment Entry",
		"Warehouse",
		"Stock Entry",
		"User",
	],
}

SKIP_ROLES = {
	"Administrator",
	"System Manager",
	"All",
	"Guest",
	"Desk User",
	"Workspace Manager",
}


def workspace_doctypes(ws_name: str) -> set[str]:
	if not frappe.db.exists("Workspace", ws_name):
		return set()
	ws = frappe.get_doc("Workspace", ws_name)
	dts: set[str] = set()
	for s in ws.shortcuts or []:
		if s.type == "DocType" and s.link_to:
			dts.add(s.link_to)
	for link in ws.links or []:
		if (
			getattr(link, "type", None) == "Link"
			and getattr(link, "link_type", None) == "DocType"
			and link.link_to
		):
			dts.add(link.link_to)
	dts |= set(EXTRA.get(ws_name, []))
	return {d for d in dts if frappe.db.exists("DocType", d)}


def profile_roles(name: str) -> list[str]:
	doc = frappe.get_doc("Role Profile", name)
	return [r.role for r in doc.roles]


def doctype_perm_rows(doctype: str) -> list[dict]:
	return frappe.db.sql(
		"""
		select role, `read`, `write`, `create`, `delete`, submit, cancel
		from `tabDocPerm` where parent=%s
		union all
		select role, `read`, `write`, `create`, `delete`, submit, cancel
		from `tabCustom DocPerm` where parent=%s
		""",
		(doctype, doctype),
		as_dict=True,
	)


def perms_for_roles(roles: list[str], doctype: str) -> dict[str, bool]:
	result = {p: False for p in ("read", "write", "create", "delete", "submit", "cancel")}
	roleset = set(roles)
	for row in doctype_perm_rows(doctype):
		if row.role not in roleset:
			continue
		for p in result:
			if row.get(p):
				result[p] = True
	return result


# Gaps that are framework/site design limits — not fixable via Role Profile alone.
ACCEPTABLE_GAPS = {
	# Branch is HRMS-permissioned; not granted via Sales/Accounts roles.
	"Branch",
	# Fiscal Year write/create is System Manager only on this site.
	"Fiscal Year",
	# Singles often have create=0 for managers.
	"HR Settings",
	# No DocPerm rows exist for Employee Group on this site.
	"Employee Group",
	# No role has submit on Employee Separation.
	"Employee Separation",
	# User create is Manager-only (NDS Module Manager); User packs intentionally lack it.
	"User",
	# Period closing is Accounts Manager territory.
	"Period Closing Voucher",
	# Stock reconciliation is intentionally Stock Manager-only for User pack.
	"Stock Reconciliation",
}


def run():
	report = []
	for ws, (mgr, usr) in MODULE_WS.items():
		dts = sorted(workspace_doctypes(ws))
		mgr_roles = profile_roles(mgr)
		usr_roles = profile_roles(usr)
		print("=" * 80)
		print(f"WORKSPACE: {ws}")
		print(f"  Manager ({mgr}): {mgr_roles}")
		print(f"  User ({usr}): {usr_roles}")
		print(f"  DocTypes: {len(dts)}")

		mgr_gaps = []
		usr_gaps = []
		accepted = []
		for dt in dts:
			meta = frappe.get_meta(dt)
			is_sub = bool(meta.is_submittable)
			mp = perms_for_roles(mgr_roles, dt)
			up = perms_for_roles(usr_roles, dt)
			mgr_ok = mp["read"] and mp["write"] and mp["create"] and (mp["submit"] if is_sub else True)
			# For Singles, create is often unused — require read+write only.
			if meta.issingle:
				mgr_ok = mp["read"] and mp["write"]
			usr_ok = up["read"]
			if not mgr_ok:
				need = [p for p in ("read", "write", "create") if not mp[p]]
				if is_sub and not meta.issingle and not mp["submit"]:
					need.append("submit")
				if meta.issingle:
					need = [p for p in ("read", "write") if not mp[p]]
				if dt in ACCEPTABLE_GAPS:
					accepted.append((dt, "manager", need))
				else:
					mgr_gaps.append((dt, need, mp))
			if not usr_ok:
				if dt in ACCEPTABLE_GAPS:
					accepted.append((dt, "user", ["read"]))
				else:
					usr_gaps.append((dt, ["read"], up))

		print(f"\n  MANAGER GAPS ({len(mgr_gaps)}):")
		for dt, need, mp in mgr_gaps:
			print(
				f"    - {dt}: missing {need} "
				f"(R={int(mp['read'])} W={int(mp['write'])} C={int(mp['create'])} S={int(mp['submit'])})"
			)
		print(f"  USER GAPS (no read) ({len(usr_gaps)}):")
		for dt, need, up in usr_gaps:
			print(f"    - {dt}: missing {need}")
		if accepted:
			print(f"  ACCEPTED BY DESIGN ({len(accepted)}):")
			for dt, who, need in accepted:
				print(f"    - [{who}] {dt}: {need}")

		report.append(
			{
				"ws": ws,
				"mgr": mgr,
				"usr": usr,
				"mgr_gaps": mgr_gaps,
				"usr_gaps": usr_gaps,
				"mgr_roles": mgr_roles,
				"usr_roles": usr_roles,
			}
		)

	print("\n" + "=" * 80)
	print("SUMMARY")
	all_ok = True
	for block in report:
		mg, ug = len(block["mgr_gaps"]), len(block["usr_gaps"])
		status = "OK" if mg == 0 and ug == 0 else f"GAPS mgr={mg} user={ug}"
		if mg or ug:
			all_ok = False
		print(f"  {block['ws']}: {status}")
	print("\nOVERALL:", "PASS" if all_ok else "NEEDS ATTENTION")


if __name__ == "__main__":
	run()
