# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P4: capabilities, billing role, table restriction, captain transfer / move / merge, sent-item
lock, branch user list and KDS access (isolated NDSUT fixtures only)."""

import json
import unittest

import frappe

from nds_restaurant.api import kot as kot_api
from nds_restaurant.api.pos import (
	cancel_order,
	captain_transfer,
	change_order_type,
	create_or_update_order,
	get_invoice,
	get_orders,
	get_pos_context,
	get_transfer_options,
	mark_invoice_printed,
	merge_orders,
	settle_takeaway,
	submit_payment,
)
from nds_restaurant.install import create_roles, ensure_pos_operator_permissions
from nds_restaurant.tests.test_helpers import (
	add_user_to_pos_profile,
	add_user_to_test_branch,
	cleanup_invoice_and_kots,
	code,
	delete_if_exists,
	ensure_pos_opening_entry,
	ensure_test_branch,
	ensure_test_menu,
	ensure_test_nds_only_cashier,
	ensure_test_pos_captain,
	ensure_test_pos_manager,
	ensure_test_pos_profile,
	ensure_test_price_list,
	ensure_test_production_unit,
	ensure_test_restaurant,
	ensure_test_room,
	ensure_test_table,
	new_test_run_id,
	register_standard_isolated_fixture_cleanup,
	remove_user_from_test_branch,
)

CAPTAIN_B = "nds-test-captain-b@example.com"
KITCHEN_USER = "nds-test-kitchen@example.com"
NO_ROLE_USER = "nds-test-norole@example.com"


def _ensure_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "NDS Test",
				"last_name": email.split("@")[0],
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	have = {r.role for r in user.roles}
	missing = [r for r in roles if r not in have]
	if missing:
		for role in missing:
			user.append("roles", {"role": role})
		user.save(ignore_permissions=True)
	return email


def _delete_user(email):
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)


def _create_item(cls, suffix):
	item_code = code(cls.run_id, suffix)
	cls.item_codes.append(item_code)
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return item_code


class P4Base(unittest.TestCase):
	"""Two standard tables, one VIP table (different menu and rates), a kitchen and five users."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.pos_profile = None
		cls.extra_tables = []
		cls.vip_room = None
		register_standard_isolated_fixture_cleanup(cls)
		cls.addClassCleanup(cls._cleanup_extras)

		frappe.set_user("Administrator")
		create_roles()
		ensure_pos_operator_permissions()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		cls.item_a = _create_item(cls, "p4-a")
		cls.item_b = _create_item(cls, "p4-b")
		cls.menu_name = ensure_test_menu(
			cls.run_id, cls.branch, [(cls.item_a, 40), (cls.item_b, 15)], menu_name=code(cls.run_id, "p4-menu")
		)
		cls.vip_price_list = ensure_test_price_list(cls.run_id, cls.company)
		cls.menu_vip = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item_a, 60)],
			menu_name=code(cls.run_id, "p4-vip-menu"),
			price_list=cls.vip_price_list,
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id, cls.branch, cls.company, active_menu=cls.menu_name, room_wise_menu=1
		)
		cls.room_name = ensure_test_room(cls.run_id, cls.branch)
		cls.vip_room = code(cls.run_id, "VIP-ROOM")
		if not frappe.db.exists("NDS Room", cls.vip_room):
			frappe.get_doc(
				{"doctype": "NDS Room", "name": cls.vip_room, "branch": cls.branch, "room_type": "Indoor"}
			).insert(ignore_permissions=True)
		rest = frappe.get_doc("NDS Restaurant", cls.restaurant_name)
		if rest.meta.has_field("room_wise_menu"):
			rest.room_wise_menu = 1
		if rest.meta.has_field("menu_for_room"):
			rest.set("menu_for_room", [{"room": cls.vip_room, "menu": cls.menu_vip}])
		rest.save(ignore_permissions=True)

		cls.table_name = ensure_test_table(cls.run_id, cls.restaurant_name, cls.branch, cls.room_name)
		cls.t1 = cls.table_name
		cls.t2 = cls._extra_table("TBL2", cls.room_name)
		cls.t3 = cls._extra_table("VIP-TBL", cls.vip_room)

		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		cls.warehouse = frappe.db.get_value("POS Profile", cls.pos_profile, "warehouse")
		cls.production_unit_name = ensure_test_production_unit(cls.run_id, cls.pos_profile, cls.warehouse)
		values = {}
		meta = frappe.get_meta("POS Profile")
		for field, value in (
			("custom_enable_multiple_cashier", 1),
			("custom_view_all_status", 0),
			("custom_paid_limit", 20),
			("custom_remove_items", 0),
			("custom_edit_order_type", 1),
		):
			if meta.has_field(field):
				values[field] = value
		frappe.db.set_value("POS Profile", cls.pos_profile, values)
		frappe.clear_document_cache("POS Profile", cls.pos_profile)

		cls.captain_a = ensure_test_pos_captain()
		cls.captain_b = _ensure_user(CAPTAIN_B, ["NDS Captain"])
		cls.cashier = ensure_test_nds_only_cashier()
		cls.manager = ensure_test_pos_manager()
		cls.kitchen = _ensure_user(KITCHEN_USER, ["NDS Kitchen"])
		cls.no_role = _ensure_user(NO_ROLE_USER, [])
		for user in (cls.captain_a, cls.captain_b, cls.cashier, cls.manager):
			add_user_to_pos_profile(cls.pos_profile, user)
			add_user_to_test_branch(cls.branch, user)

	@classmethod
	def _extra_table(cls, suffix, room):
		name = code(cls.run_id, suffix)
		if not frappe.db.exists("NDS Table", name):
			frappe.get_doc(
				{
					"doctype": "NDS Table",
					"name": name,
					"restaurant": cls.restaurant_name,
					"restaurant_room": room,
					"branch": cls.branch,
					"no_of_seats": 4,
					"minimum_seating": 1,
					"table_shape": "Square",
					"is_take_away": 0,
				}
			).insert(ignore_permissions=True)
		cls.extra_tables.append(name)
		return name

	@classmethod
	def _cleanup_extras(cls):
		frappe.set_user("Administrator")
		for name in getattr(cls, "extra_tables", []):
			delete_if_exists("NDS Table", name)
		if getattr(cls, "vip_room", None):
			delete_if_exists("NDS Room", cls.vip_room)
		for email in (CAPTAIN_B, KITCHEN_USER, NO_ROLE_USER):
			_delete_user(email)

	def setUp(self):
		if not self.pos_profile:
			self.skipTest("No POS Profile")
		if not frappe.get_meta("POS Invoice").has_field("custom_captain"):
			self.skipTest("custom_captain not migrated")
		frappe.set_user("Administrator")
		self.created_invoices = []
		self._reset_tables()
		self._set_roles("custom_role_allowed_for_billing", [])
		self._set_roles("custom_transfer_role_permissions", [])
		self._set_roles("custom_role_restricted_for_table_order", [])
		self._set_profile("custom_remove_items", 0)
		ensure_pos_opening_entry(self.pos_profile, user=self.cashier, register_cleanup=self.addCleanup)

	def tearDown(self):
		frappe.set_user("Administrator")
		for inv in self.created_invoices:
			cleanup_invoice_and_kots(inv)
		self._reset_tables()
		self._set_roles("custom_role_allowed_for_billing", [])
		self._set_roles("custom_transfer_role_permissions", [])
		self._set_roles("custom_role_restricted_for_table_order", [])
		self._set_profile("custom_remove_items", 0)

	# helpers -------------------------------------------------------------
	def _reset_tables(self):
		for t in (self.t1, self.t2, self.t3):
			frappe.db.set_value("NDS Table", t, {"occupied": 0, "current_invoice": None})

	def _set_roles(self, fieldname, roles):
		if not frappe.get_meta("POS Profile").has_field(fieldname):
			return
		current = frappe.session.user
		frappe.set_user("Administrator")
		doc = frappe.get_doc("POS Profile", self.pos_profile)
		doc.set(fieldname, [{"role": r} for r in roles])
		doc.save(ignore_permissions=True)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		frappe.set_user(current)

	def _set_profile(self, fieldname, value):
		if frappe.get_meta("POS Profile").has_field(fieldname):
			frappe.db.set_value("POS Profile", self.pos_profile, fieldname, value)
			frappe.clear_document_cache("POS Profile", self.pos_profile)

	def _as(self, user):
		frappe.set_user(user)
		return user

	def _order(self, table=None, items=None, invoice=None, generate_kot=0):
		items = items or [{"item_code": self.item_a, "qty": 1}]
		res = create_or_update_order(
			pos_profile=self.pos_profile,
			items=items,
			table=table,
			order_type="Dine In" if table else "Take Away",
			invoice=invoice,
			generate_kot=generate_kot,
		)
		if res["invoice"] not in self.created_invoices:
			self.created_invoices.append(res["invoice"])
		return res

	def _pay(self, invoice):
		doc = frappe.get_doc("POS Invoice", invoice)
		return submit_payment(
			invoice,
			json.dumps([{"mode_of_payment": "Cash", "amount": doc.rounded_total or doc.grand_total}]),
		)

	def _table(self, table):
		return frappe.db.get_value("NDS Table", table, ["occupied", "current_invoice"], as_dict=True)

	def _kots(self, invoice):
		return frappe.get_all(
			"NDS KOT",
			filters={"pos_invoice": invoice, "docstatus": 1},
			fields=["name", "kot_type", "table", "comments"],
			order_by="creation asc",
		)


