"""Complete ERPNext setup wizard for الحارثي جروب on a fresh site."""

from __future__ import annotations

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete


COMPANY = "الحارثي جروب"
ABBR = "اج"
VAT = "300000000000005"


def run(admin_password: str | None = None):
	if frappe.db.exists("Company", COMPANY):
		_apply_company_identity()
		return {"status": "already_complete", "company": COMPANY}

	args = {
		"language": "English",
		"country": "Saudi Arabia",
		"timezone": "Asia/Riyadh",
		"currency": "SAR",
		"full_name": "Administrator",
		"email": "admin@nds-sa.com",
		"company_name": COMPANY,
		"company_abbr": ABBR,
		"company_tagline": COMPANY,
		"chart_of_accounts": "Standard",
		"fy_start_date": "2026-01-01",
		"fy_end_date": "2026-12-31",
		"setup_demo": 0,
		"industry": "Services",
	}
	if admin_password:
		args["password"] = admin_password

	setup_complete(args)
	_apply_company_identity()
	frappe.db.commit()
	return {"status": "ok", "company": COMPANY}


def _apply_company_identity():
	if not frappe.db.exists("Company", COMPANY):
		frappe.throw(f"Company {COMPANY} was not created")

	frappe.db.set_value("Company", COMPANY, "tax_id", VAT)
	frappe.db.set_value("Company", COMPANY, "country", "Saudi Arabia")
	frappe.db.set_value("Company", COMPANY, "default_currency", "SAR")

	ss = frappe.get_single("System Settings")
	ss.language = "ar"
	ss.time_zone = "Asia/Riyadh"
	ss.country = "Saudi Arabia"
	ss.flags.ignore_mandatory = True
	ss.save(ignore_permissions=True)
	frappe.local.lang = "ar"

	gd = frappe.get_single("Global Defaults")
	gd.default_company = COMPANY
	gd.default_currency = "SAR"
	gd.country = "Saudi Arabia"
	gd.save(ignore_permissions=True)
