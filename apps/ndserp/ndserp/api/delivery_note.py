"""
Mobile Delivery Note API (ERPNext v16).

create_delivery_note              -> creates a DRAFT Delivery Note, a linked return (full or partial; no items =
                                     everything still returnable), or an unlinked return. Same body as
                                     create_invoice, without payments. A linked return takes unbilled qty first;
                                     once nothing unbilled is left (100% billed), everything not yet returned.
calculate_delivery_note           -> same request without net_total; saves nothing and returns the totals.
create_invoice_from_delivery_note -> creates a DRAFT Sales Invoice for picked items / qty of one own,
                                     submitted Delivery Note (partial billing allowed). Stock is not moved again.
calculate_invoice_from_delivery_note -> same request without payments / net_total; saves nothing and returns
                                     the totals at the delivery note's rates.
list_delivery_notes               -> the user's own delivery notes (draft + submitted), optionally regular or returns only.
get_delivery_note                 -> full details of one own delivery note, incl. billed / pending qty per row.
print_delivery_note               -> PDF of one of the user's own delivery notes.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, strip_html

from erpnext.controllers.accounts_controller import get_taxes_and_charges
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice, make_sales_return

from ndserp.api.sales_invoice import (
	TAX_TEMPLATE_DOCTYPE,
	APIError,
	_check_payments_total,
	_check_stock,
	_check_totals,
	_get_customer,
	_get_price_list,
	_get_tax_template,
	_get_user_context,
	_handle,
	_pdf_response,
	_parse_list_request,
	_parse_request,
	_pick_return_rows,
	_pick_rows,
	_validate_items,
	_validate_payments,
)
from ndserp.api.sales_invoice import _serialize as _serialize_invoice
from ndserp.api.sales_invoice import _serialize_totals

# print_delivery_note: Frappe's built-in layout for now; swap for a custom Print Format name later
DN_PRINT_FORMAT = "Standard"
DN_LIST_FIELDS = [
	"name as delivery_note_id",
	"customer",
	"customer_name",
	"posting_date",
	"posting_time",
	"is_return",
	"return_against",
	"status",
	"docstatus",
	"currency",
	"net_total",
	"total_taxes_and_charges",
	"grand_total",
	"per_billed",
	"per_returned",
]


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@frappe.whitelist(methods=["POST"])
def create_delivery_note(**kwargs):
	"""Body: customer, posting_datetime, net_total, items[{item_code, qty, uom}],
	optional is_return, return_against, return_reason. No payments."""

	def run():
		req = _parse_request(kwargs, allow_payments=False)
		doc = _build(req)
		_check_totals(doc, req)

		doc.insert()  # draft; runs ERPNext's own validations with the user's permissions
		frappe.clear_messages()
		return {"success": True, "data": _serialize(doc)}

	return _handle(run)


@frappe.whitelist(methods=["POST"])
def calculate_delivery_note(**kwargs):
	"""Same body as create_delivery_note minus net_total (posting_datetime optional).
	Nothing is saved; all amounts in the response are positive, also for returns."""

	def run():
		req = _parse_request(kwargs, calculate_only=True, allow_payments=False)
		doc = _build(req)
		frappe.db.rollback()  # nothing to keep; releases the stock-check row locks
		frappe.clear_messages()
		return {"success": True, "data": _serialize_totals(doc)}

	return _handle(run)


@frappe.whitelist(methods=["POST"])
def create_invoice_from_delivery_note(**kwargs):
	"""Body: delivery_note_id, posting_datetime, net_total, items[{item_code, qty, uom}], optional payments.
	Only the picked items / qty are invoiced; the rest stays open on the delivery note."""

	def run():
		req = _parse_invoice_request(kwargs)
		doc = _build_invoice_from_note(req)
		_check_totals(doc, req)
		_check_payments_total(doc)

		doc.insert()  # draft
		frappe.clear_messages()
		return {"success": True, "data": _serialize_invoice(doc)}

	return _handle(run)


@frappe.whitelist(methods=["POST"])
def calculate_invoice_from_delivery_note(**kwargs):
	"""Same body as create_invoice_from_delivery_note minus payments / net_total (posting_datetime optional).
	Nothing is saved; returns the totals (VAT, grand total) of the picked items at the delivery note's rates."""

	def run():
		req = _parse_invoice_request(kwargs, calculate_only=True)
		doc = _build_invoice_from_note(req)
		frappe.db.rollback()  # nothing to keep; releases the delivery note row lock
		frappe.clear_messages()
		return {"success": True, "data": {"delivery_note_id": req.delivery_note_id, **_serialize_totals(doc)}}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def list_delivery_notes(
	note_type=None, search=None, from_date=None, to_date=None, docstatus=None, page=1, page_size=50
):
	"""Delivery notes created by the logged-in user, drafts and submitted (cancelled are hidden).
	note_type: "regular" | "return" (omit for both). Return amounts are negative (ERPNext convention)."""

	def run():
		filters, or_filters, pg, size = _parse_list_request(
			note_type, search, from_date, to_date, docstatus, page, page_size, type_param="note_type"
		)

		data = frappe.get_list(
			"Delivery Note",
			filters=filters,
			or_filters=or_filters,
			fields=DN_LIST_FIELDS,
			order_by="posting_date desc, posting_time desc, creation desc",
			start=(pg - 1) * size,
			page_length=size,
		)
		total = frappe.get_list(
			"Delivery Note", filters=filters, or_filters=or_filters, fields=[{"COUNT": "*", "as": "total"}]
		)[0].total

		for row in data:
			row.is_return = bool(row.is_return)
			row.posting_date = str(row.posting_date)
			row.posting_time = str(row.posting_time)

		frappe.clear_messages()
		return {"success": True, "page": pg, "page_size": size, "total": total, "data": data}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def get_delivery_note(delivery_note_id=None):
	"""Full details of one delivery note created by the logged-in user (draft, submitted or cancelled)."""

	def run():
		dn_id = _own_note(delivery_note_id, _("You can only view delivery notes you created"))
		doc = frappe.get_doc("Delivery Note", dn_id)
		doc.check_permission("read")

		frappe.clear_messages()
		return {"success": True, "data": _serialize_details(doc)}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def print_delivery_note(delivery_note_id=None):
	"""PDF of a delivery note created by the logged-in user.
	Success returns the PDF file itself; errors return the usual JSON body."""

	def run():
		dn_id = _own_note(delivery_note_id, _("You can only print delivery notes you created"))

		_pdf_response("Delivery Note", dn_id, DN_PRINT_FORMAT)

	return _handle(run)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #


