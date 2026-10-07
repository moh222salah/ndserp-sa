"""
Mobile Sales Invoice API (ERPNext v16).

create_invoice     -> creates a DRAFT Sales Invoice, a linked return (full or partial; no items =
                      everything still returnable), or an unlinked return. Returns the invoice id.
calculate_invoice  -> same request without payments / net_total; saves nothing and returns
                      the calculated totals (VAT, grand total) so the app knows what to collect.
list_invoices      -> the user's own invoices (draft + submitted), optionally regular or returns only.
get_invoice        -> full details (customer, items, taxes, payments, status, returns) of one own invoice.
print_invoice      -> PDF of one of the user's own invoices, A4 (ZATCA) or receipt (POS Next).
"""

import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime, strip_html

from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.controllers.accounts_controller import get_taxes_and_charges

from ndserp.api.utils import default_price_lists, error, get_company, parse_paging, resolve_assignment

# Allowed difference between the app's totals and ERPNext's calculated totals.
TOTAL_TOLERANCE = 0.05
# Allowed clock drift for a posting datetime slightly in the future (mobile clocks).
FUTURE_SKEW_MINUTES = 5
TAX_TEMPLATE_DOCTYPE = "Sales Taxes and Charges Template"
# list_invoices: invoice_type value -> is_return
INVOICE_TYPES = {"regular": 0, "return": 1}
# print_invoice: print_type value -> Print Format
PRINT_FORMATS = {"a4": "ZATCA Tax Invoice", "receipt": "POS Next Receipt"}
LIST_FIELDS = [
	"name as invoice_id",
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
	"paid_amount",
	"outstanding_amount",
]


class APIError(Exception):
	def __init__(self, code, message, http_status=417, errors=None):
		super().__init__(message)
		self.code = code
		self.message = message
		self.http_status = http_status
		self.errors = errors or []


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #


@frappe.whitelist(methods=["POST"])
def create_invoice(**kwargs):
	def run():
		req = _parse_request(kwargs)
		doc = _build(req)
		_check_totals(doc, req)

		doc.insert()  # draft; runs ERPNext's own validations with the user's permissions
		return _ok(doc)

	return _handle(run)


@frappe.whitelist(methods=["POST"])
def calculate_invoice(**kwargs):
	"""Same body as create_invoice minus payments / net_total (posting_datetime optional).
	Nothing is saved; all amounts in the response are positive, also for returns."""

	def run():
		req = _parse_request(kwargs, calculate_only=True)
		doc = _build(req)
		frappe.db.rollback()  # nothing to keep; releases the stock-check row locks
		frappe.clear_messages()
		return {"success": True, "data": _serialize_totals(doc)}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def list_invoices(
	invoice_type=None, search=None, from_date=None, to_date=None, docstatus=None, page=1, page_size=50
):
	"""Invoices created by the logged-in user, drafts and submitted (cancelled are hidden).
	invoice_type: "regular" | "return" (omit for both). Return amounts are negative (ERPNext convention)."""

	def run():
		filters, or_filters, pg, size = _parse_list_request(
			invoice_type, search, from_date, to_date, docstatus, page, page_size
		)
		data = frappe.get_list(
			"Sales Invoice",
			filters=filters,
			or_filters=or_filters,
			fields=LIST_FIELDS,
			order_by="posting_date desc, posting_time desc, creation desc",
			start=(pg - 1) * size,
			page_length=size,
		)
		total = frappe.get_list(
			"Sales Invoice", filters=filters, or_filters=or_filters, fields=[{"COUNT": "*", "as": "total"}]
		)[0].total

		for row in data:
			row.is_return = bool(row.is_return)
			row.posting_date = str(row.posting_date)
			row.posting_time = str(row.posting_time)

		frappe.clear_messages()
		return {"success": True, "page": pg, "page_size": size, "total": total, "data": data}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def get_invoice(invoice_id=None):
	"""Full details of one invoice created by the logged-in user (draft, submitted or cancelled).
	Return amounts are negative (ERPNext convention), same as list_invoices."""

	def run():
		invoice_id_ = invoice_id.strip() if isinstance(invoice_id, str) else None
		if not invoice_id_:
			raise APIError("INVALID_REQUEST", _("Invalid request"), 417, ["invoice_id is required"])

		owner = frappe.db.get_value("Sales Invoice", invoice_id_, "owner")
		if not owner:
			raise APIError("NOT_FOUND", _("Sales Invoice {0} not found").format(invoice_id_), 404)
		if owner != frappe.session.user:
			raise APIError("NOT_PERMITTED", _("You can only view invoices you created"), 403)

		doc = frappe.get_doc("Sales Invoice", invoice_id_)
		doc.check_permission("read")

		frappe.clear_messages()
		return {"success": True, "data": _serialize_details(doc)}

	return _handle(run)


