# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime
import json

from nds_restaurant.utils.access import (
	assert_branch_access,
	assert_can_bill,
	assert_can_transfer,
	get_capabilities,
	invoice_captain,
	is_manager,
)


@frappe.whitelist()
def get_pos_context(pos_profile=None):
	"""Return restaurant, menu, tables, and opening status for the current user."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	profile = pos_profile or _default_pos_profile(user)
	if not profile:
		frappe.throw(_("No POS Profile assigned to you"))

	# Check POS Settings Invoice Type when the field exists (ERPNext v16+; salvaged from PR #11)
	invoice_type = (
		frappe.db.get_single_value("POS Settings", "invoice_type")
		if frappe.get_meta("POS Settings").has_field("invoice_type")
		else None
	)
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

	# P7-T5: a sub-cashier's opening closed by a Sub POS Closing no longer counts
	from nds_restaurant.api.shift import closing_kind, profile_opening, user_opening

	opening = user_opening(user, profile)

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
	tables = [_normalize_table_row(t) for t in tables]
	capabilities = get_capabilities(user, profile_doc)
	_annotate_table_captains(tables, user, capabilities)
	_annotate_table_ready(tables)
	rooms = frappe.get_all(
		"NDS Room",
		filters={"branch": rest.branch},
		fields=["name", "room_type"],
	)

	# Room restriction for multi-cashier
	# P4-T4: users with a transfer role see every table.
	allowed_rooms = [] if capabilities["can_transfer"] else _user_rooms(user, rest.branch)
	if allowed_rooms:
		tables = [t for t in tables if t.restaurant_room in allowed_rooms]
		rooms = [r for r in rooms if r.name in allowed_rooms]

	payments = [
		{"mode_of_payment": p.mode_of_payment, "default": p.default}
		for p in profile_doc.payments
	]

	tabs, paid_limit, view_all = _order_tabs(profile_doc, capabilities)

	# P8-T1: Branch aggregators (with their price-list rates for the menu items)
	from nds_restaurant.api.aggregators import context_aggregators

	aggregators = context_aggregators(rest.branch, _menu_item_codes(menu_items))
	if aggregators and capabilities.get("can_bill") and _aggregator_si_ready():
		tabs = tabs + [AGGREGATOR_UNPAID]

	return {
		"pos_profile": profile,
		"company": profile_doc.company,
		"warehouse": profile_doc.warehouse,
		"cost_center": profile_doc.cost_center,
		"currency": frappe.db.get_value("Company", profile_doc.company, "default_currency"),
		"time_zone": frappe.utils.get_system_timezone(),
		"restaurant": rest.as_dict(),
		"menu": menu_name,
		"price_list": price_list,
		"menu_items": menu_items,
		"courses": courses,
		"tables": tables,
		"rooms": rooms,
		"payments": payments,
		"opening": opening,
		"aggregators": aggregators,
		"shift_kind": closing_kind(profile_doc, user),
		"profile_opening": profile_opening(profile),
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
			"qz_host": profile_doc.get("custom_qz_host") or "localhost",
			"qz_printer": profile_doc.get("custom_qz_printer"),
			"kot_naming_series": profile_doc.get("custom_kot_naming_series") or "KOT-.#####",
			"multiple_cashier": profile_doc.get("custom_enable_multiple_cashier"),
			"print_format": profile_doc.get("print_format") or "NDS Receipt",
			"auto_print": 1 if profile_doc.get("custom_nds_auto_print_receipt") is None else flt(profile_doc.get("custom_nds_auto_print_receipt")),
			"table_attention_time": flt(profile_doc.get("custom_table_attention_time") or 0),
			"edit_order_type": cint(profile_doc.get("custom_edit_order_type") or 0),
			"default_customer": profile_doc.get("customer")
			or frappe.db.get_value("Customer", {"customer_name": "Walk-in Customer"}, "name"),
			"print_before_pay": 1 if _print_before_pay_enabled() else 0,
			"is_manager": capabilities["is_manager"],
			"remove_items": 1 if profile_doc.get("custom_remove_items") else 0,
			"kot_reprint": 1 if profile_doc.get("custom_enable_kot_reprint") else 0,
		},
		"capabilities": capabilities,


	}

def _restaurant_child_menu(restaurant, child_doctype, parentfield, extra_filters):
	filters = {
		"parent": restaurant,
		"parenttype": "NDS Restaurant",
		"parentfield": parentfield,
	}
	filters.update(extra_filters or {})
	return frappe.db.get_value(child_doctype, filters, "menu")


def _resolve_menu(restaurant, room=None, order_type=None):
	rest = frappe.get_cached_doc("NDS Restaurant", restaurant)
	rest_meta = rest.meta
	candidates = []

	if order_type and rest_meta.has_field("order_type_wise_menu") and rest.get("order_type_wise_menu"):
		ot_menu = _restaurant_child_menu(
			restaurant,
			"NDS Order Type Menu",
			"order_type_menu",
			{"order_type": order_type},
		)
		if ot_menu:
			candidates.append(ot_menu)

	if room and rest_meta.has_field("room_wise_menu") and rest.get("room_wise_menu"):
		room_menu = _restaurant_child_menu(
			restaurant,
			"NDS Menu For Room",
			"menu_for_room",
			{"room": room},
		)
		if room_menu:
			candidates.append(room_menu)

	active_menu = rest.get("active_menu")
	if active_menu:
		candidates.append(active_menu)

	for menu_name in candidates:
		enabled = _menu_if_enabled(menu_name)
		if enabled:
			return enabled
	return None


def _assert_menu_accessible(menu_name, restaurant_doc):
	if not menu_name or not frappe.db.exists("NDS Menu", menu_name):
		return
	menu_branch = frappe.db.get_value("NDS Menu", menu_name, "branch")
	if menu_branch and menu_branch != restaurant_doc.branch:
		frappe.throw(_("Menu {0} is not available for this branch").format(menu_name))


@frappe.whitelist()
def get_menu(pos_profile, room=None, order_type=None):
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)

	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	restaurant = profile_doc.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("No restaurant linked to this POS Profile"))

	rest = frappe.get_doc("NDS Restaurant", restaurant)
	_assert_branch_access(user, rest.branch)

	menu_name = _resolve_menu(restaurant, room, order_type)
	if not menu_name:
		return {"menu": None, "price_list": profile_doc.selling_price_list, "items": []}

	_assert_menu_accessible(menu_name, rest)

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
	aggregator=None,
	aggregator_order_id=None,
):
	"""Create or update a draft POS Invoice and optionally generate KOTs.

	P8-T1: order_type "Aggregator" needs `aggregator` (a Customer configured on the Branch's
	Aggregator Settings): customer, price list and no-tax come from that row; no table.
	"""
	import json

	if isinstance(items, str):
		items = json.loads(items)
	generate_kot = int(generate_kot or 0)

	table = _coalesce_table(table)
	order_type = _coalesce_order_type(order_type)
	if order_type == "Aggregator":
		table = None
	capabilities = get_capabilities(frappe.session.user, pos_profile)

	if table and order_type != "Take Away":
		_reconcile_stale_table_occupancy(table)
		_assert_table_not_locked(table, capabilities)
		if not invoice:
			invoice = _resolve_invoice_for_new_table_order(table)

	profile = frappe.get_doc("POS Profile", pos_profile)
	_assert_opening(frappe.session.user, pos_profile)
	
	# Get restaurant for settings
	restaurant = profile.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("POS Profile {0} has no Restaurant linked").format(pos_profile))
	
	rest = frappe.get_doc("NDS Restaurant", restaurant)

	aggregator_settings = None
	if order_type == "Aggregator":
		from nds_restaurant.api.aggregators import assert_aggregator_configured

		if not aggregator and invoice:
			aggregator = frappe.db.get_value("POS Invoice", invoice, "custom_aggregator") if frappe.get_meta(
				"POS Invoice"
			).has_field("custom_aggregator") else None
		if not aggregator:
			frappe.throw(_("Select an aggregator for Aggregator orders"))
		aggregator_settings = assert_aggregator_configured(rest.branch, aggregator)
		customer = aggregator_settings["customer"]

	if not customer:
		customer = profile.get("customer")
	if not customer:
		customer = _default_customer()

	previous_table = None
	preserved_taxes_and_charges = None
	previous_items_signature = None
	if invoice and frappe.db.exists("POS Invoice", invoice):
		doc = frappe.get_doc("POS Invoice", invoice)
		if doc.docstatus != 0:
			frappe.throw(_("Cannot edit submitted invoice"))

		_assert_order_editable_by_user(doc)

		if expected_modified and str(doc.modified) != str(expected_modified):
			frappe.throw(_("Order changed on another device, please reload"))
		previous_table = _invoice_table_name(doc)
		preserved_taxes_and_charges = doc.taxes_and_charges
		previous_items_signature = _items_signature(doc.items)
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
		if doc.meta.has_field("custom_captain"):
			doc.custom_captain = frappe.session.user
		# P7-T1: the creator is the cashier until someone takes the payment (submit_payment overwrites it)
		if doc.meta.has_field("custom_cashier"):
			doc.custom_cashier = frappe.session.user
		# P7-T2: daily order number, assigned once on the first save
		from nds_restaurant.api.shift import assign_order_no

		assign_order_no(doc)

	doc.customer = customer
	doc.custom_nds_order_type = order_type
	doc.custom_order_comments = comments

	if order_type in ("Take Away", "Aggregator"):
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
	if not resolved_menu:
		frappe.throw(_("No enabled menu available for this order"))

	menu_rates = {}
	menu_courses = {}
	menu_doc = frappe.get_doc("NDS Menu", resolved_menu)
	for m_item in menu_doc.items:
		if not m_item.disabled:
			menu_rates[m_item.item] = m_item.rate
			if m_item.get("course"):
				menu_courses[m_item.item] = m_item.course

	item_meta = frappe.get_meta("POS Invoice Item")
	for row in items:
		item_code = row.get("item_code") or row.get("item")
		qty = flt(row.get("qty") or 1)

		if item_code not in menu_rates:
			frappe.throw(_("Item {0} is not on the active menu").format(item_code))
		server_rate = flt(menu_rates[item_code])


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
		# P5-T4: the course (and so the KDS serving priority) comes from the menu row
		course = menu_courses.get(item_code) or row.get("course")
		if item_meta.has_field("custom_nds_course") and course:
			item_dict["custom_nds_course"] = course

		doc.append("items", item_dict)

	# Set missing values (calculates totals, taxes, payments, etc.)
	doc.set_missing_values()
	_sanitize_invoice_totals(doc)

	if preserved_taxes_and_charges:
		doc.taxes_and_charges = preserved_taxes_and_charges
	
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

	_apply_resolved_menu_pricing(doc, menu_doc, profile, menu_rates)

	# P8-T1: aggregator customer, price list and no-tax (after the menu pricing and default tax)
	if aggregator_settings:
		from nds_restaurant.api.aggregators import apply_to_order

		apply_to_order(doc, aggregator_settings, menu_rates)
		if doc.meta.has_field("custom_aggregator_order_id") and aggregator_order_id is not None:
			doc.custom_aggregator_order_id = (aggregator_order_id or "").strip()[:140] or None
	elif doc.meta.has_field("custom_aggregator") and doc.get("custom_aggregator"):
		doc.custom_aggregator = None
		if doc.meta.has_field("custom_aggregator_order_id"):
			doc.custom_aggregator_order_id = None
	
	# P3-T7: Server-side stock validation before saving
	if invoice:
		old_doc = frappe.get_doc("POS Invoice", invoice)
		prev_qty = {}
		for old_item in old_doc.items:
			key = old_item.item_code
			prev_qty[key] = prev_qty.get(key, 0) + flt(old_item.qty)
	else:
		prev_qty = {}

	from nds_restaurant.api.recipe import get_item_availability, get_stock_item_availability

	exclude_invoice = invoice or doc.name
	for item_row in doc.items:
		item_code = item_row.item_code
		new_qty = sum(flt(ir.qty) for ir in doc.items if ir.item_code == item_code)
		old_qty = prev_qty.get(item_code, 0)
		extra_qty = new_qty - old_qty

		if extra_qty > 0:
			if frappe.db.exists("NDS Recipe", {"item": item_code, "enabled": 1}):
				availability = get_item_availability(
					item_code, profile.warehouse, exclude_invoice=exclude_invoice
				)
				if availability is not None and new_qty > availability:
					frappe.throw(
						_("Only {0} portions of {1} available").format(
							int(availability), frappe.bold(item_code)
						)
					)
			elif frappe.db.get_value("Item", item_code, "is_stock_item"):
				availability = get_stock_item_availability(
					item_code, profile.warehouse, exclude_invoice=exclude_invoice
				)
				if availability is not None and new_qty > availability:
					frappe.throw(
						_("Only {0} portions of {1} available").format(
							int(availability), frappe.bold(item_code)
						)
					)

	if invoice and not capabilities["can_remove_items"]:
		_assert_sent_items_kept(invoice, doc.items)

	if doc.meta.has_field("custom_invoice_printed"):
		# P2-T3: a printed bill stays valid until the items change.
		if previous_items_signature is None or previous_items_signature != _items_signature(doc.items):
			doc.custom_invoice_printed = 0
	doc.flags.ignore_permissions = True
	doc.save()

	_sync_nds_table_after_order_save(
		order_type=order_type,
		table=table,
		previous_table=previous_table,
		invoice_name=doc.name,
	)

	kot_result = _send_kots(doc.name) if generate_kot else {}

	modified = frappe.db.get_value("POS Invoice", doc.name, "modified")

	return {
		"invoice": doc.name,
		"grand_total": doc.grand_total,
		"modified": modified,
		"status": doc.status,
		"invoice_printed": cint(doc.get("custom_invoice_printed") or 0),
		"items": _invoice_items_payload(doc),
		"sent_items": _sent_items(doc.name),
		"kots": kot_result.get("created") or [],
		"kot_warnings": kot_result.get("warnings") or [],
		"kot_error": kot_result.get("error"),
	}


def _send_kots(invoice):
	"""P5-T1: create KOTs without ever losing the saved order.

	On failure the KOT work is rolled back to a savepoint, "KOT Creation Failed" is logged and the
	message is returned as `error` (the POS shows it as a red toast).
	"""
	from nds_restaurant.api.kot import kot_execute_with_warnings

	message_count = len(frappe.local.message_log or [])
	frappe.db.savepoint("nds_kot_execute")
	try:
		return kot_execute_with_warnings(invoice)
	except Exception as e:
		frappe.db.rollback(save_point="nds_kot_execute")
		# drop the msgprint queued by frappe.throw so the request itself still succeeds
		if frappe.local.message_log:
			del frappe.local.message_log[message_count:]
		frappe.log_error(title="KOT Creation Failed", message=frappe.get_traceback(), reference_doctype="POS Invoice", reference_name=invoice)
		return {"created": [], "warnings": [], "error": frappe.utils.strip_html(str(e)) or _("KOT creation failed")}


def _sent_items(invoice):
	from nds_restaurant.api.kot import sent_items_payload

	return sent_items_payload(invoice)


def _line_key(row):
	return (
		row.get("item_code"),
		row.get("custom_nds_notes") or "",
		row.get("custom_addon_group_id") or "",
	)


def _assert_sent_items_kept(invoice, rows):
	"""P4-T5: quantities already sent to the kitchen can't be reduced without remove_items."""
	from nds_restaurant.api.kot import sent_quantities

	sent = sent_quantities(invoice)
	if not sent:
		return
	current = {}
	for row in rows or []:
		key = _line_key(row)
		current[key] = current.get(key, 0) + flt(row.get("qty"))
	for key, qty in sent.items():
		if flt(current.get(key, 0)) < flt(qty):
			frappe.throw(
				_("Items already sent to kitchen cannot be removed: {0}").format(key[0]),
				title=_("Item locked"),
			)