def _build(req):
	if not frappe.has_permission("Delivery Note", "create"):
		raise APIError("NOT_PERMITTED", _("You are not allowed to create Delivery Notes"), 403)

	ctx = _get_user_context()
	customer = _get_customer(req.customer)
	if req.is_return and req.return_against:
		return _build_linked_return(req, ctx)
	return _build_note(req, ctx, customer)


def _build_note(req, ctx, customer):
	"""Normal delivery note, or return without an original note (unlinked)."""
	_validate_items(req.lines)
	price_list = _get_price_list(customer)
	tax_template = _get_tax_template(ctx.company)
	sign = -1 if req.is_return else 1

	doc = frappe.new_doc("Delivery Note")
	doc.update(
		{
			"customer": req.customer,
			"company": ctx.company,
			"posting_date": req.posting_date,
			"posting_time": req.posting_time,
			"set_posting_time": 1,
			"is_return": 1 if req.is_return else 0,
			"set_warehouse": ctx.warehouse,
			"selling_price_list": price_list,
			"ignore_pricing_rule": 1,  # no discounts: rate = price list rate
			"disable_rounded_total": 1,
		}
	)
	if doc.meta.has_field("branch"):
		doc.branch = ctx.branch
	for r in req.lines:
		doc.append(
			"items",
			{"item_code": r.item_code, "qty": sign * r.qty, "uom": r.uom, "warehouse": ctx.warehouse},
		)
	if req.is_return:
		_set_return_reason(doc, req.return_reason)

	# Fetch item details, price list rates, currency ...
	doc.set_missing_values()

	# VAT from the template chosen by our rule (set after set_missing_values so nothing overrides it)
	doc.taxes_and_charges = tax_template
	doc.set("taxes", [])
	for tax in get_taxes_and_charges(TAX_TEMPLATE_DOCTYPE, tax_template) or []:
		doc.append("taxes", tax)

	doc.calculate_taxes_and_totals()

	no_price = [row.item_code for row in doc.items if flt(row.price_list_rate) <= 0]
	if no_price:
		raise APIError(
			"ITEM_PRICE_NOT_FOUND",
			_("No price in price list {0} for some items").format(price_list),
			417,
			sorted(set(no_price)),
		)

	if not req.is_return:
		_check_stock(doc, ctx.warehouse)
	return doc