@frappe.whitelist(methods=["GET"])
def print_invoice(invoice_id=None, print_type=None):
	"""PDF of an invoice created by the logged-in user.
	print_type: "a4" (ZATCA Tax Invoice) | "receipt" (POS Next Receipt).
	Success returns the PDF file itself; errors return the usual JSON body."""

	def run():
		invoice_id_, print_format = _parse_print_request(invoice_id, print_type)

		inv = frappe.db.get_value("Sales Invoice", invoice_id_, ["name", "owner"], as_dict=True)
		if not inv:
			raise APIError("NOT_FOUND", _("Sales Invoice {0} not found").format(invoice_id_), 404)
		if inv.owner != frappe.session.user:
			raise APIError("NOT_PERMITTED", _("You can only print invoices you created"), 403)

		_pdf_response("Sales Invoice", inv.name, print_format)

	return _handle(run)


def _pdf_response(doctype, name, print_format):
	"""Send the document as a PDF file. "Standard" is Frappe's built-in layout, not a Print Format record."""
	if print_format != "Standard" and not frappe.db.get_value(
		"Print Format", {"name": print_format, "disabled": 0}
	):
		raise APIError(
			"PRINT_FORMAT_NOT_FOUND", _("Print format {0} is not available").format(print_format), 417
		)

	pdf = frappe.get_print(doctype, name, print_format, as_pdf=True, no_letterhead=1)

	frappe.clear_messages()
	frappe.local.response.filename = f"{name}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


def _parse_print_request(invoice_id, print_type):
	errors = []
	invoice_id = invoice_id.strip() if isinstance(invoice_id, str) else None
	if not invoice_id:
		errors.append("invoice_id is required")

	print_type = print_type.strip().lower() if isinstance(print_type, str) else ""
	if print_type not in PRINT_FORMATS:
		errors.append("print_type must be 'a4' or 'receipt'")

	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)
	return invoice_id, PRINT_FORMATS[print_type]


def _parse_list_request(
	invoice_type, search, from_date, to_date, docstatus, page, page_size, type_param="invoice_type"
):
	"""Invoice / delivery note list filters. type_param is the request field name, used in the error text."""
	errors = []
	invoice_type = (invoice_type or "").strip().lower()
	if invoice_type and invoice_type not in INVOICE_TYPES:
		errors.append(f"{type_param} must be 'regular' or 'return'")

	filters, pg, size = _parse_list_filters(from_date, to_date, docstatus, page, page_size, errors)
	if invoice_type in INVOICE_TYPES:
		filters["is_return"] = INVOICE_TYPES[invoice_type]

	or_filters = None
	if search and search.strip():
		like = f"%{search.strip()}%"
		or_filters = {"name": ["like", like], "customer": ["like", like], "customer_name": ["like", like]}
	return filters, or_filters, pg, size


def _parse_list_filters(from_date, to_date, docstatus, page, page_size, errors=None):
	"""Common list filters: own documents, draft + submitted, date range, paging.
	Raises INVALID_REQUEST with `errors` (plus any found here)."""
	errors = errors if errors is not None else []
	filters = {"owner": frappe.session.user, "docstatus": ["in", [0, 1]]}

	if docstatus not in (None, ""):
		if str(docstatus) in ("0", "1"):
			filters["docstatus"] = cint(docstatus)
		else:
			errors.append("docstatus must be 0 (draft) or 1 (submitted)")

	dates = {}
	for field, value in (("from_date", from_date), ("to_date", to_date)):
		if value:
			try:
				dates[field] = getdate(value)
			except Exception:
				errors.append(f"{field} must be 'YYYY-MM-DD'")
	if "from_date" in dates and "to_date" in dates:
		if dates["from_date"] > dates["to_date"]:
			errors.append("from_date must be on or before to_date")
		filters["posting_date"] = ["between", [dates["from_date"], dates["to_date"]]]
	elif "from_date" in dates:
		filters["posting_date"] = [">=", dates["from_date"]]
	elif "to_date" in dates:
		filters["posting_date"] = ["<=", dates["to_date"]]

	pg, size, paging_error = parse_paging(page, page_size)
	if paging_error:
		errors.append(paging_error)

	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)
	return filters, pg, size


