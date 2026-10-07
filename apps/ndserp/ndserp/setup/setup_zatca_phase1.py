"""One-shot setup: company addresses + ZATCA Phase 1 Business Settings."""

from __future__ import annotations

import frappe


def ensure_company_address(
	company, line1, city, state, pincode, country, building_number="0000", area=None
):
	existing = frappe.db.sql(
		"""
		SELECT dl.parent FROM `tabDynamic Link` dl
		INNER JOIN tabAddress a ON a.name = dl.parent
		WHERE dl.link_doctype='Company' AND dl.link_name=%s AND dl.parenttype='Address'
		LIMIT 1
		""",
		company,
	)
	meta = frappe.get_meta("Address")
	area = area or state
	if existing:
		addr = frappe.get_doc("Address", existing[0][0])
		addr.address_line1 = line1
		addr.city = city
		addr.state = state
		addr.pincode = pincode
		addr.country = country
		addr.is_your_company_address = 1
		if meta.has_field("custom_building_number"):
			addr.custom_building_number = building_number
		if meta.has_field("custom_area"):
			addr.custom_area = area
		addr.save(ignore_permissions=True)
		return addr.name

	addr = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": company,
			"address_type": "Billing",
			"address_line1": line1,
			"city": city,
			"state": state,
			"pincode": pincode,
			"country": country,
			"is_your_company_address": 1,
			"links": [{"link_doctype": "Company", "link_name": company}],
		}
	)
	if meta.has_field("custom_building_number"):
		addr.custom_building_number = building_number
	if meta.has_field("custom_area"):
		addr.custom_area = area
	addr.insert(ignore_permissions=True)
	return addr.name


def ensure_phase1(company, address, vat, status):
	name = frappe.db.exists("ZATCA Phase 1 Business Settings", company)
	if name:
		doc = frappe.get_doc("ZATCA Phase 1 Business Settings", name)
		doc.vat_registration_number = vat or ""
		doc.address = address
		doc.type_of_transaction = "Both"
		doc.status = status
		doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc(
		{
			"doctype": "ZATCA Phase 1 Business Settings",
			"company": company,
			"vat_registration_number": vat or "",
			"address": address,
			"type_of_transaction": "Both",
			"status": status,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def is_valid_ksa_vat(vat):
	return bool(vat) and len(str(vat)) == 15 and str(vat).isdigit() and str(vat).startswith("3")


def run():
	configs = [
		{
			"company": "NDS ERP",
			"line1": "Riyadh",
			"city": "Riyadh",
			"state": "Riyadh",
			"pincode": "11564",
			"country": "Saudi Arabia",
			"vat_from_tax_id": True,
		},
		{
			"company": "الحارثي جروب",
			"line1": "Riyadh",
			"city": "Riyadh",
			"state": "Riyadh",
			"pincode": "11564",
			"country": "Saudi Arabia",
			"building_number": "0000",
			"area": "Riyadh",
			# Live Company.tax_id is empty; Phase 1 VAT is stored on settings.
			"force_vat": "300000000000005",
			"vat_from_tax_id": True,
		},
		{
			"company": "NDS (Demo)",
			"line1": "Riyadh",
			"city": "Riyadh",
			"state": "Riyadh",
			"pincode": "11564",
			"country": "Saudi Arabia",
			# Active so existing invoices can print Phase 1 QR; replace with real VAT
			"force_vat": "300000000000003",
			"force_active": True,
		},
	]

	results = []
	for cfg in configs:
		company = cfg["company"]
		if not frappe.db.exists("Company", company):
			continue
		tax_id = frappe.db.get_value("Company", company, "tax_id")
		vat = cfg.get("force_vat") or (tax_id if cfg.get("vat_from_tax_id") else None)
		address = ensure_company_address(
			company,
			cfg["line1"],
			cfg["city"],
			cfg["state"],
			cfg["pincode"],
			cfg["country"],
			building_number=cfg.get("building_number") or "0000",
			area=cfg.get("area"),
		)
		if cfg.get("force_active"):
			status = "Active"
		elif is_valid_ksa_vat(vat):
			status = "Active"
		else:
			status = "Disabled"
		settings_name = ensure_phase1(company, address, vat, status)
		results.append(
			{
				"company": company,
				"address": address,
				"vat": vat,
				"status": status,
				"settings": settings_name,
			}
		)

	frappe.db.commit()
	return results