def _build_linked_return(req, ctx):
	"""Full or partial return of an original delivery note, like ERPNext's Return button: no items sent ->
	everything still returnable; items sent -> only those items / qty. Several returns are allowed.
	Unbilled first: returnable per row = delivered - invoiced - already returned (draft invoices included).
	Once nothing unbilled is left and every invoice is submitted (100% billed): returnable = delivered -
	already returned. The stock comes back here; the money goes back through an invoice return."""
	# Locking read: concurrent returns / invoices for the same note wait for each other (see _pending_rows)
	rows = frappe.db.sql(
		"""
		select name, docstatus, is_return, customer, company, posting_date, posting_time
		from `tabDelivery Note` where name = %s for update
		""",
		req.return_against,
		as_dict=True,
	)
	if not rows:
		raise APIError("ORIGINAL_NOT_FOUND", _("Delivery Note {0} not found").format(req.return_against), 404)
	orig = rows[0]
	if not frappe.has_permission("Delivery Note", "read", doc=orig.name):
		raise APIError(
			"NOT_PERMITTED", _("You are not allowed to access delivery note {0}").format(orig.name), 403
		)
	if orig.is_return:
		raise APIError("ORIGINAL_IS_RETURN", _("Delivery Note {0} is itself a return").format(orig.name))
	if orig.docstatus == 0:
		raise APIError("ORIGINAL_NOT_SUBMITTED", _("Delivery Note {0} is not submitted yet").format(orig.name))
	if orig.docstatus == 2:
		raise APIError("ORIGINAL_CANCELLED", _("Delivery Note {0} is cancelled").format(orig.name))
	if orig.customer != req.customer:
		raise APIError(
			"CUSTOMER_MISMATCH",
			_("Customer {0} does not match delivery note {1} (customer {2})").format(
				req.customer, orig.name, orig.customer
			),
		)
	if orig.company != ctx.company:
		raise APIError("COMPANY_MISMATCH", _("Delivery Note {0} belongs to another company").format(orig.name))

	orig_dt = get_datetime(f"{orig.posting_date} {orig.posting_time or '00:00:00'}")
	if req.posting_dt < orig_dt:
		raise APIError(
			"RETURN_BEFORE_ORIGINAL",
			_("Return date/time must be on or after the delivery note date/time {0}").format(orig_dt),
		)

	note_rows = _pending_rows(orig.name, for_update=True)
	# Unbilled goods are returned first. Once nothing unbilled is left and every invoice is submitted
	# (100% billed), billed goods can be returned too.
	if not any(r.pending_qty > 0 or r.draft_billed_qty > 0 for r in note_rows):
		for r in note_rows:
			r.pending_qty = max(flt(r.qty - r.returned_qty, 6), 0)
	picked = _pick_return_rows(req.lines, note_rows, "delivery note")

	other = sorted(
		{r.warehouse for r in note_rows if r.name in picked and r.warehouse and r.warehouse != ctx.warehouse}
	)
	if other:
		raise APIError(
			"WAREHOUSE_MISMATCH",
			_("Delivery Note {0} was delivered from a different warehouse than yours").format(orig.name),
			417,
			other,
		)

	# ERPNext's own mapper: copies items (negative qty), rates, taxes, warehouse, line links.
	# Then keep only the picked rows with the picked qty.
	doc = make_sales_return(orig.name)
	doc.set("items", [d for d in doc.items if picked.get(d.dn_detail)])
	for d in doc.items:
		d.qty = -1 * picked[d.dn_detail]
		d.stock_qty = flt(d.qty) * flt(d.conversion_factor or 1)
	doc.update(
		{
			"posting_date": req.posting_date,
			"posting_time": req.posting_time,
			"set_posting_time": 1,
			"disable_rounded_total": 1,
		}
	)
	_set_return_reason(doc, req.return_reason)
	doc.calculate_taxes_and_totals()
	return doc


