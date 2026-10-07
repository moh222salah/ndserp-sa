# Copyright (c) 2026, NDS and contributors
# License: MIT

"""Shared helpers for nds_restaurant integration tests."""

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.utils import today

TEST_POS_CASHIER_EMAIL = "nds-test-cashier@example.com"
TEST_POS_CASHIER_ROLES = ("System Manager", "Sales User", "Accounts User")
TEST_POS_CAPTAIN_EMAIL = "nds-test-captain@example.com"
TEST_POS_CAPTAIN_ROLES = ("NDS Captain",)
TEST_NDS_ONLY_CASHIER_EMAIL = "nds-test-role-cashier@example.com"
TEST_NDS_ONLY_CASHIER_ROLES = ("NDS Cashier",)
TEST_POS_MANAGER_EMAIL = "nds-test-manager@example.com"
TEST_POS_MANAGER_ROLES = ("NDS Manager",)
TEST_FIXTURE_PREFIX = "NDSUT-"


def new_test_run_id():
	return uuid.uuid4().hex[:8]


def code(run_id, suffix):
	return f"{TEST_FIXTURE_PREFIX}{run_id}-{suffix}"


def is_test_fixture_name(name):
	return bool(name) and str(name).startswith(TEST_FIXTURE_PREFIX)


def ensure_test_branch(run_id):
	branch_name = code(run_id, "BR")
	if frappe.db.exists("Branch", branch_name):
		return branch_name
	frappe.get_doc({"doctype": "Branch", "branch": branch_name}).insert(ignore_permissions=True)
	return branch_name


def get_pos_profile_with_restaurant():
	"""Return a live POS Profile that has custom_restaurant set, or None."""
	for name in frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name"):
		if is_test_fixture_name(name):
			continue
		if frappe.db.get_value("POS Profile", name, "custom_restaurant"):
			return name
	return None


def ensure_test_menu(run_id, branch, menu_items, menu_name=None, enabled=1, price_list=None):
	"""Create an enabled NDS Menu with item rows. menu_items: list of (item_code, rate)."""
	menu_name = menu_name or code(run_id, "menu")
	if frappe.db.exists("NDS Menu", menu_name):
		return menu_name
	doc = {
		"doctype": "NDS Menu",
		"name": menu_name,
		"branch": branch,
		"enabled": enabled,
		"items": [{"item": item, "rate": rate} for item, rate in menu_items],
	}
	menu_meta = frappe.get_meta("NDS Menu")
	if price_list and menu_meta.has_field("price_list"):
		doc["price_list"] = price_list
	frappe.get_doc(doc).insert(ignore_permissions=True)
	return menu_name


def ensure_test_price_list(run_id, company, suffix="VIP-PL"):
	"""Selling price list for menu/VIP tests."""
	pl_name = code(run_id, suffix)
	if frappe.db.exists("Price List", pl_name):
		return pl_name
	currency = frappe.db.get_value("Company", company, "default_currency") or "USD"
	frappe.get_doc(
		{
			"doctype": "Price List",
			"price_list_name": pl_name,
			"currency": currency,
			"selling": 1,
			"enabled": 1,
		}
	).insert(ignore_permissions=True)
	return pl_name


def ensure_test_restaurant(
	run_id,
	branch,
	company,
	active_menu,
	order_type_menus=None,
	room_menus=None,
	room_wise_menu=0,
	order_type_wise_menu=None,
):
	"""Dedicated test restaurant; does not touch production NDS records."""
	restaurant_name = code(run_id, "REST")
	if frappe.db.exists("NDS Restaurant", restaurant_name):
		return restaurant_name

	rest_meta = frappe.get_meta("NDS Restaurant")
	doc = {
		"doctype": "NDS Restaurant",
		"name": restaurant_name,
		"company": company,
		"branch": branch,
		"invoice_series_prefix": "TST",
		"active_menu": active_menu,
	}
	if rest_meta.has_field("room_wise_menu"):
		doc["room_wise_menu"] = room_wise_menu
	if rest_meta.has_field("order_type_wise_menu"):
		if order_type_wise_menu is None:
			order_type_wise_menu = 1 if order_type_menus else 0
		doc["order_type_wise_menu"] = order_type_wise_menu
	if order_type_menus and rest_meta.has_field("order_type_menu"):
		doc["order_type_menu"] = [
			{"order_type": order_type, "menu": menu} for order_type, menu in order_type_menus
		]
	if room_menus and rest_meta.has_field("menu_for_room"):
		doc["menu_for_room"] = [{"room": room, "menu": menu} for room, menu in room_menus]

	frappe.get_doc(doc).insert(ignore_permissions=True)
	return restaurant_name


