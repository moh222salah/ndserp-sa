"""Create a 15% KSA VAT sales tax template for a company (Phase 1, no Fatoora)."""

from __future__ import annotations

import frappe


def ensure_vat_15(company: str, rate: float = 15.0):
	parent = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Tax", "is_group": 1},
		"name",
	)
	if not parent:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": ("like", "%Duties and Taxes%"), "is_group": 1},
			"name",
		) or frappe.db.get_value(
			"Account",
			{"company": company, "account_name": ("like", "%الرسوم والضرائب%"), "is_group": 1},
			"name",
		)

	if not parent:
		frappe.throw(f"No Duties and Taxes group account found for {company}")

	account_name = "VAT 15%"
	existing_account = frappe.db.get_value(
		"Account", {"company": company, "account_name": account_name}, "name"
	)
	if existing_account:
		account = existing_account
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"parent_account": parent,
				"company": company,
				"account_type": "Tax",
				"tax_rate": rate,
				"is_group": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		account = doc.name

	tax_category = frappe.db.get_value("Tax Category", {"title": "Standard rate"}, "name")
	if not tax_category:
		cat = frappe.get_doc({"doctype": "Tax Category", "title": "Standard rate"})
		if frappe.get_meta("Tax Category").has_field("custom_zatca_category"):
			cat.custom_zatca_category = "Standard rate"
		cat.insert(ignore_permissions=True, ignore_mandatory=True)
		tax_category = cat.name
	elif frappe.get_meta("Tax Category").has_field("custom_zatca_category"):
		if not frappe.db.get_value("Tax Category", tax_category, "custom_zatca_category"):
			frappe.db.set_value("Tax Category", tax_category, "custom_zatca_category", "Standard rate")

	title = "VAT 15%"
	template_name = frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": company, "title": title}, "name"
	)
	if not template_name:
		tmpl = frappe.get_doc(
			{
				"doctype": "Sales Taxes and Charges Template",
				"title": title,
				"company": company,
				"tax_category": tax_category,
				"is_default": 1,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": account,
						"description": "VAT 15%",
						"rate": rate,
					}
				],
			}
		)
		tmpl.insert(ignore_permissions=True)
		template_name = tmpl.name
	else:
		frappe.db.set_value("Sales Taxes and Charges Template", template_name, "is_default", 1)
		if tax_category:
			frappe.db.set_value(
				"Sales Taxes and Charges Template", template_name, "tax_category", tax_category
			)

	item_title = "VAT 15%"
	if not frappe.db.exists("Item Tax Template", {"company": company, "title": item_title}):
		item_tmpl = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": item_title,
				"company": company,
				"taxes": [{"tax_type": account, "tax_rate": rate}],
			}
		)
		if frappe.get_meta("Item Tax Template").has_field("custom_zatca_item_tax_category"):
			item_tmpl.custom_zatca_item_tax_category = "Standard rate"
		item_tmpl.insert(ignore_permissions=True, ignore_mandatory=True)

	return {"account": account, "template": template_name, "tax_category": tax_category}
