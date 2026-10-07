"""
Unit tests for dynamic menu resolution (_resolve_menu) and menu-based pricing.
"""

import frappe
import unittest
from frappe.utils import flt

from nds_restaurant.api.pos import _resolve_menu, create_or_update_order
from nds_restaurant.tests.test_helpers import (
	begin_test_pos_cashier_session,
	cleanup_invoice_and_kots,
	code,
	delete_orphan_menu_for_room_rows,
	end_test_pos_cashier_session,
	ensure_test_branch,
	ensure_test_menu,
	ensure_test_pos_profile,
	ensure_test_price_list,
	ensure_test_production_unit,
	ensure_test_restaurant,
	ensure_test_room,
	ensure_test_table,
	new_test_run_id,
	register_standard_isolated_fixture_cleanup,
)


class TestResolveMenu(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.branch = ensure_test_branch(cls.run_id)
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			raise unittest.SkipTest("No Company in site")

		cls.restaurant_name = code(cls.run_id, "REST")
		cls.room_name = code(cls.run_id, "ROOM")
		cls.menu_default = code(cls.run_id, "menu-def")
		cls.menu_room = code(cls.run_id, "menu-room")
		cls.menu_ot = code(cls.run_id, "menu-ot")
		cls.menu_disabled = code(cls.run_id, "menu-off")
		cls.item_codes = []
		register_standard_isolated_fixture_cleanup(cls)
		cls._build_fixtures()

	@classmethod
	def _create_item(cls, suffix):
		item_code = code(cls.run_id, suffix)
		cls.item_codes.append(item_code)
		if frappe.db.exists("Item", item_code):
			return item_code
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
		return item_code

	@classmethod
	def _create_menu(cls, name, items, enabled=1):
		if frappe.db.exists("NDS Menu", name):
			return name
		frappe.get_doc(
			{
				"doctype": "NDS Menu",
				"name": name,
				"branch": cls.branch,
				"enabled": enabled,
				"items": [{"item": item, "rate": rate} for item, rate in items],
			}
		).insert(ignore_permissions=True)
		return name

	@classmethod
	def _build_fixtures(cls):
		item_a = cls._create_item("item-a")
		item_b = cls._create_item("item-b")

		cls._create_menu(cls.menu_default, [(item_a, 10)], enabled=1)
		cls._create_menu(cls.menu_room, [(item_a, 20)], enabled=1)
		cls._create_menu(cls.menu_ot, [(item_a, 30)], enabled=1)
		cls._create_menu(cls.menu_disabled, [(item_a, 99)], enabled=0)

		if not frappe.db.exists("NDS Room", cls.room_name):
			frappe.get_doc(
				{
					"doctype": "NDS Room",
					"name": cls.room_name,
					"branch": cls.branch,
					"room_type": "Indoor",
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("NDS Restaurant", cls.restaurant_name):
			frappe.get_doc(
				{
					"doctype": "NDS Restaurant",
					"name": cls.restaurant_name,
					"company": cls.company,
					"branch": cls.branch,
					"invoice_series_prefix": "TST",
					"active_menu": cls.menu_default,
					"room_wise_menu": 1,
					"order_type_wise_menu": 1,
					"menu_for_room": [
						{"room": cls.room_name, "menu": cls.menu_room},
					],
					"order_type_menu": [
						{"order_type": "Delivery", "menu": cls.menu_ot},
					],
				}
			).insert(ignore_permissions=True)

	def setUp(self):
		frappe.set_user("Administrator")
		rest = frappe.get_doc("NDS Restaurant", self.restaurant_name)
		rest.active_menu = self.menu_default
		rest.room_wise_menu = 1
		rest.order_type_wise_menu = 1
		rest.save(ignore_permissions=True)

	def tearDown(self):
		delete_orphan_menu_for_room_rows(self.restaurant_name)

	def test_order_type_menu_when_flag_enabled(self):
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Delivery")
		self.assertEqual(menu, self.menu_ot)

	def test_room_menu_when_order_type_flag_off(self):
		rest = frappe.get_doc("NDS Restaurant", self.restaurant_name)
		rest.order_type_wise_menu = 0
		rest.save(ignore_permissions=True)
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Delivery")
		self.assertEqual(menu, self.menu_room)

	def test_room_menu_when_order_type_wise_off(self):
		rest = frappe.get_doc("NDS Restaurant", self.restaurant_name)
		rest.room_wise_menu = 1
		rest.order_type_wise_menu = 0
		rest.save(ignore_permissions=True)
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Dine In")
		self.assertEqual(menu, self.menu_room)

	def test_fallback_when_room_menu_disabled(self):
		frappe.db.set_value("NDS Menu", self.menu_room, "enabled", 0)
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Dine In")
		self.assertEqual(menu, self.menu_default)
		frappe.db.set_value("NDS Menu", self.menu_room, "enabled", 1)

	def test_parenttype_filter_ignores_orphan_child_row(self):
		frappe.get_doc(
			{
				"doctype": "NDS Menu For Room",
				"parent": self.restaurant_name,
				"parenttype": "NDS Menu",
				"parentfield": "menu_for_room",
				"room": self.room_name,
				"menu": self.menu_disabled,
			}
		).insert(ignore_permissions=True)
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Dine In")
		self.assertEqual(menu, self.menu_room)

	def test_active_menu_when_flags_off(self):
		rest = frappe.get_doc("NDS Restaurant", self.restaurant_name)
		rest.room_wise_menu = 0
		rest.order_type_wise_menu = 0
		rest.save(ignore_permissions=True)
		menu = _resolve_menu(self.restaurant_name, room=self.room_name, order_type="Delivery")
		self.assertEqual(menu, self.menu_default)


class TestMenuPricing(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.invoice_name = None
		cls.menu_name = None
		cls.restaurant_name = None
		register_standard_isolated_fixture_cleanup(cls)
		frappe.set_user("Administrator")
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		cls.item_code = cls._create_item("priced")
		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item_code, 42)],
			menu_name=code(cls.run_id, "price-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
			order_type_menus=[("Take Away", cls.menu_name)],
		)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)

	@classmethod
	def _create_item(cls, suffix):
		item_code = code(cls.run_id, suffix)
		cls.item_codes.append(item_code)
		if frappe.db.exists("Item", item_code):
			return item_code
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

	def setUp(self):
		if not self.pos_profile:
			self.skipTest("No POS Profile with restaurant")
		frappe.set_user("Administrator")
		begin_test_pos_cashier_session(self.pos_profile, register_cleanup=self.addCleanup)

	def tearDown(self):
		end_test_pos_cashier_session()

	def test_order_uses_menu_rate_not_client_rate(self):
		result = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 2, "rate": 5}],
			order_type="Take Away",
			generate_kot=0,
		)
		self.__class__.invoice_name = result.get("invoice")
		self.assertEqual(flt(result.get("grand_total")), 84.0)
		items = result.get("items") or []
		self.assertTrue(items)
		self.assertEqual(flt(items[0].get("rate")), 42.0)

	def test_rejects_item_not_on_menu(self):
		other_item = code(self.run_id, "other")
		self.item_codes.append(other_item)
		if not frappe.db.exists("Item", other_item):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": other_item,
					"item_name": other_item,
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			create_or_update_order(
				pos_profile=self.pos_profile,
				items=[{"item_code": other_item, "qty": 1}],
				order_type="Take Away",
				generate_kot=0,
			)