def ensure_test_room(run_id, branch):
	room_name = code(run_id, "ROOM")
	if frappe.db.exists("NDS Room", room_name):
		return room_name
	frappe.get_doc(
		{
			"doctype": "NDS Room",
			"name": room_name,
			"branch": branch,
			"room_type": "Indoor",
		}
	).insert(ignore_permissions=True)
	return room_name


def ensure_test_table(run_id, restaurant, branch, room):
	table_name = code(run_id, "TBL")
	if frappe.db.exists("NDS Table", table_name):
		return table_name
	frappe.get_doc(
		{
			"doctype": "NDS Table",
			"name": table_name,
			"restaurant": restaurant,
			"restaurant_room": room,
			"branch": branch,
			"no_of_seats": 4,
			"minimum_seating": 1,
			"table_shape": "Square",
			"is_take_away": 0,
		}
	).insert(ignore_permissions=True)
	return table_name


def ensure_test_production_unit(run_id, pos_profile, warehouse):
	unit_name = code(run_id, "kitchen")
	if frappe.db.exists("NDS Production Unit", unit_name):
		return unit_name
	company = frappe.db.get_value("POS Profile", pos_profile, "company")
	branch = frappe.db.get_value("POS Profile", pos_profile, "custom_branch")
	frappe.get_doc(
		{
			"doctype": "NDS Production Unit",
			"name": unit_name,
			"pos_profile": pos_profile,
			"warehouse": warehouse or frappe.db.get_value("POS Profile", pos_profile, "warehouse"),
			"company": company,
			"branch": branch,
			"item_groups": [{"item_group": "Products"}],
		}
	).insert(ignore_permissions=True)
	return unit_name


def register_standard_isolated_fixture_cleanup(cls):
	"""Register teardown for NDSUT-* fixtures; call at the start of setUpClass."""

	def _cleanup():
		frappe.set_user("Administrator")
		run_id = getattr(cls, "run_id", None)
		if not run_id:
			return

		invoice_name = getattr(cls, "invoice_name", None)
		if invoice_name:
			cleanup_invoice_and_kots(invoice_name)

		recipe_name = getattr(cls, "recipe_name", None)
		if recipe_name:
			delete_if_exists("NDS Recipe", recipe_name)

		production_unit_name = getattr(cls, "production_unit_name", None)
		if production_unit_name:
			delete_if_exists("NDS Production Unit", production_unit_name)

		table_name = getattr(cls, "table_name", None)
		if table_name:
			delete_if_exists("NDS Table", table_name)

		restaurant_name = getattr(cls, "restaurant_name", None)
		if restaurant_name and is_test_fixture_name(restaurant_name):
			delete_orphan_menu_for_room_rows(restaurant_name)
			room_name = getattr(cls, "room_name", None)
			if room_name and is_test_fixture_name(room_name):
				delete_if_exists("NDS Room", room_name)

		profile_name = code(run_id, "POS")
		cancel_opening_entries_for_profile(profile_name)
		cleanup_test_pos_cashier()
		cleanup_test_pos_captain()
		cleanup_test_pos_manager()
		cleanup_test_nds_only_cashier()
		delete_if_exists("POS Profile", profile_name)
		delete_if_exists("NDS Restaurant", restaurant_name)

		menu_names = []
		for attr in (
			"menu_name",
			"menu_default",
			"menu_room",
			"menu_ot",
			"menu_disabled",
			"menu_vip",
		):
			menu = getattr(cls, attr, None)
			if menu:
				menu_names.append(menu)
		delete_menus(menu_names)

		vip_price_list = getattr(cls, "vip_price_list", None)
		if vip_price_list and is_test_fixture_name(vip_price_list):
			delete_if_exists("Price List", vip_price_list)

		branch_name = getattr(cls, "branch", None)
		if branch_name and is_test_fixture_name(branch_name):
			delete_if_exists("Branch", branch_name)

		delete_items(list(getattr(cls, "item_codes", None) or []))

	cls.addClassCleanup(_cleanup)