def _build(req):
	if not frappe.has_permission("Sales Invoice", "create"):
		raise APIError("NOT_PERMITTED", _("You are not allowed to create Sales Invoices"), 403)

	ctx = _get_user_context()
	customer = _get_customer(req.customer)

	if req.is_return and req.return_against:
		return _build_linked_return(req, ctx)
	return _build_invoice(req, ctx, customer)


def _handle(run):
	try:
		return run()

	except APIError as e:
		return _fail(e.http_status, e.code, e.message, e.errors)

	except frappe.PermissionError as e:
		return _fail(403, "NOT_PERMITTED", _clean(e) or _("Not permitted"))

	except frappe.DoesNotExistError as e:
		return _fail(404, "NOT_FOUND", _clean(e))

	except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
		return _fail(409, "BUSY", _("Stock is being updated by another request, please try again"))

	except frappe.ValidationError as e:
		# Any ERPNext validation we did not pre-check (accounts setup, UOM must be whole number, ...)
		return _fail(417, "ERP_VALIDATION", _clean(e))


# --------------------------------------------------------------------------- #
# Request parsing
# --------------------------------------------------------------------------- #


def _parse_request(kw, calculate_only=False, allow_payments=True):
	data = frappe._dict(kw)
	errors = []
	if not allow_payments and data.get("payments"):
		errors.append("payments are not allowed here")

	def required_str(field):
		value = data.get(field)
		value = value.strip() if isinstance(value, str) else value
		if not value or not isinstance(value, str):
			errors.append(f"{field} is required")
			return None
		return value

	def number(value, field):
		if isinstance(value, bool) or value in (None, ""):
			errors.append(f"{field} is required and must be a number")
			return None
		try:
			value = float(value)
		except (TypeError, ValueError):
			errors.append(f"{field} must be a number")
			return None
		if not math.isfinite(value):
			errors.append(f"{field} must be a finite number")
			return None
		return value

	def as_list(field):
		value = data.get(field) or []
		if isinstance(value, str):
			try:
				value = frappe.parse_json(value)
			except Exception:
				errors.append(f"{field} must be a list")
				return []
		if not isinstance(value, list):
			errors.append(f"{field} must be a list")
			return []
		return value

	req = frappe._dict()
	req.customer = required_str("customer")
	req.is_return = data.get("is_return") in (True, 1, "1", "true", "True")
	req.return_against = (data.get("return_against") or "").strip() or None
	req.return_reason = (data.get("return_reason") or "").strip() or None
	if req.is_return and not req.return_reason and not calculate_only:
		errors.append("return_reason is required for returns")
	if req.return_against and not req.is_return:
		errors.append("return_against is only allowed when is_return is true")

	# Posting date/time
	req.posting_dt = None
	if calculate_only and not data.get("posting_datetime"):
		data.posting_datetime = str(now_datetime())
	raw_dt = required_str("posting_datetime")
	if raw_dt:
		try:
			req.posting_dt = get_datetime(raw_dt)
		except Exception:
			errors.append("posting_datetime must be 'YYYY-MM-DD HH:MM:SS'")
	if req.posting_dt and req.posting_dt > add_to_date(now_datetime(), minutes=FUTURE_SKEW_MINUTES):
		errors.append("posting_datetime cannot be in the future")

	# Client net total (before VAT; positive, also for returns). VAT and grand total are calculated here.
	req.net_total = None if calculate_only else number(data.get("net_total"), "net_total")
	if req.net_total is not None and req.net_total < 0:
		errors.append("net_total must be positive (send positive values for returns too)")

	# Items (a linked return without items returns everything still returnable, like ERPNext's Return button)
	req.lines = []
	raw_items = as_list("items")
	if not raw_items and not (req.is_return and req.return_against):
		errors.append("items must contain at least one item")
	for idx, row in enumerate(raw_items, 1):
		if not isinstance(row, dict):
			errors.append(f"items row {idx}: must be an object")
			continue
		code = (row.get("item_code") or "").strip() if isinstance(row.get("item_code"), str) else None
		if not code:
			errors.append(f"items row {idx}: item_code is required")
		qty = number(row.get("qty"), f"items row {idx}: qty")
		if qty is not None and qty <= 0:
			errors.append(f"items row {idx}: qty must be greater than 0 (send positive qty for returns too)")
		uom = row.get("uom").strip() if isinstance(row.get("uom"), str) and row.get("uom").strip() else None
		req.lines.append(frappe._dict(item_code=code, qty=qty, uom=uom))

	# Payments (optional: empty list = credit invoice)
	req.payments = []
	seen_modes = set()
	for idx, row in enumerate([] if calculate_only or not allow_payments else as_list("payments"), 1):
		if not isinstance(row, dict):
			errors.append(f"payments row {idx}: must be an object")
			continue
		mode = (row.get("mode_of_payment") or "").strip() if isinstance(row.get("mode_of_payment"), str) else None
		if not mode:
			errors.append(f"payments row {idx}: mode_of_payment is required")
		elif mode in seen_modes:
			errors.append(f"payments row {idx}: mode_of_payment {mode} is repeated")
		seen_modes.add(mode)
		amount = number(row.get("amount"), f"payments row {idx}: amount")
		if amount is not None and amount <= 0:
			errors.append(f"payments row {idx}: amount must be greater than 0 (send positive amounts for returns too)")
		req.payments.append(frappe._dict(mode_of_payment=mode, amount=amount))

	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)

	req.posting_date = req.posting_dt.date()
	req.posting_time = req.posting_dt.strftime("%H:%M:%S")
	return req


