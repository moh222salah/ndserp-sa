import re

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display

from ndserp.api.sales_invoice import APIError, _handle
from ndserp.api.utils import error, parse_paging

# Saudi VAT registration number: 15 digits, first and last digit 3 (ZATCA)
VAT_PATTERN = re.compile(r"^3\d{13}3$")
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")
# Customer group by type; used only when the group exists on the site
CUSTOMER_GROUPS = {"Company": "Commercial", "Individual": "Individual"}


ADDRESS_FIELDS = ["name", "address_line1", "address_line2", "city", "state", "pincode", "country", "phone"]


@frappe.whitelist(methods=["GET"])
def get_customers(search=None, page=1, page_size=50):
	page, page_size, paging_error = parse_paging(page, page_size)
	if paging_error:
		return error(417, "Invalid request", error_code="INVALID_REQUEST", errors=[paging_error])
	filters = {"disabled": 0}
	or_filters = None
	if search and search.strip():
		like = f"%{search.strip()}%"
		or_filters = {
			"name": ["like", like],
			"customer_name": ["like", like],
			"tax_id": ["like", like],
			"mobile_no": ["like", like],
		}

	data = frappe.get_list(
		"Customer",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name as customer_id",
			"customer_name",
			"tax_id as vat_no",
			"mobile_no as phone",
			"customer_primary_address",
		],
		order_by="customer_name asc",
		start=(page - 1) * page_size,
		page_length=page_size,
	)

	# One query for all primary addresses on this page instead of one per customer
	address_names = list({d.customer_primary_address for d in data if d.customer_primary_address})
	addresses = {}
	if address_names:
		addresses = {
			a.name: a
			for a in frappe.get_all("Address", filters={"name": ["in", address_names]}, fields=ADDRESS_FIELDS)
		}

	for d in data:
		addr = addresses.get(d.pop("customer_primary_address"))
		# Fall back to the address phone when the customer has no primary contact mobile
		if not d.phone and addr:
			d.phone = addr.phone
		d.phone = d.phone or None
		d.address = (
			{
				"address_line1": addr.address_line1,
				"address_line2": addr.address_line2,
				"city": addr.city,
				"state": addr.state,
				"pincode": addr.pincode,
				"country": addr.country,
			}
			if addr
			else None
		)

	# Same filters and user permissions as the page itself, so total matches what can be paged through
	total = frappe.get_list(
		"Customer", filters=filters, or_filters=or_filters, fields=[{"COUNT": "*", "as": "total"}]
	)[0].total
	return {"page": page, "page_size": page_size, "total": total, "data": data}


@frappe.whitelist(methods=["POST"])
def create_customer(**kwargs):
	"""
	Body: customer_name, mobile_no, optional vat_no,
	address{street, city, building_number, district, postal_code, optional address_line2}.
	With a VAT number the customer is B2B for ZATCA: building_number (4 digits), district and
	postal_code (5 digits) are then required, otherwise the customer's invoices cannot be submitted.
	Creates the Customer, its primary Contact (mobile) and primary Address in one transaction.
	"""

	def run():
		req = _parse_customer_request(kwargs)
		for doctype in ("Customer", "Address", "Contact"):
			if not frappe.has_permission(doctype, "create"):
				raise APIError("NOT_PERMITTED", _("You are not allowed to create {0}").format(_(doctype)), 403)

		if req.vat_no:
			vat_fields = ["tax_id"] + (["custom_vat_registration_number"] if _has_zatca_vat_field() else [])
			existing = frappe.get_all(
				"Customer", or_filters={f: req.vat_no for f in vat_fields}, pluck="name", limit=1
			)
			if existing:
				raise APIError(
					"CUSTOMER_EXISTS",
					_("A customer with VAT number {0} already exists").format(req.vat_no),
					409,
					existing,
				)

		customer_type = "Company" if req.vat_no else "Individual"
		customer = frappe.new_doc("Customer")
		customer.update(
			{
				"customer_name": req.customer_name,
				"customer_type": customer_type,
				"customer_group": _existing("Customer Group", CUSTOMER_GROUPS[customer_type]),
				"territory": _existing("Territory", req.address.city),
				"tax_id": req.vat_no,
				"mobile_no": req.mobile_no,  # ERPNext creates the primary Contact from it
			}
		)
		if req.vat_no and _has_zatca_vat_field():
			customer.custom_vat_registration_number = req.vat_no  # what ZATCA reads as the buyer VAT
		customer.insert()

		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": customer.customer_name,
				"address_type": "Billing",
				"address_line1": req.address.street,
				"address_line2": req.address.address_line2,
				"city": req.address.city,
				"pincode": req.address.postal_code,
				"country": "Saudi Arabia",
				"phone": req.mobile_no,
				"is_primary_address": 1,
				"is_shipping_address": 1,
				"links": [{"link_doctype": "Customer", "link_name": customer.name}],
			}
		)
		if address.meta.has_field("custom_building_number"):
			address.custom_building_number = req.address.building_number
		if address.meta.has_field("custom_area"):
			address.custom_area = req.address.district  # ZATCA "district"
		address.insert()

		customer.db_set(
			{"customer_primary_address": address.name, "primary_address": get_address_display(address.name)}
		)

		frappe.clear_messages()  # e.g. "Changed customer name to ... - 1"
		return {"success": True, "data": _serialize_customer(customer.name)}

	return _handle(run)