class TestP4Capabilities(P4Base):
	def test_captain_cannot_bill_until_role_is_allowed(self):
		self._as(self.captain_a)
		ctx = get_pos_context(self.pos_profile)
		self.assertEqual(ctx["capabilities"]["can_bill"], 0)
		self.assertEqual(ctx["settings"]["tabs"], ["Draft", "Unbilled"])
		with self.assertRaises(frappe.PermissionError):
			get_orders(self.pos_profile, status="Recently Paid")

		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_captain"), self.captain_a)
		self.assertTrue(self._kots(inv))
		self.assertEqual(get_invoice(inv)["can_pay"], 0)
		mark_invoice_printed(inv)
		with self.assertRaises(frappe.PermissionError) as cm:
			self._pay(inv)
		self.assertIn("Not permitted to bill", str(cm.exception))

		self._set_roles("custom_role_allowed_for_billing", ["NDS Captain"])
		self.assertEqual(get_pos_context(self.pos_profile)["capabilities"]["can_bill"], 1)

	def test_cashier_pays_captain_order(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		self._as(self.cashier)
		self.assertEqual(get_pos_context(self.pos_profile)["capabilities"]["can_bill"], 1)
		mark_invoice_printed(inv)
		self.assertEqual(self._pay(inv)["invoice"], inv)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "docstatus"), 1)
		self.assertFalse(self._table(self.t1).current_invoice)

	def test_billing_table_replaces_default_roles(self):
		self._set_roles("custom_role_allowed_for_billing", ["NDS Captain"])
		self._as(self.cashier)
		self.assertEqual(get_pos_context(self.pos_profile)["capabilities"]["can_bill"], 0)
		self._as(self.manager)
		self.assertEqual(get_pos_context(self.pos_profile)["capabilities"]["can_bill"], 1)

	def test_settle_takeaway_and_order_type_change_need_billing(self):
		self._as(self.captain_a)
		before = frappe.db.count("POS Invoice", {"pos_profile": self.pos_profile})
		with self.assertRaises(frappe.PermissionError):
			settle_takeaway(self.pos_profile, json.dumps([{"item_code": self.item_a, "qty": 1}]))
		self.assertEqual(frappe.db.count("POS Invoice", {"pos_profile": self.pos_profile}), before)

		inv = self._order(table=self.t1)["invoice"]
		with self.assertRaises(frappe.PermissionError):
			change_order_type(inv, "Take Away")

	def test_restricted_captain_sees_other_captains_table_locked(self):
		if not frappe.get_meta("POS Profile").has_field("custom_role_restricted_for_table_order"):
			self.skipTest("restricted role table not migrated")
		self._set_roles("custom_role_restricted_for_table_order", ["NDS Captain"])
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		row = next(t for t in get_pos_context(self.pos_profile)["tables"] if t.name == self.t1)
		self.assertEqual(row["locked"], 0)

		self._as(self.captain_b)
		ctx = get_pos_context(self.pos_profile)
		row = next(t for t in ctx["tables"] if t.name == self.t1)
		self.assertEqual(row["locked"], 1)
		self.assertEqual(row["captain"], self.captain_a)
		free = next(t for t in ctx["tables"] if t.name == self.t2)
		self.assertEqual(free["locked"], 0)
		with self.assertRaises(frappe.PermissionError) as cm:
			self._order(table=self.t1)
		self.assertIn("belongs to", str(cm.exception))
		with self.assertRaises(frappe.PermissionError):
			get_invoice(inv)

		self._as(self.manager)
		res = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 2}])
		self.assertEqual(res["invoice"], inv)

		self._set_roles("custom_transfer_role_permissions", ["NDS Captain"])
		self._as(self.captain_b)
		row = next(t for t in get_pos_context(self.pos_profile)["tables"] if t.name == self.t1)
		self.assertEqual(row["locked"], 0)

	def test_branch_user_list_is_enforced(self):
		remove_user_from_test_branch(self.branch, self.cashier)
		try:
			self._as(self.cashier)
			with self.assertRaises(frappe.PermissionError) as cm:
				get_pos_context(self.pos_profile)
			self.assertIn("not assigned to branch", str(cm.exception))
			self._as(self.manager)
			remove_user_from_test_branch(self.branch, self.manager)
			self.assertTrue(get_pos_context(self.pos_profile)["capabilities"]["is_manager"])
		finally:
			frappe.set_user("Administrator")
			add_user_to_test_branch(self.branch, self.cashier)
			add_user_to_test_branch(self.branch, self.manager)
		self._as(self.cashier)
		self.assertEqual(get_pos_context(self.pos_profile)["pos_profile"], self.pos_profile)

	def test_sent_items_locked_unless_remove_items(self):
		self._as(self.cashier)
		first = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 2}], generate_kot=1)
		inv = first["invoice"]
		self.assertEqual([(s["item_code"], s["qty"]) for s in first["sent_items"]], [(self.item_a, 2)])
		with self.assertRaises(frappe.ValidationError) as cm:
			self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)
		self.assertIn("already sent to kitchen", str(cm.exception))
		# Adding items stays allowed.
		self._order(
			table=self.t1,
			invoice=inv,
			items=[{"item_code": self.item_a, "qty": 2}, {"item_code": self.item_b, "qty": 1}],
			generate_kot=1,
		)

		self._set_profile("custom_remove_items", 1)
		res = self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)
		kots = self._kots(inv)
		self.assertIn(kots[-1].kot_type, ("Partially Cancelled", "Modified"))
		self.assertEqual(
			sorted((s["item_code"], s["qty"]) for s in res["sent_items"]), [(self.item_a, 1)]
		)
		# Re-sending the unchanged order must not repeat the cancellation.
		self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)
		self.assertEqual(len(self._kots(inv)), len(kots))

	def test_manager_may_reduce_sent_items(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 3}], generate_kot=1)["invoice"]
		self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)
		kots = self._kots(inv)
		self.assertEqual(kots[-1].kot_type, "Partially Cancelled")
		self.assertEqual(kot_api.sent_quantities(inv), {(self.item_a, "", ""): 1})