# --------------------------------------------------------------------------- #
# User / master data lookups
# --------------------------------------------------------------------------- #


def _get_user_context():
	"""Branch, warehouse and company: same helpers as the login API."""
	user = frappe.session.user
	branch, warehouse, errors = resolve_assignment(user)
	if errors:
		raise APIError("ACCOUNT_SETUP_INCOMPLETE", _("Account setup incomplete"), 403, errors)

	company = get_company(warehouse)
	if not company:
		raise APIError(
			"ACCOUNT_SETUP_INCOMPLETE",
			_("Account setup incomplete"),
			403,
			[f"Warehouse {warehouse} not found or has no company"],
		)
	return frappe._dict(user=user, branch=branch, warehouse=warehouse, company=company)


def _get_customer(name):
	customer = frappe.db.get_value("Customer", name, ["name", "disabled", "default_price_list"], as_dict=True)
	if not customer:
		raise APIError("CUSTOMER_NOT_FOUND", _("Customer {0} not found").format(name), 404)
	if customer.disabled:
		raise APIError("CUSTOMER_DISABLED", _("Customer {0} is disabled").format(name))
	if not frappe.has_permission("Customer", "read", doc=name):
		raise APIError("CUSTOMER_NOT_PERMITTED", _("You are not allowed to use customer {0}").format(name), 403)
	return customer


def _get_price_list(customer):
	"""Customer's default price list, otherwise the default selling list (same helper as the Item API)."""
	price_list = customer.default_price_list or default_price_lists()[0]
	pl = frappe.db.get_value("Price List", price_list, ["enabled", "selling"], as_dict=True)
	if not pl or not pl.enabled or not pl.selling:
		raise APIError(
			"PRICE_LIST_INVALID",
			_("Price list {0} is missing, disabled or not a selling price list").format(price_list),
		)
	return price_list


def _get_tax_template(company):
	"""
	Templates the user can see (permission-aware), active, same company:
	one -> use it; several -> the default one; otherwise error.
	"""
	templates = frappe.get_list(
		TAX_TEMPLATE_DOCTYPE,
		filters={"company": company, "disabled": 0},
		fields=["name", "is_default"],
		order_by="name asc",
	)
	if not templates:
		raise APIError(
			"TAX_TEMPLATE_NOT_FOUND",
			_("No active Sales Taxes and Charges Template is available to you for company {0}").format(company),
		)
	if len(templates) == 1:
		return templates[0].name
	defaults = [t.name for t in templates if t.is_default]
	if len(defaults) == 1:
		return defaults[0]
	raise APIError(
		"TAX_TEMPLATE_AMBIGUOUS",
		_("Several tax templates are available to you and none (or more than one) is marked as default"),
		417,
		[t.name for t in templates],
	)