@frappe.whitelist()
def submit_payment(invoice, payments, discount_percentage=None, discount_amount=None):
	if isinstance(payments, str):
		payments = json.loads(payments)

	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	assert_can_bill(doc.pos_profile)
	if doc.docstatus != 0:
		frappe.throw(_("Invoice {0} is already submitted or cancelled").format(doc.name))
	_assert_printed_before_payment(doc)

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
	# P8-T1: set_missing_values reloads the profile's tax template and price list; an aggregator
	# order keeps its own
	if doc.meta.has_field("custom_aggregator") and doc.get("custom_aggregator"):
		from nds_restaurant.api.aggregators import order_settings

		agg = order_settings(doc)
		if agg and agg.get("without_tax"):
			doc.taxes_and_charges = None
			doc.set("taxes", [])
		if agg and agg.get("price_list"):
			doc.selling_price_list = agg["price_list"]
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
	if doc.meta.has_field("custom_cashier"):
		doc.custom_cashier = frappe.session.user
	doc.submit()

	_free_nds_table_for_invoice(doc.name, doc=doc)

	return {"invoice": doc.name, "grand_total": doc.grand_total}

@frappe.whitelist()
def settle_takeaway(pos_profile, items, customer=None, mode_of_payment=None, comments=None):
	import json

	_assert_pos_profile_access(pos_profile)
	assert_can_bill(pos_profile)

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