def _parse_customer_request(kw):
	data = frappe._dict(kw)
	errors = []

	def text(source, field, label=None, required=False):
		value = source.get(field)
		value = value.strip() if isinstance(value, str) else None if value is None else str(value).strip()
		if required and not value:
			errors.append(f"{label or field} is required")
		return value or None

	req = frappe._dict()
	req.customer_name = text(data, "customer_name", required=True)

	mobile = text(data, "mobile_no", required=True)
	req.mobile_no = re.sub(r"[\s-]", "", mobile) if mobile else None
	if req.mobile_no and not PHONE_PATTERN.match(req.mobile_no):
		errors.append("mobile_no must be 9 to 15 digits, optionally starting with +")

	req.vat_no = text(data, "vat_no")
	if req.vat_no and not VAT_PATTERN.match(req.vat_no):
		errors.append("vat_no must be 15 digits, starting and ending with 3")

	address = data.get("address")
	if isinstance(address, str):
		try:
			address = frappe.parse_json(address)
		except Exception:
			address = None
	if not isinstance(address, dict):
		errors.append("address is required and must be an object")
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)

	b2b = bool(req.vat_no)
	req.address = frappe._dict(
		street=text(address, "street", "address.street", required=True),
		city=text(address, "city", "address.city", required=True),
		address_line2=text(address, "address_line2"),
		building_number=text(address, "building_number", "address.building_number (required with vat_no)", required=b2b),
		district=text(address, "district", "address.district (required with vat_no)", required=b2b),
		postal_code=text(address, "postal_code", "address.postal_code (required with vat_no)", required=b2b),
	)
	if req.address.building_number and not re.fullmatch(r"\d{4}", req.address.building_number):
		errors.append("address.building_number must be exactly 4 digits")
	if req.address.postal_code and not re.fullmatch(r"\d{5}", req.address.postal_code):
		errors.append("address.postal_code must be exactly 5 digits")

	if errors:
		raise APIError("INVALID_REQUEST", _("Invalid request"), 417, errors)
	return req


def _has_zatca_vat_field():
	return frappe.get_meta("Customer").has_field("custom_vat_registration_number")


def _existing(doctype, name):
	return name if name and frappe.db.exists(doctype, name) else None


def _serialize_customer(name):
	c = frappe.db.get_value(
		"Customer",
		name,
		[
			"name",
			"customer_name",
			"customer_type",
			"customer_group",
			"territory",
			"tax_id",
			"mobile_no",
			"customer_primary_contact",
			"customer_primary_address",
		],
		as_dict=True,
	)
	a = frappe.db.get_value("Address", c.customer_primary_address, "*", as_dict=True) or frappe._dict()
	return {
		"customer_id": c.name,
		"customer_name": c.customer_name,
		"customer_type": c.customer_type,
		"customer_group": c.customer_group,
		"territory": c.territory,
		"vat_no": c.tax_id,
		"mobile_no": c.mobile_no,
		"contact_id": c.customer_primary_contact,
		"address_id": c.customer_primary_address,
		"address": {
			"street": a.address_line1,
			"address_line2": a.address_line2,
			"building_number": a.get("custom_building_number"),
			"district": a.get("custom_area"),
			"city": a.city,
			"postal_code": a.pincode,
			"country": a.country,
		},
	}