def _validate_items(rows):
	"""Item must exist, be enabled, sellable, not a template; UOM must belong to the item."""
	codes = list({r.item_code for r in rows})
	items = {
		i.name: i
		for i in frappe.get_all(
			"Item",
			filters={"name": ["in", codes]},
			fields=["name", "disabled", "is_sales_item", "has_variants", "stock_uom"],
		)
	}
	item_uoms = defaultdict(set)
	for d in frappe.get_all(
		"UOM Conversion Detail",
		filters={"parenttype": "Item", "parent": ["in", codes]},
		fields=["parent", "uom"],
	):
		item_uoms[d.parent].add(d.uom)

	errors = []
	for idx, r in enumerate(rows, 1):
		item = items.get(r.item_code)
		if not item:
			errors.append(f"Row {idx}: item {r.item_code} not found")
			continue
		if item.disabled:
			errors.append(f"Row {idx}: item {r.item_code} is disabled")
		if not item.is_sales_item:
			errors.append(f"Row {idx}: item {r.item_code} is not a sales item")
		if item.has_variants:
			errors.append(f"Row {idx}: item {r.item_code} is a template, choose a variant")
		r.uom = r.uom or item.stock_uom
		if r.uom != item.stock_uom and r.uom not in item_uoms[item.name]:
			errors.append(f"Row {idx}: UOM {r.uom} is not set up for item {r.item_code}")
	if errors:
		raise APIError("INVALID_ITEMS", _("Some items are not valid"), 417, errors)
	return items


def _validate_payments(payments, company):
	errors = []
	for p in payments:
		mop = frappe.db.get_value("Mode of Payment", p.mode_of_payment, ["name", "enabled"], as_dict=True)
		if not mop:
			errors.append(f"Mode of payment {p.mode_of_payment} not found")
		elif not mop.enabled:
			errors.append(f"Mode of payment {p.mode_of_payment} is disabled")
		elif not frappe.db.get_value(
			"Mode of Payment Account",
			{"parenttype": "Mode of Payment", "parent": p.mode_of_payment, "company": company},
			"default_account",
		):
			errors.append(f"Mode of payment {p.mode_of_payment} has no default account for company {company}")
	if errors:
		raise APIError("INVALID_PAYMENTS", _("Some payments are not valid"), 417, errors)


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #


def _build_invoice(req, ctx, customer):
	"""Normal invoice, or return without an original invoice (unlinked)."""
	_validate_items(req.lines)
	_validate_payments(req.payments, ctx.company)
	price_list = _get_price_list(customer)
	tax_template = _get_tax_template(ctx.company)
	sign = -1 if req.is_return else 1

	doc = frappe.new_doc("Sales Invoice")
	doc.flags.ignore_pos_profile = True  # a POS Profile must not override our price list / taxes / payments
	doc.update(
		{
			"customer": req.customer,
			"company": ctx.company,
			"posting_date": req.posting_date,
			"posting_time": req.posting_time,
			"set_posting_time": 1,
			"is_return": 1 if req.is_return else 0,
			"update_stock": 1,
			"set_warehouse": ctx.warehouse,
			"selling_price_list": price_list,
			"ignore_pricing_rule": 1,  # no discounts: rate = price list rate
			"disable_rounded_total": 1,
			"is_pos": 1 if req.payments else 0,
		}
	)
	for r in req.lines:
		doc.append(
			"items",
			{"item_code": r.item_code, "qty": sign * r.qty, "uom": r.uom, "warehouse": ctx.warehouse},
		)
	for p in req.payments:
		doc.append("payments", {"mode_of_payment": p.mode_of_payment, "amount": sign * p.amount})

	if req.is_return:
		doc.custom_return_reason = _("Return reason: {0}").format(req.return_reason)

	# Fetch item details, price list rates, accounts, currency, due date ...
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

	_check_payments_total(doc)
	return doc