AGGREGATOR_UNPAID = "Aggregator Unpaid"
ORDER_STATUSES = ("Draft", "Unbilled", "Recently Paid", "Paid", "Consolidated", "Return", AGGREGATOR_UNPAID)


def _aggregator_si_ready():
	"""P8-T3: Keep Unpaid aggregator orders live as Sales Invoices (custom field installed)."""
	return frappe.get_meta("Sales Invoice").has_field("custom_source_pos_invoice")


def _menu_item_codes(menu_items):
	codes = []
	for row in menu_items or []:
		if row.get("item"):
			codes.append(row.get("item"))
		for variant in row.get("variants") or []:
			if isinstance(variant, dict) and variant.get("item"):
				codes.append(variant.get("item"))
	return codes


def _aggregator_unpaid_orders(pos_profile, aggregator=None, search=None, limit=50):
	"""P8-T3: unpaid aggregator Sales Invoices of this till, shaped like Orders rows."""
	if not _aggregator_si_ready():
		return []
	filters = {
		"pos_profile": pos_profile,
		"docstatus": 1,
		"custom_source_pos_invoice": ["is", "set"],
		"outstanding_amount": [">", 0],
	}
	if aggregator:
		filters["custom_aggregator"] = aggregator
	or_filters = None
	if search and str(search).strip():
		like = f"%{str(search).strip()}%"
		or_filters = [
			["name", "like", like],
			["custom_source_pos_invoice", "like", like],
			["custom_aggregator_order_id", "like", like],
		]
	rows = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"customer",
			"customer_name",
			"grand_total",
			"rounded_total",
			"outstanding_amount",
			"status",
			"docstatus",
			"posting_date",
			"posting_time",
			"modified",
			"creation",
			"owner",
			"custom_aggregator",
			"custom_aggregator_order_id",
			"custom_source_pos_invoice",
			"custom_daily_order_no",
		],
		order_by="posting_date desc, posting_time desc",
		limit=limit,
	)
	for r in rows:
		r["aggregator"] = r.get("custom_aggregator")
		r["aggregator_order_id"] = r.get("custom_aggregator_order_id")
		r["source_pos_invoice"] = r.get("custom_source_pos_invoice")
		r["daily_order_no"] = r.get("custom_daily_order_no")
		r["doctype"] = "Sales Invoice"
		r["order_type"] = r["custom_nds_order_type"] = "Aggregator"
		r["table"] = r["custom_nds_table"] = None
		r["aggregator_name"] = r.get("customer_name")
		r["order_status"] = "Unpaid (aggregator)"
	return rows
POS_MANAGER_ROLES = ("NDS Manager", "System Manager")


def _is_pos_manager(user=None):
	return is_manager(user)