def _set_return_reason(doc, reason):
	if not reason:  # calculate_delivery_note does not require one
		return
	text = _("Return reason: {0}").format(reason)
	if doc.meta.has_field("custom_return_reason"):
		doc.custom_return_reason = text
	else:
		doc.instructions = text


# --------------------------------------------------------------------------- #
# Invoice from delivery note
# --------------------------------------------------------------------------- #


def _parse_invoice_request(kwargs, calculate_only=False):
	dn_id = kwargs.get("delivery_note_id")
	dn_id = dn_id.strip() if isinstance(dn_id, str) else None
	if not dn_id:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, ["delivery_note_id is required"])
	# customer is taken from the delivery note; filled in so the shared parser does not ask for it
	req = _parse_request(
		{**kwargs, "customer": "-", "is_return": 0, "return_against": None}, calculate_only=calculate_only
	)
	req.delivery_note_id = dn_id
	return req


def _build_invoice_from_note(req):
	if not frappe.has_permission("Sales Invoice", "create"):
		raise APIError("NOT_PERMITTED", _("You are not allowed to create Sales Invoices"), 403)

	ctx = _get_user_context()
	dn = _get_billable_note(req.delivery_note_id, ctx, req)
	_get_customer(dn.customer)
	_validate_payments(req.payments, ctx.company)

	picked = _pick_rows(
		req.lines,
		_pending_rows(dn.name, for_update=True),
		_("Some items cannot be invoiced from this delivery note"),
		"pending_qty",
		"delivery note",
	)

	doc = make_sales_invoice(dn.name)
	doc.flags.ignore_pos_profile = True
	doc.set("items", [d for d in doc.items if picked.get(d.dn_detail)])
	for d in doc.items:
		d.qty = picked[d.dn_detail]
		d.stock_qty = flt(d.qty) * flt(d.conversion_factor or 1)
	doc.update(
		{
			"posting_date": req.posting_date,
			"posting_time": req.posting_time,
			"set_posting_time": 1,
			"update_stock": 0,  # the delivery note already moved the stock
			"disable_rounded_total": 1,
			"is_pos": 1 if req.payments else 0,
		}
	)
	doc.set("payments", [])
	for p in req.payments:
		doc.append("payments", {"mode_of_payment": p.mode_of_payment, "amount": p.amount})

	doc.calculate_taxes_and_totals()
	return doc


def _own_note(delivery_note_id, not_owner_message):
	dn_id = delivery_note_id.strip() if isinstance(delivery_note_id, str) else None
	if not dn_id:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, ["delivery_note_id is required"])

	owner = frappe.db.get_value("Delivery Note", dn_id, "owner")
	if not owner:
		raise APIError("NOT_FOUND", _("Delivery Note {0} not found").format(dn_id), 404)
	if owner != frappe.session.user:
		raise APIError("NOT_PERMITTED", not_owner_message, 403)
	return dn_id