def _build_linked_return(req, ctx):
	"""Full or partial return of an original invoice, like ERPNext's Return button: no items sent ->
	everything still returnable; items sent -> only those items / qty. Several returns are allowed."""
	# Locking read: concurrent returns of the same invoice wait for each other (see _returnable_invoice_rows)
	rows = frappe.db.sql(
		"""
		select name, docstatus, is_return, customer, company, posting_date, posting_time, update_stock
		from `tabSales Invoice` where name = %s for update
		""",
		req.return_against,
		as_dict=True,
	)
	if not rows:
		raise APIError("ORIGINAL_NOT_FOUND", _("Invoice {0} not found").format(req.return_against), 404)
	orig = rows[0]
	if not frappe.has_permission("Sales Invoice", "read", doc=orig.name):
		raise APIError("NOT_PERMITTED", _("You are not allowed to access invoice {0}").format(orig.name), 403)
	if orig.is_return:
		raise APIError("ORIGINAL_IS_RETURN", _("Invoice {0} is itself a return").format(orig.name))
	if orig.docstatus == 0:
		raise APIError("ORIGINAL_NOT_SUBMITTED", _("Invoice {0} is not submitted yet").format(orig.name))
	if orig.docstatus == 2:
		raise APIError("ORIGINAL_CANCELLED", _("Invoice {0} is cancelled").format(orig.name))
	if orig.customer != req.customer:
		raise APIError(
			"CUSTOMER_MISMATCH",
			_("Customer {0} does not match invoice {1} (customer {2})").format(req.customer, orig.name, orig.customer),
		)
	if orig.company != ctx.company:
		raise APIError("COMPANY_MISMATCH", _("Invoice {0} belongs to another company").format(orig.name))

	orig_dt = get_datetime(f"{orig.posting_date} {orig.posting_time or '00:00:00'}")
	if req.posting_dt < orig_dt:
		raise APIError(
			"RETURN_BEFORE_ORIGINAL",
			_("Return date/time must be on or after the invoice date/time {0}").format(orig_dt),
		)

	invoice_rows = _returnable_invoice_rows(orig.name)
	picked = _pick_return_rows(req.lines, invoice_rows, "invoice")
	if orig.update_stock:
		other = sorted(
			{
				r.warehouse
				for r in invoice_rows
				if r.name in picked and r.warehouse and r.warehouse != ctx.warehouse
			}
		)
		if other:
			raise APIError(
				"WAREHOUSE_MISMATCH",
				_("Invoice {0} was sold from a different warehouse than yours").format(orig.name),
				417,
				other,
			)

	_validate_payments(req.payments, ctx.company)

	# ERPNext's own mapper: copies items (negative qty), rates, taxes, warehouse, line links.
	# Then keep only the picked rows with the picked qty.
	doc = make_sales_return(orig.name)
	doc.flags.ignore_pos_profile = True
	doc.set("items", [d for d in doc.items if picked.get(d.sales_invoice_item)])
	for d in doc.items:
		d.qty = -1 * picked[d.sales_invoice_item]
		d.stock_qty = flt(d.qty) * flt(d.conversion_factor or 1)
	doc.update(
		{
			"posting_date": req.posting_date,
			"posting_time": req.posting_time,
			"set_posting_time": 1,
			"disable_rounded_total": 1,
			"remarks": _("Return reason: {0}").format(req.return_reason),
			"is_pos": 1 if req.payments else 0,
		}
	)
	doc.set("payments", [])
	for p in req.payments:
		doc.append("payments", {"mode_of_payment": p.mode_of_payment, "amount": -1 * p.amount})

	doc.calculate_taxes_and_totals()
	_check_payments_total(doc)
	return doc


def _pick_rows(lines, rows, error_message, available_key, label):
	"""Spread the app's (item_code, uom) quantities over the original document's rows in row order.
	rows: name, item_code, uom, pending_qty, returned_qty and optionally billed_qty / draft_billed_qty.
	available_key names the pending qty in the error rows ("pending_qty" / "returnable_qty").
	Returns {row name: qty}."""
	stock_uoms = dict(
		frappe.get_all(
			"Item",
			filters={"name": ["in", list({r.item_code for r in lines})]},
			fields=["name", "stock_uom"],
			as_list=True,
		)
	)
	wanted = defaultdict(float)
	for r in lines:
		wanted[(r.item_code, r.uom or stock_uoms.get(r.item_code))] += flt(r.qty)

	by_key = defaultdict(list)
	for r in rows:
		by_key[(r.item_code, r.uom)].append(r)

	picked, errors = {}, []
	for (code, uom), qty in wanted.items():
		candidates = by_key.get((code, uom))
		if not candidates:
			errors.append({"item_code": code, "uom": uom, "problem": f"not in {label}", "sent_qty": qty})
			continue
		pending = flt(sum(r.pending_qty for r in candidates), 6)
		if qty - pending > 1e-6:
			error = {
				"item_code": code,
				"uom": uom,
				"problem": "more than pending",
				"sent_qty": qty,
				available_key: pending,
				"returned_qty": flt(sum(r.returned_qty for r in candidates), 6),
			}
			if "billed_qty" in candidates[0]:
				error["billed_qty"] = flt(sum(r.billed_qty + r.draft_billed_qty for r in candidates), 6)
			errors.append(error)
			continue
		left = qty
		for r in candidates:
			take = min(r.pending_qty, left)
			if take > 0:
				picked[r.name] = take
				left = flt(left - take, 6)
	if errors:
		raise APIError("INVALID_ITEMS", error_message, 417, errors)
	return picked


