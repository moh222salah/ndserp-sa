# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, now_datetime
import json



@frappe.whitelist()
def get_pos_context(pos_profile=None):
	"""Return restaurant, menu, tables, and opening status for the current user."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	profile = pos_profile or _default_pos_profile(user)
	if not profile:
		frappe.throw(_("No POS Profile assigned to you"))

	# Check POS Settings Invoice Type (ERPNext v16+)
	invoice_type = frappe.db.get_single_value("POS Settings", "invoice_type")
	if invoice_type == "Sales Invoice":
		frappe.msgprint(
			_(
				"POS Settings Invoice Type is set to 'Sales Invoice'. "
				"Please change it to 'POS Invoice' in POS Settings to use this POS. "
				"Go to: Setup > Point of Sale > POS Settings"
			),
			title=_("POS Configuration Required"),
			indicator="red",
		)
		frappe.throw(_("POS Settings must use 'POS Invoice' mode"))

	profile_doc = frappe.get_doc("POS Profile", profile)
	restaurant = profile_doc.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("POS Profile {0} has no Restaurant linked").format(profile))

	rest = frappe.get_doc("NDS Restaurant", restaurant)
	_assert_branch_access(user, rest.branch)

	opening = frappe.db.get_value(
		"POS Opening Entry",
		{"user": user, "pos_profile": profile, "status": "Open", "docstatus": 1},
		["name", "period_start_date"],
		as_dict=True,
	)

	menu_name = rest.active_menu
	if menu_name:
		menu_enabled = _menu_if_enabled(menu_name)
		if menu_enabled is None:
			frappe.throw(_("Menu {0} is disabled").format(menu_name))
		menu_name = menu_enabled
	
	menu_items = []
	courses = []
	price_list = profile_doc.selling_price_list
	if menu_name and frappe.db.exists("NDS Menu", menu_name):
		menu = frappe.get_doc("NDS Menu", menu_name)
		price_list = menu.price_list or price_list
		menu_items = _build_menu_items(menu, profile_doc.warehouse, price_list)
		courses = frappe.get_all(
			"NDS Menu Course",
			fields=["name", "course", "serving_priority", "indicate_in_kds"],
			order_by="serving_priority asc",
		)

	tables = frappe.get_all(
		"NDS Table",
		filters={"restaurant": restaurant, "is_take_away": 0},
		fields=[
			"name",
			"no_of_seats",
			"table_shape",
			"restaurant_room",
			"occupied",
			"layout_x",
			"layout_y",
			"layout_width",
			"layout_height",
			"current_invoice",
			"latest_invoice_time",
		],
	)
	rooms = frappe.get_all(
		"NDS Room",
		filters={"branch": rest.branch},
		fields=["name", "room_type"],
	)

	# Room restriction for multi-cashier
	allowed_rooms = _user_rooms(user, rest.branch)
	if allowed_rooms:
		tables = [t for t in tables if t.restaurant_room in allowed_rooms]
		rooms = [r for r in rooms if r.name in allowed_rooms]

	payments = [
		{"mode_of_payment": p.mode_of_payment, "default": p.default}
		for p in profile_doc.payments
	]

	paid_limit = profile_doc.get("custom_paid_limit")
	if paid_limit is None:
		paid_limit = 50
		
	view_all = profile_doc.get("custom_view_all_status")
	
	tabs = ["Draft", "Unbilled"]
	if paid_limit > 0:
		tabs.append("Recently Paid")
	if view_all:
		tabs.extend(["Paid", "Consolidated", "Return"])

	return {
		"pos_profile": profile,
		"company": profile_doc.company,
		"warehouse": profile_doc.warehouse,
		"cost_center": profile_doc.cost_center,
		"currency": frappe.db.get_value("Company", profile_doc.company, "default_currency"),
		"restaurant": rest.as_dict(),
		"menu": menu_name,
		"price_list": price_list,
		"menu_items": menu_items,
		"courses": courses,
		"tables": tables,
		"rooms": rooms,
		"payments": payments,
		"opening": opening,
		"settings": {
			"tabs": tabs,
			"show_item_image": profile_doc.get("custom_show_item_image"),
			"enable_discount": profile_doc.get("custom_enable_discount"),
			"view_all_status": view_all,
			"paid_limit": paid_limit,
			"low_stock_threshold": profile_doc.get("custom_low_stock_threshold")
			if profile_doc.meta.has_field("custom_low_stock_threshold")
			else 5,
			"qz_print": profile_doc.get("custom_qz_print"),
			"qz_host": profile_doc.get("custom_qz_host"),
			"kot_naming_series": profile_doc.get("custom_kot_naming_series") or "KOT-.#####",
			"multiple_cashier": profile_doc.get("custom_enable_multiple_cashier"),
			"print_format": profile_doc.get("print_format") or "NDS Receipt",
			"auto_print": 1 if profile_doc.get("custom_nds_auto_print_receipt") is None else flt(profile_doc.get("custom_nds_auto_print_receipt")),
		},
	}

def _resolve_menu(restaurant, room=None, order_type=None):
	if order_type:
		ot_menu = frappe.db.get_value("NDS Order Type Menu", 
			{"parent": restaurant, "order_type": order_type}, "menu")
		if ot_menu: return _menu_if_enabled(ot_menu)
		
	if room:
		room_menu = frappe.db.get_value("NDS Menu For Room", 
			{"parent": restaurant, "room": room}, "menu")
		if room_menu: return _menu_if_enabled(room_menu)
		
	active_menu = frappe.db.get_value("NDS Restaurant", restaurant, "active_menu")
	return _menu_if_enabled(active_menu)


@frappe.whitelist()
def get_menu(pos_profile, room=None, order_type=None):
	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	restaurant = profile_doc.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("No restaurant linked to this POS Profile"))

	menu_name = _resolve_menu(restaurant, room, order_type)
	if not menu_name:
		return {"menu": None, "price_list": profile_doc.selling_price_list, "items": []}

	menu_doc = frappe.get_doc("NDS Menu", menu_name)
	price_list = menu_doc.price_list or profile_doc.selling_price_list


	menu_items = _build_menu_items(menu_doc, profile_doc.warehouse, price_list)

	return {"menu": menu_name, "price_list": price_list, "items": menu_items}

@frappe.whitelist()
def create_or_update_order(
	pos_profile,
	items,
	customer=None,
	table=None,
	order_type="Dine In",
	invoice=None,
	comments=None,
	generate_kot=1,
	expected_modified=None,
):
	"""Create or update a draft POS Invoice and optionally generate KOTs."""
	import json

	if isinstance(items, str):
		items = json.loads(items)
	generate_kot = int(generate_kot or 0)

	table = _coalesce_table(table)
	order_type = _coalesce_order_type(order_type)

	profile = frappe.get_doc("POS Profile", pos_profile)
	_assert_opening(frappe.session.user, pos_profile)
	
	# Get restaurant for settings
	restaurant = profile.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("POS Profile {0} has no Restaurant linked").format(pos_profile))
	
	rest = frappe.get_doc("NDS Restaurant", restaurant)
	
	# Check menu is enabled (only if menu is set)
	menu_name = rest.active_menu
	if menu_name:
		menu_enabled = _menu_if_enabled(menu_name)
		if menu_enabled is None:
			frappe.throw(_("Menu {0} is disabled").format(menu_name))

	if not customer:
		customer = profile.get("customer")
	if not customer:
		customer = _default_customer()

	previous_table = None
	if invoice and frappe.db.exists("POS Invoice", invoice):
		doc = frappe.get_doc("POS Invoice", invoice)
		if doc.docstatus != 0:
			frappe.throw(_("Cannot edit submitted invoice"))

		if expected_modified and str(doc.modified) != str(expected_modified):
			frappe.throw(_("Order changed on another device, please reload"))
		previous_table = _invoice_table_name(doc)
		doc.set("items", [])
	else:
		doc = frappe.new_doc("POS Invoice")
		doc.pos_profile = pos_profile
		doc.company = profile.company
		doc.customer = customer
		doc.is_pos = 1
		doc.update_stock = 1
		doc.set_warehouse = profile.warehouse
		doc.selling_price_list = profile.selling_price_list
		doc.taxes_and_charges = profile.taxes_and_charges

	doc.customer = customer
	doc.custom_nds_order_type = order_type
	doc.custom_order_comments = comments

	if order_type == "Take Away":
		doc.custom_nds_table = None
		if doc.meta.has_field("restaurant_table"):
			doc.restaurant_table = None
		doc.custom_nds_room = None
	else:
		if table:
			_assert_table_available_for_order(table, invoice=invoice or doc.name)
			doc.custom_nds_table = table
			if doc.meta.has_field("restaurant_table"):
				doc.restaurant_table = table
			room = frappe.db.get_value("NDS Table", table, "restaurant_room")
			doc.custom_nds_room = room
		else:
			doc.custom_nds_table = None
			if doc.meta.has_field("restaurant_table"):
				doc.restaurant_table = None
			doc.custom_nds_room = None

  
	room = doc.get("custom_nds_room")
	resolved_menu = _resolve_menu(restaurant, room, order_type)
	
	menu_rates = {}
	if resolved_menu:
		menu_doc = frappe.get_doc("NDS Menu", resolved_menu)
		doc.selling_price_list = menu_doc.price_list or profile.selling_price_list
	
		for m_item in menu_doc.items:
			if not m_item.disabled:
				menu_rates[m_item.item] = m_item.rate


	item_meta = frappe.get_meta("POS Invoice Item")
	for row in items:
		item_code = row.get("item_code") or row.get("item")
		qty = flt(row.get("qty") or 1)
		
		
		if item_code in menu_rates:
			server_rate = flt(menu_rates[item_code])
		else:
			server_rate = flt(frappe.db.get_value("Item Price", 
				{"item_code": item_code, "price_list": doc.selling_price_list}, 
				"price_list_rate") or 0.0)


		item_dict = {
			"item_code": item_code,
			"qty": qty,
			"rate": server_rate,  
			"warehouse": profile.warehouse,
		}

		if item_meta.has_field("custom_nds_notes") and row.get("notes"):
			item_dict["custom_nds_notes"] = row.get("notes")
		if item_meta.has_field("custom_is_addon") and row.get("is_addon"):
			item_dict["custom_is_addon"] = 1
		if item_meta.has_field("custom_addon_group_id") and row.get("addon_group_id"):
			item_dict["custom_addon_group_id"] = row.get("addon_group_id")
		if item_meta.has_field("custom_nds_course") and row.get("course"):
			item_dict["custom_nds_course"] = row.get("course")

		doc.append("items", item_dict)

	# Set missing values (calculates totals, taxes, payments, etc.)
	doc.set_missing_values()
	_sanitize_invoice_totals(doc)
	
	# Apply restaurant's default tax template for new docs only
	# This must happen AFTER set_missing_values() to override POS Profile's template
	if not invoice and rest.get('default_tax_template'):
		template = rest.default_tax_template
		# Only apply if different from current and belongs to same company
		if (template != doc.taxes_and_charges and 
			frappe.db.get_value("Sales Taxes and Charges Template", template, "company") == doc.company):
			doc.taxes_and_charges = template
			doc.set("taxes", [])
			doc.set_taxes()
	
	# P3-T7: Server-side stock validation before saving
	if invoice:
		old_doc = frappe.get_doc("POS Invoice", invoice)
		prev_qty = {}
		for old_item in old_doc.items:
			key = old_item.item_code
			prev_qty[key] = prev_qty.get(key, 0) + flt(old_item.qty)
	else:
		prev_qty = {}

	from nds_restaurant.api.recipe import get_item_availability
	for item_row in doc.items:
		item_code = item_row.item_code
		new_qty = sum(flt(ir.qty) for ir in doc.items if ir.item_code == item_code)
		old_qty = prev_qty.get(item_code, 0)
		extra_qty = new_qty - old_qty

		if extra_qty > 0:
			if frappe.db.exists("NDS Recipe", {"item": item_code, "enabled": 1}):
				availability = get_item_availability(item_code, profile.warehouse)
				if availability is not None and new_qty > availability:
					frappe.throw(
						_("Only {0} portions of {1} available").format(
							int(availability), frappe.bold(item_code)
						)
					)
			elif frappe.db.get_value("Item", item_code, "is_stock_item"):
				actual_qty = flt(
					frappe.db.get_value(
						"Bin",
						{"item_code": item_code, "warehouse": profile.warehouse},
						"actual_qty",
					) or 0
				)
				if new_qty > actual_qty:
					frappe.throw(
						_("Only {0} portions of {1} available").format(
							int(actual_qty), frappe.bold(item_code)
						)
					)

	if frappe.get_meta("POS Invoice").has_field("custom_invoice_printed"):
		doc.custom_invoice_printed = 0
	doc.flags.ignore_permissions = True
	doc.save()

	_sync_nds_table_after_order_save(
		order_type=order_type,
		table=table,
		previous_table=previous_table,
		invoice_name=doc.name,
	)

	if generate_kot:
		from nds_restaurant.api.kot import kot_execute

		kot_execute(doc.name)

	return {"invoice": doc.name, "grand_total": doc.grand_total, "status": doc.status}



@frappe.whitelist()
def submit_payment(invoice, payments, discount_percentage=None, discount_amount=None):
	if isinstance(payments, str):
		payments = json.loads(payments)

	doc = frappe.get_doc("POS Invoice", invoice)

	
	pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
	enable_discount = getattr(pos_profile, "custom_enable_discount", 0)

	disc_pct = flt(discount_percentage) if discount_percentage else 0
	disc_amt = flt(discount_amount) if discount_amount else 0

	if (disc_pct > 0 or disc_amt > 0) and not enable_discount:
		frappe.throw(_("Discount is disabled for this POS Profile"))


	if enable_discount and (disc_pct > 0 or disc_amt > 0):
		doc.apply_discount_on = "Grand Total"
		if disc_pct > 0:
			doc.additional_discount_percentage = disc_pct
			doc.discount_amount = 0
		else:
			doc.discount_amount = disc_amt
			doc.additional_discount_percentage = 0

	doc.set_missing_values()
	doc.calculate_taxes_and_totals()


	payable_amount = flt(doc.rounded_total or doc.grand_total)

	
	doc.set("payments", [])
	if payments and len(payments) > 0:
		mop = payments[0].get("mode_of_payment") if isinstance(payments[0], dict) else getattr(payments[0], "mode_of_payment", "Cash")
		doc.append("payments", {
			"mode_of_payment": mop,
			"amount": payable_amount
		})
	else:
		doc.append("payments", {
			"mode_of_payment": "Cash",
			"amount": payable_amount
		})

	doc.paid_amount = payable_amount
	doc.status = "Paid"
	doc.submit()

	return {"invoice": doc.name, "grand_total": doc.grand_total}

@frappe.whitelist()
def settle_takeaway(pos_profile, items, customer=None, mode_of_payment=None, comments=None):
	import json
	

	order_res = create_or_update_order(
		pos_profile=pos_profile,
		items=items,
		customer=customer,
		order_type="Take Away",
		comments=comments,
		generate_kot=1
	)
	
	
	frappe.db.commit()
	
	invoice_name = order_res.get("invoice")
	doc = frappe.get_doc("POS Invoice", invoice_name)
	
	
	if not mode_of_payment:
		profile = frappe.get_cached_doc("POS Profile", pos_profile)
		default_mop = next((p.mode_of_payment for p in profile.payments if p.default), None)
		if not default_mop and profile.payments:
			default_mop = profile.payments[0].mode_of_payment
		mode_of_payment = default_mop
		
	if not mode_of_payment:
		return {"invoice": invoice_name, "settled": False, "error": "No default Mode of Payment found in POS Profile"}


	try:
		payments = json.dumps([{
			"mode_of_payment": mode_of_payment,
			"amount": doc.rounded_total or doc.grand_total
		}])
		
		submit_res = submit_payment(invoice=invoice_name, payments=payments)
		
		return {
			"invoice": invoice_name,
			"settled": True,
			"grand_total": submit_res.get("grand_total")
		}
		
	except Exception as e:
	
		frappe.log_error(message=frappe.get_traceback(), title="Take Away auto-settle failed")
		

		err_msg = str(e)
		if frappe.message_log:
			try:
				err_msg = json.loads(frappe.message_log[-1]).get("message", err_msg)
			except:
				pass
				
		return {
			"invoice": invoice_name,
			"settled": False,
			"error": err_msg or "Payment failed, order saved as Draft"
		}



@frappe.whitelist()
def get_orders(pos_profile, status=None, limit=None):
	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	view_all = profile_doc.get("custom_view_all_status")
	paid_limit = profile_doc.get("custom_paid_limit")
	
	if paid_limit is None:
		paid_limit = 50


	if status in ["Paid", "Consolidated", "Return"] and not view_all:
		frappe.throw(_("Not permitted to view all statuses"))
	if status == "Recently Paid" and paid_limit == 0:
		frappe.throw(_("Recently Paid view is disabled"))


	cond = "pos_profile = %(profile)s"
	args = {"profile": pos_profile, "limit": int(limit or 50)}

	if status == "Draft":
		cond += " AND docstatus = 0 AND (custom_invoice_printed = 1 OR IFNULL(custom_nds_table, '') = '')"
	elif status == "Unbilled":
		cond += " AND docstatus = 0 AND IFNULL(custom_nds_table, '') != '' AND custom_invoice_printed = 0"
	elif status == "Recently Paid":
		cond += " AND docstatus = 1 AND status = 'Paid'"
		args["limit"] = int(paid_limit)
	elif status == "Paid":
		cond += " AND docstatus = 1 AND status = 'Paid'"
	elif status == "Consolidated":
		cond += " AND status = 'Consolidated'"
	elif status == "Return":
		cond += " AND is_return = 1"

	return frappe.db.sql(f"""
		SELECT name, customer, grand_total, status, docstatus, 
			   custom_nds_table, custom_nds_order_type, modified, owner
		FROM `tabPOS Invoice`
		WHERE {cond}
		ORDER BY modified DESC
		LIMIT %(limit)s
	""", args, as_dict=True)


@frappe.whitelist()
def get_invoice(invoice):
	if not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice))

	doc = frappe.get_doc("POS Invoice", invoice)
	item_meta = frappe.get_meta("POS Invoice Item")
	items = []
	for d in doc.items:
		row = {
			"item": d.item_code,
			"item_code": d.item_code,
			"item_name": d.item_name,
			"qty": d.qty,
			"rate": d.rate,
		}
		if item_meta.has_field("custom_nds_notes") and d.get("custom_nds_notes"):
			row["custom_nds_notes"] = d.custom_nds_notes
			row["notes"] = d.custom_nds_notes
		if item_meta.has_field("custom_is_addon") and d.get("custom_is_addon"):
			row["custom_is_addon"] = d.custom_is_addon
			row["is_addon"] = d.custom_is_addon
		if item_meta.has_field("custom_addon_group_id") and d.get("custom_addon_group_id"):
			row["custom_addon_group_id"] = d.custom_addon_group_id
			row["addon_group_id"] = d.custom_addon_group_id
		if item_meta.has_field("custom_nds_course") and d.get("custom_nds_course"):
			row["custom_nds_course"] = d.custom_nds_course
			row["course"] = d.custom_nds_course
		items.append(row)

	return {
		"name": doc.name,
		"invoice": doc.name,
		"customer": doc.customer,
		"custom_nds_order_type": doc.custom_nds_order_type,
		"custom_nds_table": doc.custom_nds_table,
		"custom_order_comments": doc.custom_order_comments,
		"modified": doc.modified,
		"items": items,
	}

@frappe.whitelist()
def mark_invoice_printed(invoice):
	doc = frappe.get_doc("POS Invoice", invoice)
	doc.db_set("custom_invoice_printed", 1)
	return True


@frappe.whitelist()
def search_customers(query=None, txt=None):

	search_term = query or txt or ""
	search_term = search_term.strip()

	if not search_term:
		return []


	return frappe.db.sql("""
		SELECT 
			name, 
			customer_name, 
			mobile_no
		FROM `tabCustomer`
		WHERE disabled = 0
		  AND (
			LOWER(customer_name) LIKE LOWER(%(txt)s)
			OR LOWER(name) LIKE LOWER(%(txt)s)
			OR mobile_no LIKE %(txt)s
		  )
		ORDER BY customer_name ASC
		LIMIT 20
	""", {"txt": f"%{search_term}%"}, as_dict=True)

def _default_pos_profile(user):
	name = frappe.db.get_value(
		"POS Profile User",
		{"user": user},
		"parent",
	)
	if name:
		return name
	return frappe.db.get_value("POS Profile", {"disabled": 0}, "name")


def _assert_opening(user, pos_profile):
	exists = frappe.db.exists(
		"POS Opening Entry",
		{"user": user, "pos_profile": pos_profile, "status": "Open", "docstatus": 1},
	)
	# Also allow if main cashier opened in multi-cashier mode
	if not exists:
		profile = frappe.get_cached_doc("POS Profile", pos_profile)
		if profile.get("custom_enable_multiple_cashier"):
			exists = frappe.db.exists(
				"POS Opening Entry",
				{"pos_profile": pos_profile, "status": "Open", "docstatus": 1},
			)
	if not exists:
		frappe.throw(_("Create a POS Opening Entry before taking orders"))


def _assert_branch_access(user, branch):
	if user == "Administrator" or "System Manager" in frappe.get_roles():
		return
	users = frappe.get_all(
		"NDS Branch User",
		filters={"parent": branch, "parenttype": "Branch"},
		pluck="user",
	)
	if users and user not in users:
		frappe.throw(_("You are not assigned to branch {0}").format(branch))


def _user_rooms(user, branch):
	rows = frappe.get_all(
		"NDS Branch User",
		filters={"parent": branch, "parenttype": "Branch", "user": user},
		pluck="room",
	)
	return [r for r in rows if r]


def _default_customer():
	name = frappe.db.get_value("Customer", {"customer_name": "Walk-in Customer"}, "name")
	if name:
		return name
	name = frappe.db.get_value("Customer", {}, "name")
	if not name:
		frappe.throw(_("Create at least one Customer"))
	return name


def _form_dict():
	return getattr(frappe.local, "form_dict", None) or {}


def _coalesce_table(table=None, form=None):
	if table:
		return table
	form = form if form is not None else _form_dict()
	return form.get("table") or form.get("custom_nds_table") or form.get("restaurant_table")


def _coalesce_order_type(order_type=None, form=None):
	if order_type:
		return order_type
	form = form if form is not None else _form_dict()
	if form.get("order_type"):
		return form.get("order_type")
	if form.get("custom_nds_order_type"):
		return form.get("custom_nds_order_type")
	return "Dine In"


def _invoice_table_name(doc):
	table = doc.get("custom_nds_table")
	if not table and doc.meta.has_field("restaurant_table"):
		table = doc.get("restaurant_table")
	return table


def _assert_table_available_for_order(table, invoice=None):
	if not table or not frappe.db.exists("NDS Table", table):
		return

	row = frappe.db.get_value(
		"NDS Table",
		table,
		["occupied", "current_invoice"],
		as_dict=True,
	)
	if not row or not row.occupied or not row.current_invoice:
		return

	current_invoice = row.current_invoice
	if invoice and current_invoice == invoice:
		return

	inv = frappe.db.get_value(
		"POS Invoice",
		current_invoice,
		["owner", "docstatus"],
		as_dict=True,
	)
	if not inv or inv.docstatus != 0:
		return

	user = frappe.session.user
	if user in (inv.owner, "Administrator"):
		return
	if "System Manager" in frappe.get_roles():
		return

	frappe.throw(
		_("Table {0} is already occupied by order {1}").format(table, current_invoice)
	)


def _set_nds_table_occupied(table, invoice_name, occupied):
	if not table or not frappe.db.exists("NDS Table", table):
		return

	meta = frappe.get_meta("NDS Table")
	values = {"occupied": 1 if occupied else 0}
	if meta.has_field("current_invoice"):
		values["current_invoice"] = invoice_name if occupied else None
	if occupied and meta.has_field("latest_invoice_time"):
		values["latest_invoice_time"] = now_datetime()
	frappe.db.set_value("NDS Table", table, values)


def _sync_nds_table_after_order_save(order_type, table, previous_table, invoice_name):
	effective_table = table if order_type != "Take Away" else None

	if previous_table and previous_table != effective_table:
		_set_nds_table_occupied(previous_table, None, occupied=False)

	if effective_table:
		_set_nds_table_occupied(effective_table, invoice_name, occupied=True)


def _sanitize_invoice_totals(doc):
	if doc.grand_total is None:
		doc.grand_total = 0.0
	if doc.base_grand_total is None:
		doc.base_grand_total = doc.grand_total
	if doc.rounded_total is None:
		doc.rounded_total = doc.grand_total
	if doc.base_rounded_total is None:
		doc.base_rounded_total = doc.base_grand_total


def _menu_if_enabled(name):
	"""
	Return menu name if it exists and is enabled, None if it exists but is disabled,
	or the name itself if the menu doesn't exist (for backward compatibility).
	"""
	if not name:
		return name
	
	if frappe.db.exists("NDS Menu", name):
		enabled = frappe.db.get_value("NDS Menu", name, "enabled")
		if enabled:
			return name
		else:
			return None  # Menu exists but is disabled
	
	# Menu doesn't exist, return the name (backward compatibility)
	return name


def _build_menu_items(menu, warehouse, price_list):
	"""
	P3-T4: Build menu items with resolved variants and add-ons.
	
	For each enabled menu row:
	- Get item details and availability
	- Resolve variants from Item.custom_pos_item_variants (with rates from menu)
	- Resolve add-ons from Item.custom_pos_add_on_items (with rates from menu)
	- Skip variant/addon codes that aren't in this menu
	
	Returns list of menu item dicts.
	"""
	from nds_restaurant.api.recipe import get_item_availability
	
	menu_items = []
	
	# Build a map of item codes to menu rows for quick lookup
	menu_item_map = {}
	for row in menu.items:
		if not row.disabled and row.item:
			menu_item_map[row.item] = row
	
	# Check if Item has custom fields (guard for pre-migration)
	meta = frappe.get_meta("Item")
	has_variant_field = meta.has_field("custom_pos_item_variants")
	has_addon_field = meta.has_field("custom_pos_add_on_items")
	
	for row in menu.items:
		if row.disabled:
			continue
		
		item = frappe.db.get_value(
			"Item",
			row.item,
			["item_name", "image", "item_group", "is_stock_item"],
			as_dict=True,
		) or {}
		
		# Calculate availability
		availability = None
		if frappe.db.exists("NDS Recipe", {"item": row.item, "enabled": 1}):
			availability = get_item_availability(row.item, warehouse)
		elif item.get("is_stock_item"):
			availability = flt(
				frappe.db.get_value(
					"Bin",
					{"item_code": row.item, "warehouse": warehouse},
					"actual_qty",
				)
				or 0
			)
		
		# Resolve variants (new model or fallback to old text field)
		variants = []
		if has_variant_field:
			# Get variants from Item child table
			variant_rows = frappe.get_all(
				"NDS POS Item Variant",
				filters={"parent": row.item, "parenttype": "Item"},
				fields=["item", "item_name"]
			)
			for v_row in variant_rows:
				variant_code = v_row.item
				if variant_code in menu_item_map:
					# Get the variant's menu row for rate and other details
					variant_menu_row = menu_item_map[variant_code]
					variant_item = frappe.db.get_value(
						"Item",
						variant_code,
						["item_name", "image", "is_stock_item"],
						as_dict=True,
					) or {}
					
					# Calculate variant availability
					variant_availability = None
					if frappe.db.exists("NDS Recipe", {"item": variant_code, "enabled": 1}):
						variant_availability = get_item_availability(variant_code, warehouse)
					elif variant_item.get("is_stock_item"):
						variant_availability = flt(
							frappe.db.get_value(
								"Bin",
								{"item_code": variant_code, "warehouse": warehouse},
								"actual_qty",
							)
							or 0
						)
					
					variants.append({
						"item": variant_code,
						"item_name": v_row.item_name or variant_item.get("item_name"),
						"rate": variant_menu_row.rate,
						"image": variant_item.get("image"),
						"availability": variant_availability,
					})
		else:
			# Fallback to old comma-separated text field
			variants = [v.strip() for v in (row.variants or "").split(",") if v.strip()]
		
		# Resolve add-ons (new model or fallback to old text field)
		addons = []
		if has_addon_field:
			# Get add-ons from Item child table
			addon_rows = frappe.get_all(
				"NDS Item Add On",
				filters={"parent": row.item, "parenttype": "Item"},
				fields=["item", "item_name"]
			)
			for a_row in addon_rows:
				addon_code = a_row.item
				if addon_code in menu_item_map:
					# Get the add-on's menu row for rate
					addon_menu_row = menu_item_map[addon_code]
					addon_item = frappe.db.get_value(
						"Item",
						addon_code,
						["item_name"],
						as_dict=True,
					) or {}
					
					addons.append({
						"item": addon_code,
						"item_name": a_row.item_name or addon_item.get("item_name"),
						"rate": addon_menu_row.rate,
					})
		else:
			# Fallback to old comma-separated text field
			addons = [a.strip() for a in (row.addons or "").split(",") if a.strip()]
		
		menu_items.append(
			{
				"item": row.item,
				"item_name": row.item_name or item.get("item_name"),
				"rate": row.rate,
				"course": row.course,
				"image": item.get("image"),
				"item_group": item.get("item_group"),
				"special_dish": row.special_dish,
				"variants": variants,
				"addons": addons,
				"availability": availability,
			}
		)
	
	return menu_items


@frappe.whitelist()
def create_customer(customer_name, mobile_number):
	if not customer_name or not mobile_number:
		frappe.throw("Customer Name and Mobile Number are required")

	exists = frappe.db.get_value("Customer", {"mobile_no": mobile_number}, "name")
	if exists:
		frappe.throw(f"Customer with mobile number {mobile_number} already exists")

	doc = frappe.new_doc("Customer")
	doc.customer_name = customer_name
	doc.customer_group = "Individual"
	doc.customer_type = "Company"
	doc.mobile_no = mobile_number
	doc.insert(ignore_permissions=True)
	
	return {"name": doc.name, "customer_name": doc.customer_name, "mobile_no": doc.mobile_no}




@frappe.whitelist()
def change_order_type(invoice, order_type, table=None, expected_modified=None):
	if not invoice:
		frappe.throw(_("Invoice number is required"))

	doc = frappe.get_doc("POS Invoice", invoice)

	if doc.docstatus != 0:
		frappe.throw(_("Can only edit order type for draft/unbilled invoices"))

	if expected_modified and str(doc.modified) != str(expected_modified):
		frappe.throw(_("Order changed on another device, please reload"))

	pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
	if not getattr(pos_profile, "custom_edit_order_type", 0):
		frappe.throw(_("Editing order type is disabled for this profile"))

	current_table = _invoice_table_name(doc)
	selected_table = None

	doc.db_set("custom_nds_order_type", order_type)

	if order_type == "Take Away":
		doc.db_set("custom_nds_table", None)
		if doc.meta.has_field("restaurant_table"):
			doc.db_set("restaurant_table", None)
		if current_table:
			_set_nds_table_occupied(current_table, None, occupied=False)
	else:
		selected_table = table or current_table
		if selected_table:
			_assert_table_available_for_order(selected_table, invoice=invoice)
			doc.db_set("custom_nds_table", selected_table)
			if doc.meta.has_field("restaurant_table"):
				doc.db_set("restaurant_table", selected_table)
			if current_table and current_table != selected_table:
				_set_nds_table_occupied(current_table, None, occupied=False)
			_set_nds_table_occupied(selected_table, invoice, occupied=True)

	return {"invoice": invoice, "order_type": order_type, "table": selected_table}