def _assert_pos_profile_access(pos_profile):
	"""Allow managers, or users listed on the POS Profile (an empty list means everyone)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		frappe.throw(_("POS Profile {0} not found").format(pos_profile or ""))
	if _is_pos_manager(user):
		return
	users = frappe.get_all(
		"POS Profile User",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		pluck="user",
	)
	if users and user not in users:
		frappe.throw(
			_("You are not allowed to access POS Profile {0}").format(pos_profile),
			frappe.PermissionError,
		)


def _order_tabs(profile_doc, capabilities=None):
	"""Visible Orders tabs for a profile: (tabs, paid_limit, view_all).

	P4-T2: users who can't bill only get the Draft/Unbilled tabs.
	"""
	paid_limit = profile_doc.get("custom_paid_limit")
	if paid_limit is None:
		paid_limit = 50
	paid_limit = cint(paid_limit)
	view_all = cint(profile_doc.get("custom_view_all_status") or 0)
	if capabilities is not None and not capabilities.get("can_bill"):
		return ["Draft", "Unbilled"], 0, 0
	tabs = ["Draft", "Unbilled"]
	if paid_limit > 0:
		tabs.append("Recently Paid")
	if view_all:
		tabs.extend(["Paid", "Consolidated", "Return"])
	return tabs, paid_limit, view_all


def _print_before_pay_enabled():
	return frappe.get_meta("POS Invoice").has_field("custom_invoice_printed")


def _assert_printed_before_payment(doc):
	"""P2-T3: dine-in table bills must be printed before payment."""
	if not _print_before_pay_enabled():
		return
	if (doc.get("custom_nds_order_type") or "Dine In") != "Dine In":
		return
	if not _invoice_table_name(doc):
		return
	if cint(doc.get("custom_invoice_printed") or 0):
		return
	frappe.throw(_("Please print invoice before making payment"))


def _items_signature(rows):
	sig = []
	for r in rows or []:
		sig.append(
			(
				r.get("item_code"),
				flt(r.get("qty")),
				r.get("custom_nds_notes") or "",
				r.get("custom_addon_group_id") or "",
			)
		)
	return sorted(sig)


def _order_list_status(row):
	if row.get("docstatus") == 2:
		return "Cancelled"
	if row.get("docstatus") == 1:
		if row.get("is_return"):
			return "Return"
		return row.get("status") or "Paid"
	if row.get("table") and not cint(row.get("invoice_printed") or 0):
		return "Unbilled"
	return "Draft"


@frappe.whitelist()
def get_orders(pos_profile, status=None, limit=None, table=None, captain=None, search=None, aggregator=None):
	"""P2-T1: list POS orders for the Orders page, filtered by tab, table, captain and search.

	P8-T3: `aggregator` (Customer) filters to that platform's orders; the "Aggregator Unpaid" tab
	lists the receivable Sales Invoices of Keep Unpaid aggregator orders.
	"""
	_assert_pos_profile_access(pos_profile)
	profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	caps = get_capabilities(profile=profile_doc)
	_tabs, paid_limit, view_all = _order_tabs(profile_doc, caps)

	status = status or "Draft"
	if status not in ORDER_STATUSES:
		frappe.throw(_("Unknown order status {0}").format(status))
	if status == AGGREGATOR_UNPAID:
		if not caps.get("can_bill"):
			frappe.throw(_("Not permitted to view aggregator invoices"), frappe.PermissionError)
		return _aggregator_unpaid_orders(pos_profile, aggregator, search, max(1, min(cint(limit) or 50, 200)))
	if status in ("Paid", "Consolidated", "Return") and not view_all:
		frappe.throw(_("Not permitted to view all statuses"), frappe.PermissionError)
	if status == "Recently Paid" and paid_limit <= 0:
		frappe.throw(_("Recently Paid view is disabled"), frappe.PermissionError)

	meta = frappe.get_meta("POS Invoice")
	has_printed = meta.has_field("custom_invoice_printed")
	has_captain = meta.has_field("custom_captain")
	has_table = meta.has_field("custom_nds_table")
	has_room = meta.has_field("custom_nds_room")
	has_type = meta.has_field("custom_nds_order_type")
	has_cashier = meta.has_field("custom_cashier")
	has_order_no = meta.has_field("custom_daily_order_no")
	has_aggregator = meta.has_field("custom_aggregator")
	has_aggregator_id = meta.has_field("custom_aggregator_order_id")

	table_col = "IFNULL(custom_nds_table, '')" if has_table else "''"
	printed_col = "IFNULL(custom_invoice_printed, 0)" if has_printed else "0"

	cond = ["pos_profile = %(profile)s"]
	args = {"profile": pos_profile}
	requested_limit = cint(limit)
	limit = max(1, min(requested_limit or 50, 200))

	if status == "Draft":
		cond.append(f"docstatus = 0 AND ({printed_col} = 1 OR {table_col} = '')")
	elif status == "Unbilled":
		cond.append(f"docstatus = 0 AND {table_col} != '' AND {printed_col} = 0")
	elif status == "Recently Paid":
		cond.append("docstatus = 1 AND status = 'Paid' AND IFNULL(is_return, 0) = 0")
		limit = min(requested_limit, paid_limit) if requested_limit else paid_limit
	elif status == "Paid":
		cond.append("docstatus = 1 AND status = 'Paid' AND IFNULL(is_return, 0) = 0")
	elif status == "Consolidated":
		cond.append("docstatus = 1 AND status = 'Consolidated'")
	elif status == "Return":
		cond.append("docstatus = 1 AND IFNULL(is_return, 0) = 1")

	if table and has_table:
		cond.append("custom_nds_table = %(table)s")
		args["table"] = table
	if aggregator and has_aggregator:
		cond.append("custom_aggregator = %(aggregator)s")
		args["aggregator"] = aggregator
	if captain:
		if has_captain:
			cond.append("(IFNULL(custom_captain, owner) = %(captain)s)")
		else:
			cond.append("owner = %(captain)s")
		args["captain"] = captain
	if search and str(search).strip():
		args["search"] = f"%{str(search).strip()}%"
		parts = ["name LIKE %(search)s", "customer LIKE %(search)s", "customer_name LIKE %(search)s"]
		# P7-T2: "#12" or "12" finds the daily order number
		order_no = str(search).strip().lstrip("#")
		if has_order_no and order_no.isdigit():
			args["order_no"] = cint(order_no)
			parts.append("custom_daily_order_no = %(order_no)s")
		if has_table:
			parts.append("custom_nds_table LIKE %(search)s")
		if has_aggregator_id:
			parts.append("custom_aggregator_order_id LIKE %(search)s")
		cond.append("(" + " OR ".join(parts) + ")")

	args["limit"] = limit
	cols = [
		"name",
		"customer",
		"customer_name",
		"grand_total",
		"rounded_total",
		"status",
		"docstatus",
		"is_return",
		"posting_date",
		"posting_time",
		"modified",
		"creation",
		"owner",
		f"{table_col} AS `table`",
		f"{printed_col} AS invoice_printed",
		("IFNULL(custom_captain, owner)" if has_captain else "owner") + " AS captain",
		("custom_nds_room" if has_room else "NULL") + " AS room",
		("custom_nds_order_type" if has_type else "NULL") + " AS order_type",
		("custom_cashier" if has_cashier else "NULL") + " AS cashier",
		("custom_daily_order_no" if has_order_no else "NULL") + " AS daily_order_no",
		("custom_aggregator" if has_aggregator else "NULL") + " AS aggregator",
		("custom_aggregator_order_id" if has_aggregator_id else "NULL") + " AS aggregator_order_id",
	]
	order_by = "modified DESC" if status in ("Draft", "Unbilled") else "posting_date DESC, posting_time DESC, modified DESC"
	rows = frappe.db.sql(
		f"""
		SELECT {", ".join(cols)}
		FROM `tabPOS Invoice`
		WHERE {" AND ".join(cond)}
		ORDER BY {order_by}
		LIMIT %(limit)s
		""",
		args,
		as_dict=True,
	)
	for r in rows:
		# Backward-compatible keys used by older UI code.
		r["custom_nds_table"] = r.get("table") or None
		r["custom_nds_order_type"] = r.get("order_type")
		r["order_status"] = _order_list_status(r)
		r["aggregator_name"] = r.get("customer_name") if r.get("aggregator") else None
	return rows


def _order_capabilities(doc):
	user = frappe.session.user
	caps = get_capabilities(user, doc.pos_profile)
	is_manager = bool(caps["is_manager"])
	roles = set(frappe.get_roles(user))
	has_kots = bool(
		frappe.db.exists("NDS KOT", {"pos_invoice": doc.name, "docstatus": 1})
	)
	is_draft = doc.docstatus == 0
	captain = invoice_captain(doc)
	can_edit = is_draft and (is_manager or user == captain)
	can_pay = is_draft and bool(caps["can_bill"])
	if is_draft:
		can_cancel = is_manager or (
			not has_kots and (user == captain or "NDS Cashier" in roles)
		)
	elif doc.docstatus == 1:
		can_cancel = is_manager and doc.status != "Consolidated"
	else:
		can_cancel = False
	return {
		"can_edit": 1 if can_edit else 0,
		"can_pay": 1 if can_pay else 0,
		"can_cancel": 1 if can_cancel else 0,
		"can_print": 1,
		"can_transfer": 1 if (is_draft and caps["can_transfer"]) else 0,
		"can_remove_items": caps["can_remove_items"],
		"can_reprint_kot": 1 if (has_kots and _kot_reprint_enabled(doc.pos_profile) and (is_manager or caps["can_bill"])) else 0,
		"has_kots": 1 if has_kots else 0,
	}


def _kot_reprint_enabled(pos_profile):
	"""P6-T4: POS Profile 'Enable KOT Reprint' (guarded for sites without the field)."""
	if not pos_profile or not frappe.get_meta("POS Profile").has_field("custom_enable_kot_reprint"):
		return 0
	return cint(frappe.db.get_value("POS Profile", pos_profile, "custom_enable_kot_reprint") or 0)


@frappe.whitelist()
def get_invoice(invoice):
	"""P2-T4: full order payload for reopening, the Orders detail panel and printing."""
	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice))

	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	table = _invoice_table_name(doc)
	if doc.docstatus == 0 and table:
		_assert_invoice_not_locked(doc, table, get_capabilities(profile=doc.pos_profile))
	items = _invoice_items_payload(doc)
	kot_fields = ["name", "kot_type", "docstatus", "production_unit", "creation", "served"]
	kot_meta = frappe.get_meta("NDS KOT")
	for optional in ("order_status", "production_time", "serve_time", "picked_up_time", "original_kot"):
		if kot_meta.has_field(optional):
			kot_fields.append(optional)
	kots = frappe.get_all(
		"NDS KOT",
		filters={"pos_invoice": doc.name},
		fields=kot_fields,
		order_by="creation asc",
	)
	from nds_restaurant.api.kot import READY_KOT_TYPES

	for k in kots:
		# P5-T3: what the POS may do with each KOT
		k["can_pick_up"] = 1 if (
			k.docstatus == 1 and k.kot_type in READY_KOT_TYPES and k.get("order_status") == "Served"
		) else 0
	captain = invoice_captain(doc)

	return {
		"name": doc.name,
		"invoice": doc.name,
		"pos_profile": doc.pos_profile,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"custom_nds_order_type": doc.get("custom_nds_order_type"),
		"order_type": doc.get("custom_nds_order_type"),
		"custom_nds_table": table,
		"table": table,
		"room": doc.get("custom_nds_room"),
		"custom_order_comments": doc.get("custom_order_comments"),
		"modified": doc.modified,
		"posting_date": doc.posting_date,
		"posting_time": doc.posting_time,
		"status": doc.status,
		"docstatus": doc.docstatus,
		"is_return": doc.is_return,
		"order_status": _order_list_status(
			{
				"docstatus": doc.docstatus,
				"is_return": doc.is_return,
				"status": doc.status,
				"table": table,
				"invoice_printed": doc.get("custom_invoice_printed"),
			}
		),
		"invoice_printed": cint(doc.get("custom_invoice_printed") or 0),
		"owner": doc.owner,
		"captain": captain,
		"cashier": doc.get("custom_cashier"),
		"daily_order_no": cint(doc.get("custom_daily_order_no") or 0) or None,
		"aggregator": doc.get("custom_aggregator"),
		"aggregator_name": doc.customer_name if doc.get("custom_aggregator") else None,
		"aggregator_order_id": doc.get("custom_aggregator_order_id"),
		"currency": doc.currency,
		"total": doc.total,
		"net_total": doc.net_total,
		"total_taxes_and_charges": doc.total_taxes_and_charges,
		"discount_amount": doc.discount_amount,
		"additional_discount_percentage": doc.additional_discount_percentage,
		"grand_total": doc.grand_total,
		"rounded_total": doc.rounded_total,
		"paid_amount": doc.paid_amount,
		"payments": [
			{"mode_of_payment": p.mode_of_payment, "amount": p.amount}
			for p in (doc.payments or [])
			if flt(p.amount)
		],
		"items": items,
		"sent_items": _sent_items(doc.name) if doc.docstatus == 0 else [],
		"kots": kots,
		**_order_capabilities(doc),
	}


@frappe.whitelist(methods=["POST"])
def mark_invoice_printed(invoice):
	"""P2-T3: the bill was printed; a draft table order moves from Unbilled to Draft."""
	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice))
	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	if doc.docstatus == 0 and doc.meta.has_field("custom_invoice_printed"):
		doc.db_set("custom_invoice_printed", 1, update_modified=False)
	return {
		"invoice": doc.name,
		"invoice_printed": cint(doc.get("custom_invoice_printed") or 0),
		"modified": frappe.db.get_value("POS Invoice", doc.name, "modified"),
	}


@frappe.whitelist(methods=["POST"])
def cancel_order(invoice, reason=None):
	"""Void a draft order (kitchen gets a Cancelled KOT) or cancel a paid invoice (manager only)."""
	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice))
	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	caps = _order_capabilities(doc)
	reason = (reason or "").strip()

	if doc.docstatus == 2:
		frappe.throw(_("Invoice {0} is already cancelled").format(doc.name))

	if not caps["can_cancel"]:
		if doc.docstatus == 1:
			msg = _("Only an NDS Manager can cancel a paid invoice")
			if doc.status == "Consolidated":
				msg = _("Invoice {0} is already consolidated; create a return instead").format(doc.name)
		elif caps["has_kots"]:
			msg = _("Order {0} was already sent to the kitchen; only an NDS Manager can void it").format(doc.name)
		else:
			msg = _("You are not allowed to cancel order {0}").format(doc.name)
		frappe.throw(msg, frappe.PermissionError)

	table = _invoice_table_name(doc)

	if doc.docstatus == 0:
		created_kots = []
		if caps["has_kots"]:
			from nds_restaurant.api.kot import generate_kots

			note = _("VOID {0}").format(doc.name) + (f": {reason}" if reason else "")
			created_kots = generate_kots(doc.name, cancel_all=True, comments=note)
		_free_nds_table_for_invoice(doc.name, doc=doc, table=table)
		# Submitted KOTs keep the invoice name for the kitchen audit trail, so skip the link check.
		frappe.delete_doc(
			"POS Invoice",
			doc.name,
			ignore_permissions=True,
			force=bool(caps["has_kots"]),
		)
		return {"invoice": invoice, "action": "voided", "table": table, "kots": created_kots}

	doc.flags.ignore_permissions = True
	doc.cancel()
	if reason:
		doc.add_comment("Comment", _("Cancelled from POS: {0}").format(reason))
	_free_nds_table_for_invoice(doc.name, doc=doc, table=table)
	return {"invoice": invoice, "action": "cancelled", "table": table}


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
	from nds_restaurant.api.shift import assert_opening_is_today

	from nds_restaurant.api.shift import profile_opening, user_opening

	own = user_opening(user, pos_profile)
	exists = own.name if own else None
	# Also allow if main cashier opened in multi-cashier mode
	if not exists:
		profile = frappe.get_cached_doc("POS Profile", pos_profile)
		if profile.get("custom_enable_multiple_cashier"):
			exists = profile_opening(pos_profile)
	if not exists:
		frappe.throw(_("Create a POS Opening Entry before taking orders"))
	# P7-T3: no orders against yesterday's opening when Daily POS Close is on
	assert_opening_is_today(exists, pos_profile)


def _assert_branch_access(user, branch):
	"""P4-T6: moved to utils.access (kept as an alias for older imports)."""
	assert_branch_access(user, branch)


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


def _user_can_takeover_table_order():
	return is_manager()


def _assert_order_editable_by_user(doc):
	"""Owner lock: only the order's captain (custom_captain, else creator) or a manager may edit."""
	user = frappe.session.user
	if user in (invoice_captain(doc), "Administrator"):
		return
	if is_manager(user):
		return
	frappe.throw(_("You are not allowed to modify order {0}").format(doc.name))