def _pick_return_rows(lines, rows, label):
	"""Linked return: the picked items / qty, or (no items sent) everything still returnable."""
	if not lines:
		picked = {r.name: r.pending_qty for r in rows if r.pending_qty > 0}
		if not picked:
			raise APIError(
				"NOTHING_TO_RETURN",
				_("Nothing left to return on this {0}").format(_(label)),
				417,
				[
					{
						"item_code": r.item_code,
						"uom": r.uom,
						"qty": flt(r.qty),
						"returned_qty": r.returned_qty,
						**({"billed_qty": flt(r.billed_qty + r.draft_billed_qty, 6)} if "billed_qty" in r else {}),
					}
					for r in rows
				],
			)
		return picked
	return _pick_rows(
		lines, rows, _("Some items cannot be returned from this {0}").format(_(label)), "returnable_qty", label
	)


def _returnable_invoice_rows(invoice_name):
	"""Per invoice row: qty, returned (non-cancelled returns, drafts included) and
	pending = qty - returned. Locking reads: see delivery_note._pending_rows."""
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parenttype": "Sales Invoice", "parent": invoice_name},
		fields=["name", "idx", "item_code", "item_name", "qty", "uom", "warehouse"],
		order_by="idx asc",
	)
	returned = dict(
		frappe.db.sql(
			"""
			select sii.sales_invoice_item, sum(abs(sii.qty))
			from `tabSales Invoice Item` sii
			inner join `tabSales Invoice` si on si.name = sii.parent
			where si.return_against = %s and si.is_return = 1 and si.docstatus < 2
			group by sii.sales_invoice_item
			for update
			""",
			invoice_name,
		)
	)
	for r in rows:
		r.returned_qty = flt(returned.get(r.name))
		r.pending_qty = max(flt(r.qty - r.returned_qty, 6), 0)
	return rows


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def _check_stock(doc, warehouse):
	"""
	available = Bin.actual_qty - qty on DRAFT sales invoices (update_stock) and DRAFT delivery notes
	(same warehouse, not returns). Submitted documents are already inside Bin.actual_qty, so they are
	not subtracted again.
	Locking reads (FOR UPDATE) make concurrent requests for the same items wait for each other
	and read the latest committed data.
	"""
	needed = defaultdict(float)
	for row in doc.items:
		if frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
			needed[row.item_code] += flt(row.qty) * flt(row.conversion_factor or 1)
	if not needed:
		return

	codes = tuple(needed)
	actual = dict(
		frappe.db.sql(
			"""
			select item_code, actual_qty
			from `tabBin`
			where warehouse = %s and item_code in %s
			for update
			""",
			(warehouse, codes),
		)
	)
	in_drafts = dict(
		frappe.db.sql(
			"""
			select sii.item_code, sum(sii.qty * ifnull(sii.conversion_factor, 1))
			from `tabSales Invoice Item` sii
			inner join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 0
				and si.update_stock = 1
				and si.is_return = 0
				and sii.warehouse = %s
				and sii.item_code in %s
			group by sii.item_code
			for update
			""",
			(warehouse, codes),
		)
	)
	in_draft_notes = dict(
		frappe.db.sql(
			"""
			select dni.item_code, sum(dni.qty * ifnull(dni.conversion_factor, 1))
			from `tabDelivery Note Item` dni
			inner join `tabDelivery Note` dn on dn.name = dni.parent
			where dn.docstatus = 0
				and dn.is_return = 0
				and dni.warehouse = %s
				and dni.item_code in %s
			group by dni.item_code
			for update
			""",
			(warehouse, codes),
		)
	)

	errors = []
	for code, qty in needed.items():
		available = flt(actual.get(code)) - flt(in_drafts.get(code)) - flt(in_draft_notes.get(code))
		if qty > available + 1e-9:
			errors.append(
				{"item_code": code, "requested_qty": flt(qty, 6), "available_qty": flt(max(available, 0), 6)}
			)
	if errors:
		raise APIError(
			"INSUFFICIENT_STOCK",
			_("Not enough stock in warehouse {0}").format(warehouse),
			417,
			errors,
		)


