# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

"""
POS Expenses API

Records cash expenses from the POS drawer by creating Journal Entries:
  Debit  -> Expense account (from POS Profile / selection / company fallback)
  Credit -> Cash account (from cash mode of payment)
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate, cstr

from pos_next.api.invoices import get_payment_account, _resolve_opening_shift

PREFERRED_EXPENSE_ACCOUNT_NAMES = (
	"Miscellaneous Expenses",
	"Administrative Expenses",
	"Entertainment Expenses",
	"Office Maintenance Expenses",
)


def _check_pos_access(pos_profile):
	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user},
	)
	if not has_access and not frappe.has_permission("POS Profile", "read"):
		frappe.throw(_("You don't have access to this POS Profile"))


def _get_cash_mode_of_payment(pos_profile):
	cash_mode = frappe.db.get_value("POS Profile", pos_profile, "posa_cash_mode_of_payment")
	return cash_mode or "Cash"


def _get_expense_accounts(company):
	"""Leaf expense accounts available for POS cash expenses."""
	return frappe.get_all(
		"Account",
		filters={
			"company": company,
			"root_type": "Expense",
			"is_group": 0,
			"disabled": 0,
		},
		fields=["name", "account_name"],
		order_by="account_name asc",
	)


def _validate_expense_account(account, company):
	account_doc = frappe.db.get_value(
		"Account",
		account,
		["name", "company", "root_type", "is_group", "disabled"],
		as_dict=True,
	)
	if (
		not account_doc
		or account_doc.company != company
		or account_doc.root_type != "Expense"
		or account_doc.is_group
		or account_doc.disabled
	):
		frappe.throw(
			_("Invalid expense account {0} for company {1}").format(account, company),
			title=_("Invalid Expense Account"),
		)
	return account_doc.name


def _find_preferred_expense_account(company):
	for account_name in PREFERRED_EXPENSE_ACCOUNT_NAMES:
		account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_name": account_name,
				"is_group": 0,
				"disabled": 0,
			},
			"name",
		)
		if account:
			return account
	return None


def _get_expense_account(pos_profile, company, expense_account=None):
	"""
	Resolve expense account for POS cash expenses.

	Priority:
	1. Explicit account from the dialog
	2. POS Profile.posa_expense_account (dedicated cash-expense account)
	3. POS Profile.expense_account (ERPNext stock/COGS field, if set)
	4. Preferred petty-cash style expense accounts
	5. Company default_expense_account
	6. First available expense account
	"""
	if expense_account:
		return _validate_expense_account(expense_account, company)

	profile_meta = frappe.get_meta("POS Profile")
	if profile_meta.has_field("posa_expense_account"):
		posa_expense_account = frappe.db.get_value(
			"POS Profile", pos_profile, "posa_expense_account"
		)
		if posa_expense_account:
			return posa_expense_account

	expense_account = frappe.db.get_value("POS Profile", pos_profile, "expense_account")
	if expense_account:
		return expense_account

	preferred = _find_preferred_expense_account(company)
	if preferred:
		return preferred

	company_default = frappe.get_cached_value("Company", company, "default_expense_account")
	if company_default:
		return company_default

	accounts = _get_expense_accounts(company)
	if accounts:
		return accounts[0].name

	frappe.throw(
		_("Please set Expense Account on POS Profile {0} before recording expenses").format(
			pos_profile
		),
		title=_("Expense Account Missing"),
	)


def _get_cash_account(pos_profile, company):
	cash_mode = _get_cash_mode_of_payment(pos_profile)
	account_info = get_payment_account(cash_mode, company)
	return account_info.get("account")


@frappe.whitelist()
def get_expense_dialog_data(pos_profile):
	"""Return account labels and selectable expense accounts for the POS expense dialog."""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	_check_pos_access(pos_profile)

	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	company = profile_doc.company
	expense_accounts = _get_expense_accounts(company)
	expense_account = _get_expense_account(pos_profile, company)
	cash_account = _get_cash_account(pos_profile, company)
	cash_mode = _get_cash_mode_of_payment(pos_profile)

	return {
		"expense_account": expense_account,
		"expense_account_label": frappe.db.get_value("Account", expense_account, "account_name")
		or expense_account,
		"expense_accounts": expense_accounts,
		"cash_account": cash_account,
		"cash_account_label": frappe.db.get_value("Account", cash_account, "account_name")
		or cash_account,
		"cash_mode_of_payment": cash_mode,
		"currency": profile_doc.currency or frappe.get_cached_value("Company", company, "default_currency"),
	}


@frappe.whitelist()
def create_pos_expense(pos_profile, amount, notes=None, pos_opening_shift=None, expense_account=None):
	"""
	Create a cash expense Journal Entry for the active POS shift.

	Args:
		pos_profile: POS Profile name
		amount: Expense amount (positive number)
		notes: Optional description shown in user remark
		pos_opening_shift: Optional opening shift name (auto-resolved when omitted)
		expense_account: Optional expense account override from the dialog
	"""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	_check_pos_access(pos_profile)

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Expense amount must be greater than zero"))

	notes = cstr(notes).strip()

	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	company = profile_doc.company
	expense_account = _get_expense_account(pos_profile, company, expense_account=expense_account)
	cash_account = _get_cash_account(pos_profile, company)
	cost_center = profile_doc.cost_center or frappe.get_cached_value("Company", company, "cost_center")

	opening_shift = _resolve_opening_shift(pos_profile, pos_opening_shift)
	if not opening_shift:
		frappe.throw(_("No open shift found. Please open a shift before recording expenses"))

	user_remark = notes or _("POS Expense")
	if notes:
		user_remark = _("POS Expense: {0}").format(notes)

	jv_doc = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Cash Entry",
			"posting_date": nowdate(),
			"company": company,
			"user_remark": user_remark[:140],
			"posa_pos_opening_shift": opening_shift,
			"posa_is_pos_expense": 1,
		}
	)

	debit_row = jv_doc.append("accounts", {})
	debit_row.update(
		{
			"account": expense_account,
			"debit_in_account_currency": amount,
			"credit_in_account_currency": 0,
			"cost_center": cost_center,
		}
	)

	credit_row = jv_doc.append("accounts", {})
	credit_row.update(
		{
			"account": cash_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": amount,
			"cost_center": cost_center,
		}
	)

	jv_doc.flags.ignore_permissions = True
	jv_doc.save()
	jv_doc.submit()

	return {
		"success": True,
		"journal_entry": jv_doc.name,
		"amount": amount,
		"notes": notes,
		"expense_account": expense_account,
		"cash_account": cash_account,
		"pos_opening_shift": opening_shift,
		"message": _("Expense {0} recorded successfully").format(
			frappe.format_value(amount, {"fieldtype": "Currency"})
		),
	}


@frappe.whitelist()
def get_pos_expenses(pos_opening_shift):
	"""List submitted POS expense journal entries for an opening shift."""
	if not pos_opening_shift:
		frappe.throw(_("POS Opening Shift is required"))

	return frappe.get_all(
		"Journal Entry",
		filters={
			"docstatus": 1,
			"posa_pos_opening_shift": pos_opening_shift,
			"posa_is_pos_expense": 1,
		},
		fields=["name", "total_debit", "user_remark", "posting_date", "creation"],
		order_by="posting_date desc, creation desc",
	)
