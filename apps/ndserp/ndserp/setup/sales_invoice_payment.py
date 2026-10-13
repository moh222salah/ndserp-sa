"""Sales Invoice: payment type + paid value captured on the invoice itself.

* Adds two fields to the Details tab (in the column under the invoice title):
  `nds_mode_of_payment` (نوع الدفع) and `nds_paid_amount` (القيمة المدفوعة).
* On submit, a non-zero paid value is settled with a submitted Payment Entry
  (Receive) allocated to this invoice, using the chosen Mode of Payment's account.

The one-click "Save = Save + Submit" behaviour lives in public/js/sales_invoice.js.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt

CUSTOM_FIELDS = {
	"Sales Invoice": [
		{
			"fieldname": "nds_mode_of_payment",
			"label": "نوع الدفع",
			"fieldtype": "Link",
			"options": "Mode of Payment",
			"insert_after": "title",
			"no_copy": 1,
			"allow_on_submit": 0,
		},
		{
			"fieldname": "nds_paid_amount",
			"label": "القيمة المدفوعة",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "nds_mode_of_payment",
			"no_copy": 1,
			"non_negative": 1,
			"description": "",
		},
	]
}


def ensure_custom_fields():
	"""Idempotent; called from install.after_migrate."""
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)


def validate(doc, method=None):
	paid = flt(doc.get("nds_paid_amount"))
	if paid < 0:
		frappe.throw(_("Paid value cannot be negative."))
	if not paid:
		return
	if doc.get("is_return") or doc.get("is_pos"):
		frappe.throw(_("Paid value is not supported on return or POS invoices."))
	if not doc.get("nds_mode_of_payment"):
		frappe.throw(_("Select the payment type for the paid value."))
	limit = flt(doc.get("rounded_total") or doc.get("grand_total"))
	if limit and paid > limit + 0.005:
		frappe.throw(_("Paid value ({0}) cannot exceed the invoice total ({1}).").format(paid, limit))


def on_submit(doc, method=None):
	paid = flt(doc.get("nds_paid_amount"))
	if not paid or doc.get("is_return") or doc.get("is_pos"):
		return

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Sales Invoice", doc.name, party_amount=paid)
	pe.mode_of_payment = doc.nds_mode_of_payment
	pe.reference_no = doc.name
	pe.reference_date = doc.posting_date
	# get_payment_entry picks the company's default cash/bank account; use the one configured
	# for the chosen Mode of Payment when it has one.
	account = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": doc.nds_mode_of_payment, "company": doc.company},
		"default_account",
	)
	if account:
		pe.paid_to = account
		pe.paid_to_account_currency = frappe.get_cached_value("Account", account, "account_currency")
	pe.flags.ignore_permissions = False
	pe.insert()
	pe.submit()
	frappe.msgprint(
		_("Payment Entry {0} created for {1}.").format(frappe.bold(pe.name), frappe.format_value(paid, "Currency")),
		alert=True,
		indicator="green",
	)