def ensure_test_pos_profile(run_id, restaurant):
	"""POS Profile linked only to the test restaurant (cloned from an existing profile)."""
	profile_name = code(run_id, "POS")
	if frappe.db.exists("POS Profile", profile_name):
		return profile_name

	template = get_pos_profile_with_restaurant()
	if not template:
		return None

	src = frappe.get_doc("POS Profile", template)
	doc = frappe.copy_doc(src)
	doc.custom_restaurant = restaurant
	if doc.meta.has_field("custom_branch"):
		doc.custom_branch = frappe.db.get_value("NDS Restaurant", restaurant, "branch")
	if doc.meta.has_field("disabled"):
		doc.disabled = 0
	doc.name = profile_name
	for fieldname in ("pos_profile", "profile_name"):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, profile_name)
	if frappe.db.exists("POS Profile", profile_name):
		add_user_to_pos_profile(profile_name, ensure_test_pos_cashier())
		return profile_name
	try:
		_prune_invalid_pos_profile_payments(doc)
		doc.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		return profile_name
	add_user_to_pos_profile(doc.name, ensure_test_pos_cashier())
	return doc.name


def _prune_invalid_pos_profile_payments(profile_doc):
	"""Drop payment rows that would fail POS Profile / opening entry account validation."""
	company = profile_doc.company
	if not company or not profile_doc.get("payments"):
		return
	valid_rows = []
	for row in profile_doc.payments:
		if _mode_of_payment_company_account(row.mode_of_payment, company):
			valid_rows.append(row)
	if not valid_rows:
		return
	if not any(row.default for row in valid_rows):
		valid_rows[0].default = 1
	profile_doc.set("payments", valid_rows)


def ensure_test_nds_only_cashier(roles=None):
	"""Cashier with only NDS Cashier role for permission regression tests."""
	email = TEST_NDS_ONLY_CASHIER_EMAIL
	roles = roles or TEST_NDS_ONLY_CASHIER_ROLES
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NDS Test",
				"last_name": "Role Cashier",
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)

	existing_roles = {row.role for row in user.roles}
	roles_changed = False
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
			roles_changed = True
	if roles_changed:
		user.save(ignore_permissions=True)
	return email


def cleanup_test_nds_only_cashier():
	email = TEST_NDS_ONLY_CASHIER_EMAIL
	for entry in frappe.get_all(
		"POS Opening Entry",
		filters={"user": email, "status": "Open"},
		pluck="name",
	):
		_restore_pos_opening_entry(entry, None, created=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def ensure_test_pos_manager(roles=None):
	"""Isolated NDS Manager for takeover tests (never use site Administrator)."""
	email = TEST_POS_MANAGER_EMAIL
	roles = roles or TEST_POS_MANAGER_ROLES
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NDS Test",
				"last_name": "Manager",
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)

	existing_roles = {row.role for row in user.roles}
	roles_changed = False
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
			roles_changed = True
	if roles_changed:
		user.save(ignore_permissions=True)
	return email