def _check_payments_total(doc):
	paid = sum(abs(flt(p.amount)) for p in doc.get("payments") or [])
	total = abs(flt(doc.grand_total))
	if paid - total > TOTAL_TOLERANCE:
		raise APIError(
			"PAYMENT_EXCEEDS_TOTAL",
			_("Payments ({0}) are more than the invoice total ({1})").format(paid, total),
		)


def _check_totals(doc, req):
	calculated = abs(flt(doc.net_total))
	if abs(calculated - req.net_total) > TOTAL_TOLERANCE:
		raise APIError(
			"TOTAL_MISMATCH",
			_("Net total sent by the app does not match the calculated net total"),
			417,
			[{"field": "net_total", "sent": req.net_total, "calculated": calculated}],
		)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #


def _serialize(doc):
	return {
		"invoice_id": doc.name,
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
		"paid_amount": flt(doc.paid_amount),
		"outstanding_amount": flt(doc.outstanding_amount),
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
		"payments": [{"mode_of_payment": p.mode_of_payment, "amount": flt(p.amount)} for p in doc.payments],
	}


def _serialize_details(doc):
	customer = frappe.db.get_value(
		"Customer", doc.customer, ["tax_id", "mobile_no", "email_id"], as_dict=True
	) or frappe._dict()
	returns = frappe.get_all(
		"Sales Invoice",
		filters={"return_against": doc.name, "is_return": 1, "docstatus": ["<", 2]},
		fields=["name as invoice_id", "status", "docstatus", "posting_date", "grand_total"],
		order_by="posting_date asc, creation asc",
	)
	for r in returns:
		r.posting_date = str(r.posting_date)
		r.grand_total = flt(r.grand_total)

	return {
		"invoice_id": doc.name,
		"status": doc.status,
		"docstatus": doc.docstatus,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"return_reason": doc.get("custom_return_reason") or (doc.remarks if doc.is_return else None),
		"returns": returns,
		"posting_date": str(doc.posting_date),
		"posting_time": str(doc.posting_time),
		"due_date": str(doc.due_date) if doc.due_date else None,
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
		"paid_amount": flt(doc.paid_amount),
		"change_amount": flt(doc.change_amount),
		"outstanding_amount": flt(doc.outstanding_amount),
		"in_words": doc.in_words,
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"qty": flt(d.qty),
				"uom": d.uom,
				"stock_qty": flt(d.stock_qty),
				"stock_uom": d.stock_uom,
				"price_list_rate": flt(d.price_list_rate),
				"discount_amount": flt(d.discount_amount),
				"rate": flt(d.rate),
				"amount": flt(d.amount),
				"net_amount": flt(d.net_amount),
				"warehouse": d.warehouse,
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
		"payments": [{"mode_of_payment": p.mode_of_payment, "amount": flt(p.amount)} for p in doc.payments],
		"created_by": doc.owner,
		"creation": str(doc.creation),
		"modified": str(doc.modified),
	}


def _serialize_totals(doc):
	return {
		"customer": doc.customer,
		"is_return": bool(doc.is_return),
		"return_against": doc.return_against,
		"currency": doc.currency,
		"taxes_and_charges": doc.taxes_and_charges,
		"net_total": abs(flt(doc.net_total)),
		"taxes": [
			{"description": t.description, "rate": flt(t.rate), "amount": abs(flt(t.tax_amount))}
			for t in doc.taxes
		],
		"total_taxes_and_charges": abs(flt(doc.total_taxes_and_charges)),
		"grand_total": abs(flt(doc.grand_total)),
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"qty": abs(flt(d.qty)),
				"uom": d.uom,
				"rate": flt(d.rate),
				"amount": abs(flt(d.amount)),
			}
			for d in doc.items
		],
	}


def _ok(doc):
	frappe.clear_messages()
	return {"success": True, "data": _serialize(doc)}


def _fail(http_status, code, message, errors=None):
	frappe.db.rollback()
	frappe.clear_messages()
	return error(http_status, message, error_code=code, errors=errors or [])


def _clean(exc):
	return strip_html(str(exc) or "").strip()