def _table_captains(invoices):
	"""{invoice: captain} for draft invoices (custom_captain when migrated, else owner)."""
	invoices = [i for i in invoices if i]
	if not invoices:
		return {}
	fields = ["name", "owner", "docstatus"]
	if frappe.get_meta("POS Invoice").has_field("custom_captain"):
		fields.append("custom_captain")
	rows = frappe.get_all("POS Invoice", filters={"name": ["in", invoices]}, fields=fields)
	return {r.name: (r.get("custom_captain") or r.owner) for r in rows if r.docstatus == 0}


def _annotate_table_captains(tables, user, capabilities):
	"""P4-T3: occupied tables carry their captain; restricted users see others' tables as locked."""
	captains = _table_captains([t.get("current_invoice") for t in tables if t.get("occupied")])
	restricted = bool(capabilities.get("table_restricted"))
	for t in tables:
		captain = captains.get(t.get("current_invoice")) if t.get("occupied") else None
		t["captain"] = captain
		t["locked"] = 1 if (restricted and captain and captain != user) else 0


def _annotate_table_ready(tables):
	"""P5-T3: `ready` = the table's order has a KOT that is Served but not yet Picked Up."""
	invoices = [t.get("current_invoice") for t in tables if t.get("occupied") and t.get("current_invoice")]
	ready = set()
	if invoices and frappe.db.table_exists("NDS KOT") and frappe.get_meta("NDS KOT").has_field("order_status"):
		from nds_restaurant.api.kot import READY_KOT_TYPES, STATUS_SERVED

		ready = set(
			frappe.get_all(
				"NDS KOT",
				filters={
					"pos_invoice": ["in", invoices],
					"docstatus": 1,
					"order_status": STATUS_SERVED,
					"kot_type": ["in", list(READY_KOT_TYPES)],
				},
				pluck="pos_invoice",
			)
		)
	for t in tables:
		t["ready"] = 1 if (t.get("occupied") and t.get("current_invoice") in ready) else 0