def cleanup_test_pos_manager():
	email = TEST_POS_MANAGER_EMAIL
	for entry in frappe.get_all(
		"POS Opening Entry",
		filters={"user": email, "status": "Open"},
		pluck="name",
	):
		profile = frappe.db.get_value("POS Opening Entry", entry, "pos_profile")
		if profile and is_test_fixture_name(profile):
			_restore_pos_opening_entry(entry, None, created=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def ensure_test_pos_captain(roles=None):
	"""Captain-only user for permission regression tests."""
	email = TEST_POS_CAPTAIN_EMAIL
	roles = roles or TEST_POS_CAPTAIN_ROLES
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NDS Test",
				"last_name": "Captain",
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)

	existing_roles = {row.role for row in user.roles}
	roles_changed = False
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
			roles_changed = True
	if roles_changed:
		user.save(ignore_permissions=True)
	return email


def ensure_test_pos_cashier(roles=None):
	"""Dedicated POS cashier so tests never open a second shift for Administrator."""
	email = TEST_POS_CASHIER_EMAIL
	roles = roles or TEST_POS_CASHIER_ROLES
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NDS Test",
				"last_name": "Cashier",
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)

	existing_roles = {row.role for row in user.roles}
	roles_changed = False
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
			roles_changed = True
	if roles_changed:
		user.save(ignore_permissions=True)
	return email


def add_user_to_pos_profile(pos_profile, user_email):
	profile = frappe.get_doc("POS Profile", pos_profile)
	users = {row.user for row in (profile.get("applicable_for_users") or [])}
	if user_email in users:
		return
	profile.append("applicable_for_users", {"user": user_email})
	profile.save(ignore_permissions=True)


def add_user_to_test_branch(branch, user_email, room=None):
	"""P4-T6: seat a user on an isolated NDSUT branch (never touches real branches)."""
	if not branch or not is_test_fixture_name(branch) or not frappe.db.exists("Branch", branch):
		return
	if not frappe.get_meta("Branch").has_field("nds_users"):
		return
	doc = frappe.get_doc("Branch", branch)
	for row in doc.get("nds_users") or []:
		if row.user == user_email and (row.room or None) == (room or None):
			return
	doc.append("nds_users", {"user": user_email, "room": room})
	doc.save(ignore_permissions=True)


def remove_user_from_test_branch(branch, user_email):
	if not branch or not is_test_fixture_name(branch) or not frappe.db.exists("Branch", branch):
		return
	if not frappe.get_meta("Branch").has_field("nds_users"):
		return
	doc = frappe.get_doc("Branch", branch)
	rows = [r for r in (doc.get("nds_users") or []) if r.user != user_email]
	if len(rows) != len(doc.get("nds_users") or []):
		doc.set("nds_users", rows)
		doc.save(ignore_permissions=True)


def begin_test_pos_cashier_session(pos_profile, register_cleanup=None, user=None):
	"""Act as the test cashier (or provided user) with an open shift on the test POS Profile."""
	cashier = user or ensure_test_pos_cashier()
	add_user_to_pos_profile(pos_profile, cashier)
	if is_test_fixture_name(pos_profile):
		add_user_to_test_branch(frappe.db.get_value("POS Profile", pos_profile, "custom_branch"), cashier)
	frappe.set_user(cashier)
	ensure_pos_opening_entry(pos_profile, user=cashier, register_cleanup=register_cleanup)
	return cashier


def end_test_pos_cashier_session():
	frappe.set_user("Administrator")


def switch_test_pos_operator_session(pos_profile, user, register_cleanup=None):
	"""Close open shifts on the isolated test profile only, then open a shift for `user`."""
	if not is_test_fixture_name(pos_profile):
		raise ValueError(f"Refusing to modify POS shifts on non-test profile: {pos_profile}")
	cancel_opening_entries_for_profile(pos_profile)
	frappe.set_user("Administrator")
	return begin_test_pos_cashier_session(
		pos_profile, user=user, register_cleanup=register_cleanup
	)


def _mode_of_payment_company_account(mode_of_payment, company):
	if not mode_of_payment or not company:
		return None
	return frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
		"default_account",
	)