def _get_billable_note(dn_id, ctx, req):
	# Locking read: concurrent invoices for the same note wait for each other (see _pending_rows)
	rows = frappe.db.sql(
		"""
		select name, owner, docstatus, is_return, status, customer, company, posting_date, posting_time
		from `tabDelivery Note` where name = %s for update
		""",
		dn_id,
		as_dict=True,
	)
	if not rows:
		raise APIError("NOT_FOUND", _("Delivery Note {0} not found").format(dn_id), 404)
	dn = rows[0]
	if dn.owner != frappe.session.user:
		raise APIError("NOT_PERMITTED", _("You can only invoice delivery notes you created"), 403)
	if not frappe.has_permission("Delivery Note", "read", doc=dn.name):
		raise APIError("NOT_PERMITTED", _("You are not allowed to access delivery note {0}").format(dn.name), 403)
	if dn.docstatus == 0:
		raise APIError("NOT_SUBMITTED", _("Delivery Note {0} is not submitted yet").format(dn.name))
	if dn.docstatus == 2:
		raise APIError("DN_CANCELLED", _("Delivery Note {0} is cancelled").format(dn.name))
	if dn.is_return:
		raise APIError("DN_IS_RETURN", _("Delivery Note {0} is a return").format(dn.name))
	if dn.status in ("Completed", "Closed", "Return Issued"):
		raise APIError(
			"DN_NOT_BILLABLE", _("Delivery Note {0} is {1}, nothing left to invoice").format(dn.name, dn.status)
		)
	if dn.company != ctx.company:
		raise APIError("COMPANY_MISMATCH", _("Delivery Note {0} belongs to another company").format(dn.name))

	dn_dt = get_datetime(f"{dn.posting_date} {dn.posting_time or '00:00:00'}")
	if req.posting_dt < dn_dt:
		raise APIError(
			"INVOICE_BEFORE_DELIVERY",
			_("Invoice date/time must be on or after the delivery note date/time {0}").format(dn_dt),
		)
	return dn


def _pending_rows(dn_name, for_update=False):
	"""
	Per delivery note row: qty, billed (submitted invoices), draft_billed (draft invoices),
	returned (non-cancelled returns) and pending = qty - billed - draft_billed - returned.
	Pending is what can still be invoiced or returned. Drafts are subtracted so two drafts never
	bill / return the same goods.
	for_update: locking reads, so a request that waited on the note's row lock sees the drafts the
	other request just committed (a plain read would use the transaction's older snapshot).
	"""
	lock = "for update" if for_update else ""
	rows = frappe.get_all(
		"Delivery Note Item",
		filters={"parenttype": "Delivery Note", "parent": dn_name},
		fields=["name", "idx", "item_code", "item_name", "qty", "uom", "warehouse"],
		order_by="idx asc",
	)
	billed, draft_billed = defaultdict(float), defaultdict(float)
	for dn_detail, docstatus, qty in frappe.db.sql(
		"""
		select sii.dn_detail, si.docstatus, sum(sii.qty)
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where sii.delivery_note = %s and si.docstatus < 2 and si.is_return = 0
		group by sii.dn_detail, si.docstatus
		{lock}
		""".format(lock=lock),
		dn_name,
	):
		(billed if docstatus == 1 else draft_billed)[dn_detail] += flt(qty)

	returned = dict(
		frappe.db.sql(
			"""
			select dni.dn_detail, sum(abs(dni.qty))
			from `tabDelivery Note Item` dni
			inner join `tabDelivery Note` dn on dn.name = dni.parent
			where dn.return_against = %s and dn.is_return = 1 and dn.docstatus < 2
			group by dni.dn_detail
			{lock}
			""".format(lock=lock),
			dn_name,
		)
	)

	for r in rows:
		r.billed_qty = flt(billed.get(r.name))
		r.draft_billed_qty = flt(draft_billed.get(r.name))
		r.returned_qty = flt(returned.get(r.name))
		r.pending_qty = max(flt(r.qty - r.billed_qty - r.draft_billed_qty - r.returned_qty, 6), 0)
	return rows


def _linked_invoices(dn_name):
	invoices = frappe.db.sql(
		"""
		select distinct si.name as invoice_id, si.status, si.docstatus, si.posting_date, si.grand_total
		from `tabSales Invoice` si
		inner join `tabSales Invoice Item` sii on sii.parent = si.name
		where sii.delivery_note = %s and si.docstatus < 2
		order by si.posting_date asc, si.creation asc
		""",
		dn_name,
		as_dict=True,
	)
	for i in invoices:
		i.posting_date = str(i.posting_date)
		i.grand_total = flt(i.grand_total)
	return invoices


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