def _assert_table_not_locked(table, capabilities):
	"""P4-T3: a restricted user can't open a table held by another captain."""
	if not capabilities.get("table_restricted"):
		return
	open_inv = _table_open_draft_invoice(table)
	if not open_inv:
		return
	captain = _table_captains([open_inv]).get(open_inv)
	if captain and captain != frappe.session.user:
		frappe.throw(_("Table {0} belongs to {1}").format(table, captain), frappe.PermissionError)


def _assert_invoice_not_locked(doc, table, capabilities):
	if not capabilities.get("table_restricted"):
		return
	captain = invoice_captain(doc)
	if captain and captain != frappe.session.user:
		frappe.throw(_("Table {0} belongs to {1}").format(table, captain), frappe.PermissionError)


def _table_open_draft_invoice(table):
	if not table or not frappe.db.exists("NDS Table", table):
		return None
	row = frappe.db.get_value(
		"NDS Table",
		table,
		["occupied", "current_invoice"],
		as_dict=True,
	)
	if not row or not row.occupied or not row.current_invoice:
		return None
	inv_name = row.current_invoice
	if not frappe.db.exists("POS Invoice", inv_name):
		return None
	if frappe.db.get_value("POS Invoice", inv_name, "docstatus") != 0:
		return None
	return inv_name


def _resolve_invoice_for_new_table_order(table):
	open_inv = _table_open_draft_invoice(table)
	if not open_inv:
		return None
	if _user_can_takeover_table_order():
		return open_inv
	frappe.throw(_("Table has an open order {0}, reopen it").format(open_inv))


def _normalize_table_row(table_row):
	"""Read-only: show tables linked to submitted/cancelled invoices as free in GET context."""
	if not table_row.get("current_invoice"):
		return table_row
	docstatus = frappe.db.get_value("POS Invoice", table_row.current_invoice, "docstatus")
	if docstatus is None or docstatus == 0:
		return table_row
	table_row.occupied = 0
	table_row.current_invoice = None
	return table_row


def _reconcile_stale_table_occupancy(table):
	"""Persist table free state when current_invoice is no longer a draft (POST paths)."""
	if not table or not frappe.db.exists("NDS Table", table):
		return
	current_invoice = frappe.db.get_value("NDS Table", table, "current_invoice")
	if not current_invoice:
		return
	docstatus = frappe.db.get_value("POS Invoice", current_invoice, "docstatus")
	if docstatus is not None and docstatus != 0:
		_free_nds_table_for_invoice(current_invoice, table=table)


def _apply_resolved_menu_pricing(doc, menu_doc, profile, menu_rates):
	"""Apply menu price list and line rates after ERPNext set_missing_values."""
	doc.selling_price_list = menu_doc.price_list or profile.selling_price_list
	for row in doc.items:
		if row.item_code in menu_rates:
			row.rate = flt(menu_rates[row.item_code])


def _free_nds_table_for_invoice(invoice_name, doc=None, table=None):
	if not table:
		if doc:
			table = _invoice_table_name(doc)
		else:
			inv = frappe.db.get_value(
				"POS Invoice",
				invoice_name,
				["custom_nds_table", "restaurant_table"],
				as_dict=True,
			)
			if not inv:
				return
			table = inv.custom_nds_table or inv.get("restaurant_table")
	if not table or not frappe.db.exists("NDS Table", table):
		return
	current = frappe.db.get_value("NDS Table", table, "current_invoice")
	if current == invoice_name:
		_set_nds_table_occupied(table, None, occupied=False)


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
		if inv and inv.docstatus != 0:
			_free_nds_table_for_invoice(current_invoice, table=table)
		return

	user = frappe.session.user
	captain = _table_captains([current_invoice]).get(current_invoice) or inv.owner
	if user in (captain, "Administrator"):
		return
	if is_manager(user):
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