def _modes_of_payment_for_pos_opening(pos_profile, company):
	"""Modes with a company account, preferring the POS Profile payment table."""
	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	payment_rows = sorted(
		profile.get("payments") or [],
		key=lambda row: (0 if row.default else 1, row.idx or 0),
	)
	modes = []
	seen = set()
	for row in payment_rows:
		mop = row.mode_of_payment
		if not mop or mop in seen:
			continue
		if _mode_of_payment_company_account(mop, company):
			modes.append(mop)
			seen.add(mop)
	if modes:
		return modes

	for mop in frappe.get_all(
		"Mode of Payment Account",
		filters={"company": company, "default_account": ["is", "set"]},
		pluck="parent",
		order_by="parent asc",
	):
		if mop and mop not in seen and _mode_of_payment_company_account(mop, company):
			return [mop]

	if frappe.db.exists("Mode of Payment", "Cash"):
		return ["Cash"]
	return ["Cash"]


def _opening_balance_details_for_profile(pos_profile, company):
	modes = _modes_of_payment_for_pos_opening(pos_profile, company)
	return [{"mode_of_payment": mop, "opening_amount": 0} for mop in modes]


def cleanup_test_pos_captain():
	email = TEST_POS_CAPTAIN_EMAIL
	for entry in frappe.get_all(
		"POS Opening Entry",
		filters={"user": email, "status": "Open"},
		pluck="name",
	):
		_restore_pos_opening_entry(entry, None, created=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def cleanup_test_pos_cashier():
	"""Cancel test-cashier shifts and remove the fixture user (idempotent)."""
	email = TEST_POS_CASHIER_EMAIL
	for entry in frappe.get_all(
		"POS Opening Entry",
		filters={"user": email, "status": "Open"},
		pluck="name",
	):
		_restore_pos_opening_entry(entry, None, created=True)
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def ensure_pos_opening_entry(pos_profile, user=None, register_cleanup=None):
	"""Create or reuse an open POS Opening Entry for today.

	When reusing an existing open entry, original dates are restored via register_cleanup
	(e.g. unittest.TestCase.addCleanup) so shared-site shifts are not left altered.
	"""
	user = user or frappe.session.user
	company = frappe.db.get_value("POS Profile", pos_profile, "company")
	posting_date = today()

	existing = frappe.db.get_value(
		"POS Opening Entry",
		{"user": user, "pos_profile": pos_profile, "status": "Open", "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if existing:
		snapshot = frappe.db.get_value(
			"POS Opening Entry",
			existing,
			["period_start_date", "posting_date"],
			as_dict=True,
		)
		frappe.db.set_value(
			"POS Opening Entry",
			existing,
			{"period_start_date": posting_date, "posting_date": posting_date},
			update_modified=True,
		)
		if register_cleanup and snapshot:
			register_cleanup(_restore_pos_opening_entry, existing, snapshot, created=False)
		return existing

	if not company:
		company = frappe.db.get_value("POS Profile", pos_profile, "company")

	doc = frappe.get_doc(
		{
			"doctype": "POS Opening Entry",
			"period_start_date": posting_date,
			"period_end_date": posting_date,
			"posting_date": posting_date,
			"user": user,
			"pos_profile": pos_profile,
			"company": company,
			"balance_details": _opening_balance_details_for_profile(pos_profile, company),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	if register_cleanup:
		register_cleanup(_restore_pos_opening_entry, doc.name, None, created=True)
	return doc.name


def cancel_opening_entries_for_profile(pos_profile):
	"""Remove open shifts created for an isolated test POS Profile."""
	for entry in frappe.get_all(
		"POS Opening Entry",
		filters={"pos_profile": pos_profile, "status": "Open"},
		pluck="name",
	):
		_restore_pos_opening_entry(entry, None, created=True)


def _restore_pos_opening_entry(entry_name, date_snapshot, created=False):
	if not entry_name or not frappe.db.exists("POS Opening Entry", entry_name):
		return
	if created:
		doc = frappe.get_doc("POS Opening Entry", entry_name)
		if doc.docstatus == 1 and doc.status == "Open":
			doc.cancel()
		frappe.delete_doc("POS Opening Entry", entry_name, force=True, ignore_permissions=True)
		return
	if date_snapshot:
		frappe.db.set_value(
			"POS Opening Entry",
			entry_name,
			{
				"period_start_date": date_snapshot.period_start_date,
				"posting_date": date_snapshot.posting_date,
			},
			update_modified=True,
		)


def ensure_bin_qty(item_code, warehouse, qty):
	if not warehouse:
		return
	bin_name = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "name")
	if bin_name:
		frappe.db.set_value("Bin", bin_name, "actual_qty", qty, update_modified=False)
	else:
		frappe.get_doc(
			{
				"doctype": "Bin",
				"item_code": item_code,
				"warehouse": warehouse,
				"actual_qty": qty,
			}
		).insert(ignore_permissions=True)


def delete_if_exists(doctype, name):
	if name and frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def delete_items(item_codes):
	for item_code in item_codes:
		delete_if_exists("Item", item_code)


def delete_menus(menu_names):
	for menu_name in menu_names:
		if not menu_name:
			continue
		pl_name = frappe.db.get_value("NDS Menu", menu_name, "price_list")
		delete_if_exists("NDS Menu", menu_name)
		delete_if_exists("Price List", pl_name)


def delete_orphan_menu_for_room_rows(parent, parenttype="NDS Menu", parentfield="menu_for_room"):
	"""Remove child rows left by tests that insert invalid parenttype on purpose."""
	for row in frappe.get_all(
		"NDS Menu For Room",
		filters={"parent": parent, "parenttype": parenttype, "parentfield": parentfield},
		pluck="name",
	):
		frappe.delete_doc("NDS Menu For Room", row, force=True, ignore_permissions=True)


@contextmanager
def ignore_item_menu_link_validation():
	"""Skip Item validate hook while building fixtures that intentionally violate menu rules."""
	with patch("nds_restaurant.api.items.validate_item_links"):
		yield


@contextmanager
def ignore_menu_variant_validation():
	"""Skip NDS Menu variant/add-on validation while building legacy text fixtures."""
	from nds_restaurant.nds_restaurant.doctype.nds_menu.nds_menu import NDSMenu

	with patch.object(NDSMenu, "validate_variants_and_addons", lambda self: None):
		yield


def set_menu_item_variants_text(menu_doc, row_index, variants_text):
	"""Update deprecated variants text without running full menu validation."""
	row = menu_doc.items[row_index]
	frappe.db.set_value(
		"NDS Menu Item",
		row.name,
		"variants",
		variants_text,
		update_modified=False,
	)
	menu_doc.reload()


def cancel_and_delete_kot(kot_name):
	if not kot_name or not frappe.db.exists("NDS KOT", kot_name):
		return
	kot = frappe.get_doc("NDS KOT", kot_name)
	if kot.docstatus == 1:
		kot.cancel()
	frappe.delete_doc("NDS KOT", kot_name, force=True, ignore_permissions=True)


def cancel_and_delete_pos_invoice(invoice_name):
	if not invoice_name or not frappe.db.exists("POS Invoice", invoice_name):
		return
	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus == 1:
		invoice.cancel()
	elif invoice.docstatus == 0:
		frappe.delete_doc("POS Invoice", invoice_name, force=True, ignore_permissions=True)
		return
	frappe.delete_doc("POS Invoice", invoice_name, force=True, ignore_permissions=True)


def cleanup_invoice_and_kots(invoice_name):
	for kot_name in frappe.get_all(
		"NDS KOT", filters={"pos_invoice": invoice_name}, pluck="name"
	):
		cancel_and_delete_kot(kot_name)
	cancel_and_delete_pos_invoice(invoice_name)


def as_frappe_rows(rows):
	"""Wrap dict rows like frappe.get_all returns for attribute access in app code."""
	return [frappe._dict(row) for row in rows]