class TestVipRoomPriceList(unittest.TestCase):
	"""Room menu price list must survive set_missing_values on create and update."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.menu_name = None
		cls.menu_vip = None
		cls.restaurant_name = None
		cls.room_name = None
		cls.table_name = None
		register_standard_isolated_fixture_cleanup(cls)
		frappe.set_user("Administrator")
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		cls.item_code = code(cls.run_id, "vip-item")
		cls.item_codes.append(cls.item_code)
		if not frappe.db.exists("Item", cls.item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.item_code,
					"item_name": cls.item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		cls.vip_price_list = ensure_test_price_list(cls.run_id, cls.company)
		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item_code, 10)],
			menu_name=code(cls.run_id, "std-menu"),
		)
		cls.menu_vip = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item_code, 10)],
			menu_name=code(cls.run_id, "vip-menu"),
			price_list=cls.vip_price_list,
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
			room_wise_menu=1,
			room_menus=None,
		)
		cls.room_name = ensure_test_room(cls.run_id, cls.branch)
		rest = frappe.get_doc("NDS Restaurant", cls.restaurant_name)
		if rest.meta.has_field("room_wise_menu"):
			rest.room_wise_menu = 1
		if rest.meta.has_field("menu_for_room"):
			rest.set(
				"menu_for_room",
				[{"room": cls.room_name, "menu": cls.menu_vip}],
			)
		rest.save(ignore_permissions=True)
		cls.table_name = ensure_test_table(cls.run_id, cls.restaurant_name, cls.branch, cls.room_name)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)

	def setUp(self):
		if not getattr(self, "pos_profile", None):
			self.skipTest("No POS Profile")
		begin_test_pos_cashier_session(self.pos_profile, register_cleanup=self.addCleanup)
		self.invoice_name = None

	def tearDown(self):
		end_test_pos_cashier_session()
		if self.invoice_name:
			cleanup_invoice_and_kots(self.invoice_name)

	def test_vip_room_order_uses_menu_price_list_on_create_and_update(self):
		profile_pl = frappe.db.get_value("POS Profile", self.pos_profile, "selling_price_list")
		self.assertNotEqual(profile_pl, self.vip_price_list)

		created = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 10}],
			table=self.table_name,
			order_type="Dine In",
			generate_kot=0,
		)
		self.invoice_name = created["invoice"]
		self.assertEqual(
			frappe.db.get_value("POS Invoice", self.invoice_name, "selling_price_list"),
			self.vip_price_list,
		)

		updated = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 2, "rate": 10}],
			table=self.table_name,
			order_type="Dine In",
			invoice=self.invoice_name,
			generate_kot=0,
		)
		self.assertEqual(updated["invoice"], self.invoice_name)
		self.assertEqual(
			frappe.db.get_value("POS Invoice", self.invoice_name, "selling_price_list"),
			self.vip_price_list,
		)


class TestOrderModifiedAfterKot(unittest.TestCase):
	"""Returned modified must stay valid after kot_execute updates custom_kot_generated."""

	@classmethod
	def setUpClass(cls):
		cls.run_id = new_test_run_id()
		cls.item_codes = []
		cls.production_unit_name = None
		cls.menu_name = None
		cls.restaurant_name = None
		register_standard_isolated_fixture_cleanup(cls)
		frappe.set_user("Administrator")
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			return

		cls.branch = ensure_test_branch(cls.run_id)
		cls.item_code = code(cls.run_id, "kot-item")
		cls.item_codes.append(cls.item_code)
		if not frappe.db.exists("Item", cls.item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": cls.item_code,
					"item_name": cls.item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		cls.menu_name = ensure_test_menu(
			cls.run_id,
			cls.branch,
			[(cls.item_code, 10)],
			menu_name=code(cls.run_id, "kot-menu"),
		)
		cls.restaurant_name = ensure_test_restaurant(
			cls.run_id,
			cls.branch,
			cls.company,
			active_menu=cls.menu_name,
			order_type_menus=[("Take Away", cls.menu_name)],
		)
		cls.pos_profile = ensure_test_pos_profile(cls.run_id, cls.restaurant_name)
		if cls.pos_profile:
			warehouse = frappe.db.get_value("POS Profile", cls.pos_profile, "warehouse")
			cls.production_unit_name = ensure_test_production_unit(
				cls.run_id, cls.pos_profile, warehouse
			)

	def setUp(self):
		frappe.set_user("Administrator")
		self.created_invoices = []
		if not self.pos_profile:
			self.skipTest("No POS Profile with restaurant")
		begin_test_pos_cashier_session(self.pos_profile, register_cleanup=self.addCleanup)

	def tearDown(self):
		end_test_pos_cashier_session()
		for invoice_name in self.created_invoices:
			cleanup_invoice_and_kots(invoice_name)

	def test_two_consecutive_sends_with_returned_modified_succeed(self):
		first = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 1, "rate": 10}],
			order_type="Take Away",
			generate_kot=1,
		)
		invoice = first["invoice"]
		self.created_invoices.append(invoice)
		self.assertTrue(first.get("modified"))

		second = create_or_update_order(
			pos_profile=self.pos_profile,
			items=[{"item_code": self.item_code, "qty": 2, "rate": 10}],
			invoice=invoice,
			order_type="Take Away",
			generate_kot=1,
			expected_modified=first["modified"],
		)
		self.assertEqual(second["invoice"], invoice)
		self.assertEqual(flt(second.get("grand_total")), 20.0)