def _invoice_items_payload(doc):
	item_meta = frappe.get_meta("POS Invoice Item")
	items = []
	for d in doc.items:
		row = {
			"item": d.item_code,
			"item_code": d.item_code,
			"item_name": d.item_name,
			"qty": d.qty,
			"rate": d.rate,
			"amount": d.amount,
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
	return items


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
			["item_name", "image", "item_group", "is_stock_item", "has_variants"],
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
					
					variant_name = v_row.item_name or variant_item.get("item_name")
					variants.append({
						"item": variant_code,
						"item_name": variant_name,
						"label": _variant_label(row.item_name or item.get("item_name"), variant_code, variant_name),
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
				"show_standalone": cint(row.get("show_standalone") or 0),
				"has_variants": cint(item.get("has_variants") or 0),
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

	_mark_menu_grid_visibility(menu_items)
	return menu_items


def _variant_label(parent_name, variant_code, variant_name):
	"""Short label for a variant button: ERPNext attribute values, else the name minus the parent's."""
	if variant_code and frappe.db.exists("Item", variant_code):
		values = frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": variant_code, "parenttype": "Item"},
			pluck="attribute_value",
			order_by="idx asc",
		)
		values = [v for v in values if v]
		if values:
			return " / ".join(values)
	name = (variant_name or variant_code or "").strip()
	parent = (parent_name or "").strip()
	if parent and name.lower().startswith(parent.lower()) and len(name) > len(parent):
		short = name[len(parent):].strip(" -_/:()")
		if short:
			return short
	return name


def _mark_menu_grid_visibility(menu_items):
	"""Hide variant/add-on-only rows from the menu grid and flag whether a base item is sellable.

	Unmigrated sites (no NDS Menu Item.show_standalone) keep the old behaviour: every row is a
	card and every base item is sellable.
	"""
	has_flag = frappe.get_meta("NDS Menu Item").has_field("show_standalone")
	child_codes = set()
	for entry in menu_items:
		for v in entry.get("variants") or []:
			child_codes.add(v.get("item") if isinstance(v, dict) else v)
		for a in entry.get("addons") or []:
			child_codes.add(a.get("item") if isinstance(a, dict) else a)
	for entry in menu_items:
		standalone = bool(entry.get("show_standalone"))
		entry["grid_hidden"] = 1 if (has_flag and entry["item"] in child_codes and not standalone) else 0
		if entry.get("has_variants"):
			# ERPNext templates can't be sold.
			entry["base_sellable"] = 0
		elif entry.get("variants") and has_flag:
			entry["base_sellable"] = 1 if standalone else 0
		else:
			entry["base_sellable"] = 1


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

	_assert_order_editable_by_user(doc)
	assert_can_bill(doc.pos_profile)

	pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
	if not getattr(pos_profile, "custom_edit_order_type", 0):
		frappe.throw(_("Editing order type is disabled for this profile"))

	restaurant = pos_profile.get("custom_restaurant")
	if not restaurant:
		frappe.throw(_("POS Profile {0} has no Restaurant linked").format(doc.pos_profile))

	current_table = _invoice_table_name(doc)
	selected_table = None

	doc.custom_nds_order_type = order_type

	if order_type in ("Take Away", "Delivery", "Aggregator"):
		doc.custom_nds_table = None
		if doc.meta.has_field("restaurant_table"):
			doc.restaurant_table = None
		if doc.meta.has_field("custom_nds_room"):
			doc.custom_nds_room = None
		if current_table:
			_set_nds_table_occupied(current_table, None, occupied=False)
	elif order_type == "Dine In":
		selected_table = table or current_table
		if not selected_table:
			frappe.throw(_("Select a table for Dine In orders"))
		_reconcile_stale_table_occupancy(selected_table)
		_assert_table_available_for_order(selected_table, invoice=invoice)
		doc.custom_nds_table = selected_table
		if doc.meta.has_field("restaurant_table"):
			doc.restaurant_table = selected_table
		room = frappe.db.get_value("NDS Table", selected_table, "restaurant_room")
		if doc.meta.has_field("custom_nds_room"):
			doc.custom_nds_room = room
		if current_table and current_table != selected_table:
			_set_nds_table_occupied(current_table, None, occupied=False)
		_set_nds_table_occupied(selected_table, invoice, occupied=True)
	else:
		selected_table = table or current_table

	room = doc.get("custom_nds_room")
	resolved_menu = _resolve_menu(restaurant, room, order_type)
	if not resolved_menu:
		frappe.throw(_("No enabled menu available for this order"))

	menu_doc = frappe.get_doc("NDS Menu", resolved_menu)
	menu_rates = {
		m_item.item: m_item.rate
		for m_item in menu_doc.items
		if not m_item.disabled and m_item.item
	}
	missing = []
	for row in doc.items:
		if row.item_code not in menu_rates:
			missing.append(row.item_code)

	if missing:
		frappe.throw(
			_("These items are not on the menu for {0}: {1}").format(
				order_type, ", ".join(missing)
			)
		)

	preserved_taxes_and_charges = doc.taxes_and_charges
	doc.set_missing_values()
	if preserved_taxes_and_charges:
		doc.taxes_and_charges = preserved_taxes_and_charges
	_apply_resolved_menu_pricing(doc, menu_doc, pos_profile, menu_rates)
	doc.flags.ignore_permissions = True
	doc.save()

	return {
		"invoice": invoice,
		"order_type": order_type,
		"table": selected_table,
		"modified": doc.modified,
		"grand_total": doc.grand_total,
		"items": _invoice_items_payload(doc),
	}


# ---------------------------------------------------------------------------
# P4-T4: captain transfer, table move and order merge
# ---------------------------------------------------------------------------


def _load_draft_order(invoice, expected_modified=None):
	if not invoice or not frappe.db.exists("POS Invoice", invoice):
		frappe.throw(_("Invoice {0} not found").format(invoice or ""))
	doc = frappe.get_doc("POS Invoice", invoice)
	_assert_pos_profile_access(doc.pos_profile)
	if doc.docstatus != 0:
		frappe.throw(_("Only open (draft) orders can be transferred: {0}").format(doc.name))
	if expected_modified and str(doc.modified) != str(expected_modified):
		frappe.throw(_("Order changed on another device, please reload"))
	return doc


def _transfer_candidates(profile_doc):
	"""Users an order can be handed to: the Branch User list, else the POS Profile users, else
	every enabled user with an NDS POS role."""
	from nds_restaurant.utils.access import NDS_POS_ROLES, branch_users

	branch = profile_doc.get("custom_branch")
	if not branch and profile_doc.get("custom_restaurant"):
		branch = frappe.db.get_value("NDS Restaurant", profile_doc.custom_restaurant, "branch")
	users = list(dict.fromkeys(branch_users(branch)))
	if not users:
		users = list(
			dict.fromkeys(row.user for row in (profile_doc.get("applicable_for_users") or []) if row.user)
		)
	if not users:
		users = list(
			dict.fromkeys(
				frappe.get_all(
					"Has Role",
					filters={"role": ["in", list(NDS_POS_ROLES)], "parenttype": "User"},
					pluck="parent",
				)
			)
		)
	if not users:
		return []
	rows = frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1},
		fields=["name", "full_name"],
	)
	by_name = {r.name: r for r in rows if r.name != "Guest"}
	return [{"user": u, "full_name": by_name[u].full_name or u} for u in users if u in by_name]


def _assert_transfer_table(to_table, profile_doc, invoice):
	if not frappe.db.exists("NDS Table", to_table):
		frappe.throw(_("Table {0} not found").format(to_table))
	row = frappe.db.get_value(
		"NDS Table", to_table, ["restaurant", "is_take_away"], as_dict=True
	)
	if row.restaurant != profile_doc.get("custom_restaurant"):
		frappe.throw(_("Table {0} belongs to another restaurant").format(to_table))
	if cint(row.is_take_away):
		frappe.throw(_("Table {0} is a take-away table").format(to_table))
	_reconcile_stale_table_occupancy(to_table)
	open_inv = _table_open_draft_invoice(to_table)
	if open_inv and open_inv != invoice:
		frappe.throw(
			_("Table {0} is occupied by order {1}; use Merge instead").format(to_table, open_inv)
		)


def _reprice_to_menu(doc, profile_doc, order_type, room, label):
	"""Re-price a draft for the menu of its (new) room/order type. Returns True if a rate changed."""
	menu_name = _resolve_menu(profile_doc.get("custom_restaurant"), room, order_type)
	if not menu_name:
		frappe.throw(_("No enabled menu available for this order"))
	menu_doc = frappe.get_doc("NDS Menu", menu_name)
	menu_rates = {m.item: m.rate for m in menu_doc.items if not m.disabled and m.item}
	missing = sorted({row.item_code for row in doc.items if row.item_code not in menu_rates})
	if missing:
		frappe.throw(
			_("These items are not on the menu for {0}: {1}").format(label, ", ".join(missing))
		)
	before = [(row.item_code, flt(row.rate)) for row in doc.items]
	preserved_taxes_and_charges = doc.taxes_and_charges
	doc.set_missing_values()
	if preserved_taxes_and_charges:
		doc.taxes_and_charges = preserved_taxes_and_charges
	_apply_resolved_menu_pricing(doc, menu_doc, profile_doc, menu_rates)
	after = [(row.item_code, flt(row.rate)) for row in doc.items]
	return before != after


def _transfer_payload(doc, **extra):
	doc.reload()
	payload = {
		"invoice": doc.name,
		"table": _invoice_table_name(doc),
		"room": doc.get("custom_nds_room"),
		"captain": invoice_captain(doc),
		"grand_total": doc.grand_total,
		"modified": doc.modified,
		"invoice_printed": cint(doc.get("custom_invoice_printed") or 0),
		"items": _invoice_items_payload(doc),
	}
	payload.update(extra)
	return payload


@frappe.whitelist()
def get_transfer_options(invoice):
	"""Captains, free tables and open orders an order can be transferred to or merged into."""
	doc = _load_draft_order(invoice)
	assert_can_transfer(doc.pos_profile)
	profile_doc = frappe.get_doc("POS Profile", doc.pos_profile)
	current_table = _invoice_table_name(doc)

	tables = frappe.get_all(
		"NDS Table",
		filters={"restaurant": profile_doc.get("custom_restaurant"), "is_take_away": 0},
		fields=["name", "restaurant_room", "no_of_seats", "occupied", "current_invoice"],
		order_by="name asc",
	)
	tables = [_normalize_table_row(t) for t in tables]
	free_tables = [
		{"name": t.name, "room": t.restaurant_room, "seats": t.no_of_seats}
		for t in tables
		if t.name != current_table and not (t.occupied and t.current_invoice)
	]

	fields = ["name", "owner", "grand_total", "rounded_total", "customer_name", "modified"]
	meta = frappe.get_meta("POS Invoice")
	for f in ("custom_nds_table", "custom_captain", "custom_nds_order_type"):
		if meta.has_field(f):
			fields.append(f)
	orders = frappe.get_all(
		"POS Invoice",
		filters={"pos_profile": doc.pos_profile, "docstatus": 0, "name": ["!=", doc.name]},
		fields=fields,
		order_by="modified desc",
		limit_page_length=100,
	)
	return {
		"invoice": doc.name,
		"captain": invoice_captain(doc),
		"table": current_table,
		"order_type": doc.get("custom_nds_order_type") or "Dine In",
		"users": _transfer_candidates(profile_doc),
		"tables": free_tables,
		"orders": [
			{
				"name": o.name,
				"table": o.get("custom_nds_table"),
				"captain": o.get("custom_captain") or o.owner,
				"order_type": o.get("custom_nds_order_type"),
				"customer_name": o.customer_name,
				"grand_total": o.rounded_total or o.grand_total,
			}
			for o in orders
		],
	}


