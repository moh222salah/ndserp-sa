"""
Mobile Payment API (ERPNext v16).

get_payment_types -> enabled modes of payment.
create_payment    -> creates a DRAFT Payment Entry for a customer:
                     "receive" (default): money from the customer, allocated automatically to the oldest
                     unpaid invoices; any rest stays as advance.
                     "pay": refund to the customer, allocated automatically to the oldest open credit notes;
                     any rest stays unallocated (refund of the customer's advances).
list_payments     -> the user's own customer payments, receive and pay (draft + submitted).
get_payment       -> full details of one of the user's own payments.
print_payment     -> PDF of one of the user's own payments.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, get_datetime, now_datetime

from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
from erpnext.accounts.party import get_party_account

from ndserp.api.sales_invoice import (
	FUTURE_SKEW_MINUTES,
	APIError,
	_get_customer,
	_get_user_context,
	_handle,
	_parse_list_filters,
	_pdf_response,
)

PAYMENT_TYPES = {"receive": "Receive", "pay": "Pay"}
PAYMENT_LIST_FIELDS = [
	"name as payment_id",
	"payment_type",
	"party as customer",
	"party_name as customer_name",
	"posting_date",
	"custom_posting_time as posting_time",
	"mode_of_payment",
	"status",
	"docstatus",
	"paid_to_account_currency as currency",
	"paid_amount",
	"total_allocated_amount",
	"unallocated_amount",
]
# print_payment: Frappe's built-in layout for now; swap for a custom Print Format name later
PAYMENT_PRINT_FORMAT = "Standard"


@frappe.whitelist(methods=["GET"])
def get_payment_types(company=None):
	filters = [["Mode of Payment", "enabled", "=", 1]]
	if company:
		# only modes that have an account set up for this company
		filters.append(["Mode of Payment Account", "company", "=", company])

	data = frappe.get_list(
		"Mode of Payment",
		filters=filters,
		fields=["name as payment_id", "mode_of_payment as payment_name"],
		order_by="mode_of_payment asc",
		distinct=True,
	)
	return {"success": True, "data": data}


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@frappe.whitelist(methods=["POST"])
def create_payment(**kwargs):
	"""Body: customer, mode_of_payment, amount (positive), posting_datetime ('YYYY-MM-DD HH:MM:SS'),
	optional payment_type: "receive" (default) | "pay" (refund to the customer)."""

	def run():
		req = _parse_request(kwargs)
		if not frappe.has_permission("Payment Entry", "create"):
			raise APIError("NOT_PERMITTED", _("You are not allowed to create Payment Entries"), 403)

		ctx = _get_user_context()
		_get_customer(req.customer)
		bank_account = _get_paid_to_account(req.mode_of_payment, ctx.company)
		party_account = get_party_account("Customer", req.customer, ctx.company)
		receive = req.payment_type == "Receive"

		doc = frappe.new_doc("Payment Entry")
		doc.update(
			{
				"payment_type": req.payment_type,
				"company": ctx.company,
				"posting_date": req.posting_date,
				"custom_posting_time": req.posting_time,
				"mode_of_payment": req.mode_of_payment,
				"party_type": "Customer",
				"party": req.customer,
				"paid_from": party_account if receive else bank_account,
				"paid_to": bank_account if receive else party_account,
				"paid_amount": req.amount,
				"received_amount": req.amount,
			}
		)
		if doc.meta.has_field("branch"):
			doc.branch = ctx.branch

		if receive:
			allocations = _allocate(req.customer, ctx.company, party_account, req.amount)
		else:
			allocations = _allocate_credit_notes(req.customer, ctx.company, party_account, req.amount)
		for inv_name, allocated, outstanding in allocations:
			doc.append(
				"references",
				{
					"reference_doctype": "Sales Invoice",
					"reference_name": inv_name,
					"allocated_amount": allocated,
					"outstanding_amount": outstanding,
				},
			)

		# ERPNext requires a reference for Bank accounts; the app does not send one
		if frappe.get_cached_value("Account", bank_account, "account_type") == "Bank":
			doc.reference_no = f"{req.mode_of_payment} {req.posting_dt}"
			doc.reference_date = req.posting_date

		doc.insert()  # draft; runs ERPNext's own validations with the user's permissions
		frappe.clear_messages()
		return {"success": True, "data": _serialize(doc)}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def list_payments(
	payment_type=None, search=None, from_date=None, to_date=None, docstatus=None, page=1, page_size=50
):
	"""Customer payments created by the logged-in user, drafts and submitted (cancelled are hidden).
	payment_type: "receive" | "pay" (omit for both)."""

	def run():
		type_ = (payment_type or "").strip().lower()
		errors = [] if not type_ or type_ in PAYMENT_TYPES else ["payment_type must be 'receive' or 'pay'"]
		filters, pg, size = _parse_list_filters(from_date, to_date, docstatus, page, page_size, errors)
		filters["payment_type"] = PAYMENT_TYPES[type_] if type_ else ["in", list(PAYMENT_TYPES.values())]
		filters["party_type"] = "Customer"

		or_filters = None
		if search and search.strip():
			like = f"%{search.strip()}%"
			or_filters = {"name": ["like", like], "party": ["like", like], "party_name": ["like", like]}

		data = frappe.get_list(
			"Payment Entry",
			filters=filters,
			or_filters=or_filters,
			fields=PAYMENT_LIST_FIELDS,
			order_by="posting_date desc, custom_posting_time desc, creation desc",
			start=(pg - 1) * size,
			page_length=size,
		)
		total = frappe.get_list(
			"Payment Entry", filters=filters, or_filters=or_filters, fields=[{"COUNT": "*", "as": "total"}]
		)[0].total

		for row in data:
			row.posting_date = str(row.posting_date)
			row.posting_time = str(row.posting_time) if row.posting_time else None

		frappe.clear_messages()
		return {"success": True, "page": pg, "page_size": size, "total": total, "data": data}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def get_payment(payment_id=None):
	"""Full details of one payment created by the logged-in user (draft, submitted or cancelled)."""

	def run():
		payment_id_ = payment_id.strip() if isinstance(payment_id, str) else None
		if not payment_id_:
			raise APIError("INVALID_REQUEST", _("Invalid request"), 417, ["payment_id is required"])

		pe = frappe.db.get_value("Payment Entry", payment_id_, ["owner", "payment_type"], as_dict=True)
		if not pe or pe.payment_type not in PAYMENT_TYPES.values():
			raise APIError("NOT_FOUND", _("Payment {0} not found").format(payment_id_), 404)
		if pe.owner != frappe.session.user:
			raise APIError("NOT_PERMITTED", _("You can only view payments you created"), 403)

		doc = frappe.get_doc("Payment Entry", payment_id_)
		doc.check_permission("read")

		frappe.clear_messages()
		return {"success": True, "data": _serialize(doc)}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def print_payment(payment_id=None):
	"""PDF of a payment created by the logged-in user.
	Success returns the PDF file itself; errors return the usual JSON body."""

	def run():
		payment_id_ = payment_id.strip() if isinstance(payment_id, str) else None
		if not payment_id_:
			raise APIError("INVALID_REQUEST", _("Invalid request"), 417, ["payment_id is required"])

		pe = frappe.db.get_value(
			"Payment Entry", payment_id_, ["name", "owner", "payment_type"], as_dict=True
		)
		if not pe or pe.payment_type not in PAYMENT_TYPES.values():
			raise APIError("NOT_FOUND", _("Payment {0} not found").format(payment_id_), 404)
		if pe.owner != frappe.session.user:
			raise APIError("NOT_PERMITTED", _("You can only print payments you created"), 403)

		_pdf_response("Payment Entry", pe.name, PAYMENT_PRINT_FORMAT)

	return _handle(run)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _parse_request(kw):
	data = frappe._dict(kw)
	errors = []
	req = frappe._dict()

	for field in ("customer", "mode_of_payment", "posting_datetime"):
		value = data.get(field)
		value = value.strip() if isinstance(value, str) else None
		if not value:
			errors.append(f"{field} is required")
		req[field] = value

	payment_type = data.get("payment_type")
	payment_type = payment_type.strip().lower() if isinstance(payment_type, str) and payment_type.strip() else "receive"
	if payment_type not in PAYMENT_TYPES:
		errors.append("payment_type must be 'receive' or 'pay'")
	req.payment_type = PAYMENT_TYPES.get(payment_type)

	amount = data.get("amount")
	req.amount = None
	if isinstance(amount, bool) or amount in (None, ""):
		errors.append("amount is required and must be a number")
	else:
		try:
			req.amount = float(amount)
			if not math.isfinite(req.amount) or req.amount <= 0:
				errors.append("amount must be greater than 0")
		except (TypeError, ValueError):
			errors.append("amount must be a number")

	req.posting_dt = None
	if req.posting_datetime:
		try:
			req.posting_dt = get_datetime(req.posting_datetime)
		except Exception:
			errors.append("posting_datetime must be 'YYYY-MM-DD HH:MM:SS'")
	if req.posting_dt and req.posting_dt > add_to_date(now_datetime(), minutes=FUTURE_SKEW_MINUTES):
		errors.append("posting_datetime cannot be in the future")

	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)

	req.posting_date = req.posting_dt.date()
	req.posting_time = req.posting_dt.strftime("%H:%M:%S")
	return req


def _get_paid_to_account(mode_of_payment, company):
	mop = frappe.db.get_value("Mode of Payment", mode_of_payment, ["name", "enabled"], as_dict=True)
	if not mop:
		raise APIError("INVALID_PAYMENTS", _("Mode of payment {0} not found").format(mode_of_payment), 404)
	if not mop.enabled:
		raise APIError("INVALID_PAYMENTS", _("Mode of payment {0} is disabled").format(mode_of_payment))
	if not frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	):
		raise APIError(
			"INVALID_PAYMENTS",
			_("Mode of payment {0} has no default account for company {1}").format(mode_of_payment, company),
		)
	return get_bank_cash_account(mode_of_payment, company)["account"]


def _allocate(customer, company, party_account, amount):
	"""
	Oldest unpaid invoices first (by due date, then posting date).
	open = outstanding_amount - amounts already allocated on DRAFT payment entries,
	so two draft payments never claim the same money. Locking reads (FOR UPDATE) make
	concurrent requests for the same customer wait for each other.
	Returns [(invoice, allocated, outstanding)].
	"""
	invoices = frappe.db.sql(
		"""
		select name, outstanding_amount
		from `tabSales Invoice`
		where docstatus = 1 and is_return = 0 and outstanding_amount > 0
			and customer = %s and company = %s and debit_to = %s
		order by due_date asc, posting_date asc, posting_time asc, name asc
		for update
		""",
		(customer, company, party_account),
		as_dict=True,
	)
	if not invoices:
		return []

	in_drafts = dict(
		frappe.db.sql(
			"""
			select per.reference_name, sum(per.allocated_amount)
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			where pe.docstatus = 0
				and per.reference_doctype = 'Sales Invoice'
				and per.reference_name in %s
			group by per.reference_name
			""",
			(tuple(i.name for i in invoices),),
		)
	)

	rows, left = [], flt(amount, 2)
	for inv in invoices:
		if left <= 0:
			break
		open_amount = flt(flt(inv.outstanding_amount) - flt(in_drafts.get(inv.name)), 2)
		if open_amount <= 0:
			continue
		allocated = min(open_amount, left)
		rows.append((inv.name, allocated, flt(inv.outstanding_amount)))
		left = flt(left - allocated, 2)
	return rows


def _allocate_credit_notes(customer, company, party_account, amount):
	"""
	Refund: oldest open credit notes first (submitted Sales Invoices with negative outstanding).
	open = |outstanding| - amounts already allocated on DRAFT payment entries.
	Allocated / outstanding amounts are negative, as ERPNext's own refund from a credit note.
	Returns [(credit note, allocated, outstanding)].
	"""
	notes = frappe.db.sql(
		"""
		select name, outstanding_amount
		from `tabSales Invoice`
		where docstatus = 1 and outstanding_amount < 0
			and customer = %s and company = %s and debit_to = %s
		order by posting_date asc, posting_time asc, name asc
		for update
		""",
		(customer, company, party_account),
		as_dict=True,
	)
	if not notes:
		return []

	in_drafts = dict(
		frappe.db.sql(
			"""
			select per.reference_name, sum(abs(per.allocated_amount))
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			where pe.docstatus = 0
				and per.reference_doctype = 'Sales Invoice'
				and per.reference_name in %s
			group by per.reference_name
			""",
			(tuple(n.name for n in notes),),
		)
	)

	rows, left = [], flt(amount, 2)
	for note in notes:
		if left <= 0:
			break
		open_amount = flt(abs(flt(note.outstanding_amount)) - flt(in_drafts.get(note.name)), 2)
		if open_amount <= 0:
			continue
		allocated = min(open_amount, left)
		rows.append((note.name, -allocated, flt(note.outstanding_amount)))
		left = flt(left - allocated, 2)
	return rows


def _serialize(doc):
	return {
		"payment_id": doc.name,
		"payment_type": doc.payment_type,
		"status": doc.status,
		"docstatus": doc.docstatus,
		"posting_date": str(doc.posting_date),
		"posting_time": str(doc.custom_posting_time) if doc.get("custom_posting_time") else None,
		"company": doc.company,
		"branch": doc.get("branch"),
		"customer": {"customer_id": doc.party, "customer_name": doc.party_name},
		"mode_of_payment": doc.mode_of_payment,
		# currency of the bank / cash side
		"currency": doc.paid_to_account_currency if doc.payment_type == "Receive" else doc.paid_from_account_currency,
		"paid_amount": flt(doc.paid_amount),
		"total_allocated_amount": flt(doc.total_allocated_amount),
		"unallocated_amount": flt(doc.unallocated_amount),
		"in_words": doc.get("in_words"),
		"reference_no": doc.reference_no,
		"reference_date": str(doc.reference_date) if doc.reference_date else None,
		"invoices": [
			{
				"invoice_id": r.reference_name,
				"due_date": str(r.due_date) if r.due_date else None,
				"invoice_total": flt(r.total_amount),
				"outstanding_amount": flt(r.outstanding_amount),
				"allocated_amount": flt(r.allocated_amount),
			}
			for r in doc.references
		],
		"created_by": doc.owner,
		"creation": str(doc.creation),
		"modified": str(doc.modified),
	}