class TestP4Transfer(P4Base):
	def test_transfer_requires_role(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		self.assertEqual(get_invoice(inv)["can_transfer"], 0)
		with self.assertRaises(frappe.PermissionError):
			captain_transfer(inv, to_table=self.t2)
		with self.assertRaises(frappe.PermissionError):
			get_transfer_options(inv)
		self.assertEqual(self._table(self.t1).current_invoice, inv)

	def test_manager_hands_order_to_another_captain(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]

		self._as(self.manager)
		opts = get_transfer_options(inv)
		self.assertIn(self.captain_b, [u["user"] for u in opts["users"]])
		self.assertIn(self.t2, [t["name"] for t in opts["tables"]])
		with self.assertRaises(frappe.ValidationError):
			captain_transfer(inv, to_user="nobody@example.com")
		res = captain_transfer(inv, to_user=self.captain_b)
		self.assertEqual(res["captain"], self.captain_b)
		self.assertEqual(res["table"], self.t1)

		self._as(self.captain_b)
		self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 2}])
		self.assertEqual(get_invoice(inv)["can_edit"], 1)
		self._as(self.captain_a)
		with self.assertRaises(frappe.ValidationError):
			self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 3}])

	def test_transfer_role_lets_a_captain_move_tables(self):
		self._set_roles("custom_transfer_role_permissions", ["NDS Captain"])
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		self.assertEqual(get_invoice(inv)["can_transfer"], 1)
		kot_names = [k.name for k in self._kots(inv)]

		res = captain_transfer(inv, to_table=self.t2)
		self.assertEqual(res["table"], self.t2)
		self.assertEqual(res["previous_table"], self.t1)
		self.assertEqual(res["repriced"], 0)
		self.assertFalse(self._table(self.t1).occupied)
		self.assertFalse(self._table(self.t1).current_invoice)
		self.assertEqual(self._table(self.t2).current_invoice, inv)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_nds_table"), self.t2)
		for name in kot_names:
			self.assertEqual(frappe.db.get_value("NDS KOT", name, "table"), self.t2)
		self.assertTrue(
			frappe.db.exists(
				"Comment", {"reference_doctype": "POS Invoice", "reference_name": inv, "comment_type": "Info"}
			)
		)
		# Sending again after the move doesn't resend the items.
		self._order(table=self.t2, invoice=inv, generate_kot=1)
		self.assertEqual(len(self._kots(inv)), len(kot_names))

	def test_move_to_vip_room_reprices_and_blocks_occupied_tables(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 2}])["invoice"]
		mark_invoice_printed(inv)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_invoice_printed"), 1)
		other = self._order(table=self.t2)["invoice"]

		with self.assertRaises(frappe.ValidationError) as cm:
			captain_transfer(inv, to_table=self.t2)
		self.assertIn("use Merge", str(cm.exception))
		self.assertEqual(self._table(self.t2).current_invoice, other)

		res = captain_transfer(inv, to_table=self.t3)
		self.assertEqual(res["repriced"], 1)
		doc = frappe.get_doc("POS Invoice", inv)
		self.assertEqual(doc.custom_nds_room, self.vip_room)
		self.assertEqual([row.rate for row in doc.items], [60])
		self.assertEqual(doc.selling_price_list, self.vip_price_list)
		self.assertEqual(doc.custom_invoice_printed, 0)

	def test_move_rejects_items_missing_from_new_menu(self):
		self._as(self.manager)
		inv = self._order(
			table=self.t1, items=[{"item_code": self.item_a, "qty": 1}, {"item_code": self.item_b, "qty": 1}]
		)["invoice"]
		with self.assertRaises(frappe.ValidationError) as cm:
			captain_transfer(inv, to_table=self.t3)
		self.assertIn(self.item_b, str(cm.exception))
		self.assertEqual(self._table(self.t1).current_invoice, inv)
		self.assertFalse(self._table(self.t3).occupied)

	def test_merge_keeps_kitchen_history_consistent(self):
		self._as(self.manager)
		target = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)["invoice"]
		source = self._order(table=self.t2, items=[{"item_code": self.item_a, "qty": 2}], generate_kot=1)["invoice"]
		source_kots = [k.name for k in self._kots(source)]
		# An unsent line on the source should reach the kitchen on the next send.
		self._order(
			table=self.t2,
			invoice=source,
			items=[{"item_code": self.item_a, "qty": 2}, {"item_code": self.item_b, "qty": 1}],
			generate_kot=0,
		)

		res = merge_orders(source, target)
		self.assertEqual(res["invoice"], target)
		self.assertEqual(res["merged_from"], source)
		self.assertFalse(frappe.db.exists("POS Invoice", source))
		self.assertFalse(self._table(self.t2).current_invoice)
		self.assertEqual(self._table(self.t1).current_invoice, target)

		doc = frappe.get_doc("POS Invoice", target)
		qty = {}
		for row in doc.items:
			qty[row.item_code] = qty.get(row.item_code, 0) + row.qty
		self.assertEqual(qty, {self.item_a: 3, self.item_b: 1})

		kots = self._kots(target)
		notice = kots[-1]
		self.assertIn(notice.kot_type, ("Transfer", "Modified"))
		self.assertIn("MERGED", notice.comments or "")
		self.assertEqual(kot_api.sent_quantities(target), {(self.item_a, "", ""): 3})
		for name in source_kots:
			self.assertEqual(frappe.db.get_value("NDS KOT", name, "table"), self.t1)
		# The kitchen can still serve a KOT whose draft was merged away (deleted).
		self.assertTrue(kot_api.serve_kot(source_kots[0])["ok"])
		self.assertEqual(frappe.db.get_value("NDS KOT", source_kots[0], "served"), 1)

		# Next send only carries the unsent source line.
		created = kot_api.kot_execute(target)
		self.assertEqual(len(created), 1)
		new_kot = frappe.get_doc("NDS KOT", created[0])
		added = {r.item: (r.qty, r.old_qty) for r in new_kot.items if r.qty != r.old_qty}
		self.assertEqual(added, {self.item_b: (1, 0)})

	def test_merge_requires_transfer_role(self):
		self._as(self.captain_a)
		a = self._order(table=self.t1)["invoice"]
		b = self._order(table=self.t2)["invoice"]
		with self.assertRaises(frappe.PermissionError):
			merge_orders(b, a)
		self.assertTrue(frappe.db.exists("POS Invoice", b))