@frappe.whitelist(methods=["POST"])
def captain_transfer(invoice, to_user=None, to_table=None, expected_modified=None):
	"""P4-T4: hand an order to another captain and/or move it to a free table.

	Moving frees the old table, occupies the new one, re-prices for the new room's menu and points the
	open KOTs at the new table so the kitchen serves the right place.
	"""
	doc = _load_draft_order(invoice, expected_modified)
	assert_can_transfer(doc.pos_profile)
	profile_doc = frappe.get_doc("POS Profile", doc.pos_profile)
	to_user = (to_user or "").strip() or None
	to_table = (to_table or "").strip() or None
	if not to_user and not to_table:
		frappe.throw(_("Choose a captain or a table to transfer to"))

	notes = []
	old_captain = invoice_captain(doc)
	if to_user and to_user != old_captain:
		if not doc.meta.has_field("custom_captain"):
			frappe.throw(_("Captain field is missing on POS Invoice; run migrate first"))
		allowed = {u["user"] for u in _transfer_candidates(profile_doc)}
		if to_user not in allowed:
			frappe.throw(_("User {0} can't take orders on this branch").format(to_user))
		doc.custom_captain = to_user
		notes.append(_("Captain {0} → {1}").format(old_captain, to_user))

	old_table = _invoice_table_name(doc)
	moved = bool(to_table and to_table != old_table)
	repriced = False
	if moved:
		order_type = doc.get("custom_nds_order_type") or "Dine In"
		if order_type != "Dine In":
			frappe.throw(_("Only Dine In orders can be moved to a table"))
		_assert_transfer_table(to_table, profile_doc, doc.name)
		room = frappe.db.get_value("NDS Table", to_table, "restaurant_room")
		doc.custom_nds_table = to_table
		if doc.meta.has_field("restaurant_table"):
			doc.restaurant_table = to_table
		if doc.meta.has_field("custom_nds_room"):
			doc.custom_nds_room = room
		repriced = _reprice_to_menu(doc, profile_doc, order_type, room, label=to_table)
		if repriced and doc.meta.has_field("custom_invoice_printed"):
			doc.custom_invoice_printed = 0
		notes.append(_("Table {0} → {1}").format(old_table or "-", to_table))

	if not notes:
		frappe.throw(_("Nothing to transfer: the order already has that captain and table"))

	doc.flags.ignore_permissions = True
	doc.save()

	kots = []
	if moved:
		from nds_restaurant.api.kot import retarget_open_kots

		if old_table:
			_free_nds_table_for_invoice(doc.name, table=old_table)
		_set_nds_table_occupied(to_table, doc.name, occupied=True)
		kots = retarget_open_kots(doc.name, to_table)

	doc.add_comment(
		"Info",
		_("Transferred by {0}: {1}").format(frappe.session.user, "; ".join(notes)),
	)
	return _transfer_payload(
		doc,
		previous_table=old_table,
		previous_captain=old_captain,
		repriced=1 if repriced else 0,
		retargeted_kots=kots,
	)


@frappe.whitelist(methods=["POST"])
def merge_orders(source_invoice, target_invoice, expected_modified=None):
	"""Merge one open order into another (e.g. two tables joined).

	The target keeps its table, captain and customer and gets the source's items re-priced for its
	menu. Items the kitchen already has are not re-sent: each production unit that held source items
	gets a Transfer KOT listing the combined order, and the source's open KOTs are pointed at the
	target table. The source order is then removed and its table freed.
	"""
	import copy

	from nds_restaurant.api.kot import create_notice_kot, retarget_open_kots, sent_state

	if not source_invoice or not target_invoice or source_invoice == target_invoice:
		frappe.throw(_("Choose two different orders to merge"))
	src = _load_draft_order(source_invoice, expected_modified)
	tgt = _load_draft_order(target_invoice)
	if src.pos_profile != tgt.pos_profile:
		frappe.throw(_("Orders from different POS Profiles can't be merged"))
	assert_can_transfer(tgt.pos_profile)
	profile_doc = frappe.get_doc("POS Profile", tgt.pos_profile)

	src_table = _invoice_table_name(src)
	tgt_table = _invoice_table_name(tgt)
	src_sent = sent_state(src.name)
	tgt_sent = sent_state(tgt.name)
	src_has_kots = bool(frappe.db.exists("NDS KOT", {"pos_invoice": src.name}))

	item_meta = frappe.get_meta("POS Invoice Item")
	for row in src.items:
		item = {
			"item_code": row.item_code,
			"qty": row.qty,
			"rate": row.rate,
			"warehouse": row.warehouse or profile_doc.warehouse,
		}
		for f in ("custom_nds_notes", "custom_is_addon", "custom_addon_group_id", "custom_nds_course"):
			if item_meta.has_field(f) and row.get(f):
				item[f] = row.get(f)
		tgt.append("items", item)

	if src.get("custom_order_comments"):
		tgt.custom_order_comments = "\n".join(
			c for c in (tgt.get("custom_order_comments"), src.custom_order_comments) if c
		)

	order_type = tgt.get("custom_nds_order_type") or "Dine In"
	_reprice_to_menu(tgt, profile_doc, order_type, tgt.get("custom_nds_room"), label=tgt_table or tgt.name)
	if tgt.meta.has_field("custom_invoice_printed"):
		tgt.custom_invoice_printed = 0
	tgt.flags.ignore_permissions = True
	tgt.save()

	notice = _("MERGED {0} into {1}").format(
		src.name + (f" ({src_table})" if src_table else ""),
		tgt.name + (f" ({tgt_table})" if tgt_table else ""),
	)
	created = []
	for unit, src_map in src_sent.items():
		combined = copy.deepcopy(tgt_sent.get(unit, {}))
		old_qty = {k: v["qty"] for k, v in combined.items()}
		for key, entry in src_map.items():
			if key in combined:
				combined[key]["qty"] += entry["qty"]
			else:
				combined[key] = dict(entry)
		name = create_notice_kot(tgt.name, unit, combined, notice, old_qty=old_qty)
		if name:
			created.append(name)
	if created:
		frappe.db.set_value("POS Invoice", tgt.name, "custom_kot_generated", 1, update_modified=False)
	retargeted = retarget_open_kots(src.name, tgt_table) if (src_has_kots and tgt_table) else []

	_free_nds_table_for_invoice(src.name, doc=src, table=src_table)
	# The kitchen got a Transfer KOT; don't let on_trash cancel the merged items (P5-T2).
	frappe.flags.nds_skip_trash_kots = src.name
	try:
		frappe.delete_doc("POS Invoice", src.name, ignore_permissions=True, force=src_has_kots)
	finally:
		frappe.flags.nds_skip_trash_kots = None
	if tgt_table and frappe.db.get_value("NDS Table", tgt_table, "current_invoice") != tgt.name:
		_set_nds_table_occupied(tgt_table, tgt.name, occupied=True)

	tgt.add_comment("Info", _("{0} by {1}").format(notice, frappe.session.user))
	return _transfer_payload(
		tgt,
		merged_from=src.name,
		freed_table=src_table,
		kots=created,
		retargeted_kots=retargeted,
	)