def _serialize(doc):
	return {
		"delivery_note_id": doc.name,
		"status": doc.status,
		"docstatus": doc.docstatus,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"customer": doc.customer,
		"posting_date": str(doc.posting_date),
		"posting_time": str(doc.posting_time),
		"warehouse": doc.set_warehouse or (doc.items[0].warehouse if doc.items else None),
		"currency": doc.currency,
		"taxes_and_charges": doc.taxes_and_charges,
		"net_total": flt(doc.net_total),
		"total_taxes_and_charges": flt(doc.total_taxes_and_charges),
		"grand_total": flt(doc.grand_total),
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"qty": flt(d.qty),
				"uom": d.uom,
				"rate": flt(d.rate),
				"amount": flt(d.amount),
			}
			for d in doc.items
		],
	}


def _serialize_details(doc):
	customer = frappe.db.get_value(
		"Customer", doc.customer, ["tax_id", "mobile_no", "email_id"], as_dict=True
	) or frappe._dict()
	returns = frappe.get_all(
		"Delivery Note",
		filters={"return_against": doc.name, "is_return": 1, "docstatus": ["<", 2]},
		fields=["name as delivery_note_id", "status", "docstatus", "posting_date", "grand_total"],
		order_by="posting_date asc, creation asc",
	)
	for r in returns:
		r.posting_date = str(r.posting_date)
		r.grand_total = flt(r.grand_total)

	progress = {} if doc.is_return else {r.name: r for r in _pending_rows(doc.name)}

	def row_progress(d):
		p = progress.get(d.name)
		if not p:
			return {"billed_qty": 0.0, "draft_billed_qty": 0.0, "returned_qty": 0.0, "pending_qty": 0.0}
		return {
			"billed_qty": p.billed_qty,
			"draft_billed_qty": p.draft_billed_qty,
			"returned_qty": p.returned_qty,
			# only a submitted note can be invoiced
			"pending_qty": p.pending_qty if doc.docstatus == 1 else 0.0,
		}

	return {
		"delivery_note_id": doc.name,
		"status": doc.status,
		"docstatus": doc.docstatus,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"return_reason": doc.get("custom_return_reason") or (doc.instructions if doc.is_return else None),
		"returns": returns,
		"invoices": [] if doc.is_return else _linked_invoices(doc.name),
		"posting_date": str(doc.posting_date),
		"posting_time": str(doc.posting_time),
		"company": doc.company,
		"branch": doc.get("branch"),
		"warehouse": doc.set_warehouse or (doc.items[0].warehouse if doc.items else None),
		"customer": {
			"customer_id": doc.customer,
			"customer_name": doc.customer_name,
			"vat_no": doc.tax_id or customer.tax_id,
			"mobile_no": doc.contact_mobile or customer.mobile_no,
			"email": doc.contact_email or customer.email_id,
			"address": strip_html(doc.address_display or "").strip() or None,
		},
		"currency": doc.currency,
		"price_list": doc.selling_price_list,
		"taxes_and_charges": doc.taxes_and_charges,
		"total_qty": flt(doc.total_qty),
		"net_total": flt(doc.net_total),
		"discount_amount": flt(doc.discount_amount),
		"total_taxes_and_charges": flt(doc.total_taxes_and_charges),
		"grand_total": flt(doc.grand_total),
		"in_words": doc.in_words,
		"per_billed": flt(doc.per_billed),
		"per_returned": flt(doc.per_returned),
		"items": [
			{
				"row_id": d.name,
				"item_code": d.item_code,
				"item_name": d.item_name,
				"qty": flt(d.qty),
				"uom": d.uom,
				"stock_qty": flt(d.stock_qty),
				"stock_uom": d.stock_uom,
				"price_list_rate": flt(d.price_list_rate),
				"rate": flt(d.rate),
				"amount": flt(d.amount),
				"net_amount": flt(d.net_amount),
				"warehouse": d.warehouse,
				**row_progress(d),
			}
			for d in doc.items
		],
		"taxes": [
			{
				"description": t.description,
				"rate": flt(t.rate),
				"amount": flt(t.tax_amount),
				"total": flt(t.total),
			}
			for t in doc.taxes
		],
		"created_by": doc.owner,
		"creation": str(doc.creation),
		"modified": str(doc.modified),
	}