class TestP4Kds(P4Base):
	def _cancel_kot(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		res = cancel_order(inv, reason="test")
		self.assertEqual(res["action"], "voided")
		self.assertTrue(res["kots"])
		return res["kots"][0]

	def test_kds_needs_nds_role_and_branch_seat(self):
		unit = self.production_unit_name
		self._as(self.no_role)
		with self.assertRaises(frappe.PermissionError):
			kot_api.get_kds_context(unit)
		self.assertEqual(kot_api.get_production_units(), [])

		frappe.set_user("Administrator")
		remove_user_from_test_branch(self.branch, self.kitchen)
		self._as(self.kitchen)
		with self.assertRaises(frappe.PermissionError):
			kot_api.get_kds_context(unit)
		self.assertNotIn(unit, [u.name for u in kot_api.get_production_units()])

		frappe.set_user("Administrator")
		add_user_to_test_branch(self.branch, self.kitchen)
		try:
			self._as(self.kitchen)
			ctx = kot_api.get_kds_context(unit)
			self.assertEqual(ctx["production_unit"], unit)
			self.assertEqual(ctx["can_verify"], 0)
			self.assertIn(unit, [u.name for u in kot_api.get_production_units()])
		finally:
			frappe.set_user("Administrator")
			remove_user_from_test_branch(self.branch, self.kitchen)

	def test_cancel_kot_needs_manager_verification(self):
		kot_name = self._cancel_kot()
		frappe.set_user("Administrator")
		add_user_to_test_branch(self.branch, self.kitchen)
		try:
			self._as(self.kitchen)
			self.assertIn(kot_name, [k.name for k in kot_api.get_kots(self.production_unit_name)])
			with self.assertRaises(frappe.PermissionError):
				kot_api.confirm_kot(kot_name)
			self._as(self.manager)
			self.assertEqual(kot_api.get_kds_context(self.production_unit_name)["can_verify"], 1)
			res = kot_api.confirm_kot(kot_name)
			self.assertTrue(res["ok"])
			kot = frappe.get_doc("NDS KOT", kot_name)
			self.assertEqual(kot.confirmed, 1)
			if kot.meta.has_field("verified_by"):
				self.assertEqual(kot.verified_by, self.manager)
			self.assertNotIn(kot_name, [k.name for k in kot_api.get_kots(self.production_unit_name)])
		finally:
			frappe.set_user("Administrator")
			remove_user_from_test_branch(self.branch, self.kitchen)
			cleanup_invoice_and_kots(frappe.db.get_value("NDS KOT", kot_name, "pos_invoice"))

	def test_kitchen_user_serves_kots(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot_name = self._kots(inv)[0].name
		frappe.set_user("Administrator")
		add_user_to_test_branch(self.branch, self.kitchen)
		try:
			self._as(self.kitchen)
			self.assertTrue(kot_api.serve_kot(kot_name)["ok"])
			self.assertEqual(frappe.db.get_value("NDS KOT", kot_name, "served"), 1)
		finally:
			frappe.set_user("Administrator")
			remove_user_from_test_branch(self.branch, self.kitchen)
