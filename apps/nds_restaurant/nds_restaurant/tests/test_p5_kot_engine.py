# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P5a: KOT creation errors and warnings, CNCL naming with original_kot, delete-sends-cancel,
Served -> Picked Up lifecycle (and the P4 picked-up guard), KDS branch filter, serving priority and
the extra KOT header/item fields. Isolated NDSUT fixtures only."""

import frappe

from nds_restaurant.api import kot as kot_api
from nds_restaurant.api.pos import get_invoice, get_pos_context, merge_orders
from nds_restaurant.tests.test_helpers import add_user_to_test_branch, code, delete_if_exists, remove_user_from_test_branch
from nds_restaurant.tests.test_p4_roles import P4Base


def _needs(fields):
	meta = frappe.get_meta("NDS KOT")
	return all(meta.has_field(f) for f in fields)


class P5Base(P4Base):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.courses = []
		cls.extra_groups = []
		cls.extra_branches = []
		cls.addClassCleanup(cls._p5_cleanup)

	@classmethod
	def _p5_cleanup(cls):
		frappe.set_user("Administrator")
		for item in getattr(cls, "item_codes", []):
			if frappe.db.exists("Item", item):
				frappe.db.set_value("Item", item, "item_group", "Products")
		for name in getattr(cls, "courses", []):
			frappe.db.sql("update `tabNDS Menu Item` set course=null where course=%s", name)
			delete_if_exists("NDS Menu Course", name)
		for name in getattr(cls, "extra_groups", []):
			delete_if_exists("Item Group", name)
		for name in getattr(cls, "extra_branches", []):
			delete_if_exists("Branch", name)

	def setUp(self):
		super().setUp()
		if not _needs(["order_status", "original_kot", "branch", "customer_name", "production_time"]):
			self.skipTest("NDS KOT P1 fields not migrated")
		self._started = frappe.utils.now_datetime()

	def tearDown(self):
		super().tearDown()
		frappe.db.delete("Error Log", {"method": "KOT Creation Failed", "creation": (">=", self._started)})

	def _all_kots(self, invoice):
		return frappe.get_all(
			"NDS KOT",
			filters={"pos_invoice": invoice, "docstatus": 1},
			fields=["name", "kot_type", "original_kot", "order_status", "branch", "customer_name", "comments"],
			order_by="creation asc, name asc",
		)


class TestP5KotCreation(P5Base):
	def test_missing_production_unit_keeps_order_and_logs(self):
		frappe.db.set_value("NDS Production Unit", self.production_unit_name, "pos_profile", None)
		try:
			self._as(self.manager)
			res = self._order(table=self.t1, generate_kot=1)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("NDS Production Unit", self.production_unit_name, "pos_profile", self.pos_profile)
		self.assertTrue(frappe.db.exists("POS Invoice", res["invoice"]))
		self.assertIn("Create NDS Production unit against POS Profile", res["kot_error"])
		self.assertEqual(res["kots"], [])
		self.assertFalse(self._all_kots(res["invoice"]))
		self.assertTrue(
			frappe.db.exists("Error Log", {"method": "KOT Creation Failed", "creation": (">=", self._started)})
		)
		# The table is still occupied by the saved order.
		self.assertEqual(self._table(self.t1).current_invoice, res["invoice"])

	def test_unmapped_item_group_warns_and_sends_the_rest(self):
		group = code(self.run_id, "UNMAPPED")
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups", "is_group": 0}
			).insert(ignore_permissions=True)
		self.extra_groups.append(group)
		frappe.db.set_value("Item", self.item_b, "item_group", group)
		try:
			self._as(self.manager)
			res = self._order(
				table=self.t1,
				items=[{"item_code": self.item_a, "qty": 1}, {"item_code": self.item_b, "qty": 1}],
				generate_kot=1,
			)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("Item", self.item_b, "item_group", "Products")
		self.assertFalse(res["kot_error"])
		self.assertEqual(len(res["kot_warnings"]), 1)
		self.assertIn(self.item_b, res["kot_warnings"][0])
		self.assertIn("is not in any production", res["kot_warnings"][0])
		kot = frappe.get_doc("NDS KOT", res["kots"][0])
		self.assertEqual([r.item for r in kot.items], [self.item_a])

	def test_header_fields_branch_customer_and_status(self):
		self._as(self.manager)
		res = self._order(table=self.t1, generate_kot=1)
		kot = frappe.get_doc("NDS KOT", res["kots"][0])
		inv = frappe.get_doc("POS Invoice", res["invoice"])
		self.assertEqual(kot.order_status, "Ready For Prepare")
		self.assertEqual(kot.customer_name, inv.customer_name)
		self.assertEqual(kot.branch, frappe.db.get_value("POS Profile", self.pos_profile, "custom_branch"))


class TestP5Cancellation(P5Base):
	def test_partial_cancel_is_cncl_with_original_and_cancelled_qty(self):
		self._set_profile("custom_remove_items", 1)
		self._as(self.manager)
		inv = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 3}], generate_kot=1)["invoice"]
		first = self._all_kots(inv)[0].name
		self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 1}], generate_kot=1)
		cancel = frappe.get_doc("NDS KOT", self._all_kots(inv)[-1].name)
		self.assertEqual(cancel.kot_type, "Partially Cancelled")
		self.assertEqual(cancel.original_kot, first)
		self.assertEqual(cancel.items[0].cancelled_qty, 2)
		if "CNCL-KOT-.#####" in (frappe.get_meta("NDS KOT").get_field("naming_series").options or ""):
			self.assertTrue(cancel.name.startswith("CNCL-"), cancel.name)

	def test_deleting_a_sent_draft_sends_cancelled_kot(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 2}], generate_kot=1)["invoice"]
		first = self._all_kots(inv)[0].name
		frappe.set_user("Administrator")
		# Plain delete (no force), as from Desk.
		frappe.delete_doc("POS Invoice", inv)
		self.assertFalse(frappe.db.exists("POS Invoice", inv))
		kots = self._all_kots(inv)
		self.assertEqual(kots[-1].kot_type, "Cancelled")
		self.assertEqual(kots[-1].original_kot, first)
		self.assertIn("deleted", kots[-1].comments or "")
		self.assertFalse(self._table(self.t1).current_invoice)
		# It shows on the kitchen display.
		self.assertIn(kots[-1].name, [k.name for k in kot_api.get_kots(self.production_unit_name)])

	def test_merge_does_not_cancel_the_merged_items(self):
		self._set_roles("custom_transfer_role_permissions", ["NDS Manager"])
		self._as(self.manager)
		target = self._order(table=self.t1, generate_kot=1)["invoice"]
		source = self._order(table=self.t2, generate_kot=1)["invoice"]
		merge_orders(source, target)
		self.assertFalse([k for k in self._all_kots(source) if k.kot_type in kot_api.CANCEL_KOT_TYPES])
		self.assertEqual(kot_api.sent_quantities(target), {(self.item_a, "", ""): 2})


class TestP5Lifecycle(P5Base):
	def _ready(self, user):
		self._as(user)
		tables = {t["name"]: t for t in get_pos_context(self.pos_profile)["tables"]}
		return tables[self.t1]["ready"]

	def test_served_then_picked_up(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._all_kots(inv)[0].name
		self.assertEqual(self._ready(self.captain_a), 0)
		self._as(self.captain_a)
		with self.assertRaises(frappe.ValidationError):
			kot_api.mark_picked_up(kot)  # not served yet

		self._as(self.manager)
		kot_api.serve_kot(kot)
		doc = frappe.get_doc("NDS KOT", kot)
		self.assertEqual(doc.order_status, "Served")
		self.assertEqual(doc.served, 1)
		self.assertIsNotNone(doc.production_time)
		self.assertGreaterEqual(doc.production_time, 0)
		self.assertNotIn(kot, [k.name for k in kot_api.get_kots(self.production_unit_name)])
		self.assertEqual(self._ready(self.captain_a), 1)
		self._as(self.captain_a)
		row = [k for k in get_invoice(inv)["kots"] if k["name"] == kot][0]
		self.assertEqual(row["order_status"], "Served")
		self.assertEqual(row["can_pick_up"], 1)

		res = kot_api.mark_picked_up(kot)
		self.assertEqual(res["order_status"], "Picked Up")
		doc.reload()
		self.assertEqual(doc.order_status, "Picked Up")
		self.assertTrue(doc.picked_up_time)
		self.assertEqual(self._ready(self.captain_a), 0)
		with self.assertRaises(frappe.ValidationError):
			kot_api.mark_picked_up(kot)

	def test_picked_up_guard(self):
		"""P4-T7: mark_picked_up needs an NDS role and a branch seat (managers exempt)."""
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._all_kots(inv)[0].name
		kot_api.serve_kot(kot)
		self._as(self.no_role)
		with self.assertRaises(frappe.PermissionError):
			kot_api.mark_picked_up(kot)
		frappe.set_user("Administrator")
		remove_user_from_test_branch(self.branch, self.captain_b)
		try:
			self._as(self.captain_b)
			with self.assertRaises(frappe.PermissionError):
				kot_api.mark_picked_up(kot)
		finally:
			frappe.set_user("Administrator")
			add_user_to_test_branch(self.branch, self.captain_b)
		self._as(self.captain_b)
		self.assertEqual(kot_api.mark_picked_up(kot)["order_status"], "Picked Up")

	def test_cancel_kots_cannot_be_picked_up(self):
		from nds_restaurant.api.pos import cancel_order

		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		cancel = cancel_order(inv, reason="p5")["kots"][0]
		kot_api.confirm_kot(cancel)
		with self.assertRaises(frappe.ValidationError):
			kot_api.mark_picked_up(cancel)


class TestP5KdsBranchAndPriority(P5Base):
	def test_kds_hides_kots_from_another_branch(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._all_kots(inv)[0].name
		self.assertIn(kot, [k.name for k in kot_api.get_kots(self.production_unit_name)])

		other = code(self.run_id, "BR2")
		frappe.set_user("Administrator")
		if not frappe.db.exists("Branch", other):
			frappe.get_doc({"doctype": "Branch", "branch": other}).insert(ignore_permissions=True)
		self.extra_branches.append(other)
		original = frappe.db.get_value("NDS Production Unit", self.production_unit_name, "branch")
		frappe.db.set_value("NDS Production Unit", self.production_unit_name, "branch", other)
		try:
			self._as(self.manager)
			self.assertNotIn(kot, [k.name for k in kot_api.get_kots(self.production_unit_name)])
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("NDS Production Unit", self.production_unit_name, "branch", original)
		# KOTs made before P5 (no branch) stay visible.
		frappe.db.set_value("NDS KOT", kot, "branch", None)
		frappe.db.set_value("NDS Production Unit", self.production_unit_name, "branch", other)
		try:
			self._as(self.manager)
			self.assertIn(kot, [k.name for k in kot_api.get_kots(self.production_unit_name)])
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("NDS Production Unit", self.production_unit_name, "branch", original)

	def _course(self, suffix, priority, indicate):
		name = code(self.run_id, suffix)
		if not frappe.db.exists("NDS Menu Course", name):
			frappe.get_doc(
				{"doctype": "NDS Menu Course", "course": name, "serving_priority": priority, "indicate_in_kds": indicate}
			).insert(ignore_permissions=True, set_name=name)
		self.courses.append(name)
		return name

	def test_serving_priority_order_and_chips(self):
		soup = self._course("SOUP", 2, 0)
		starter = self._course("STARTER", 1, 1)
		frappe.db.set_value("NDS Menu Item", {"parent": self.menu_name, "item": self.item_a}, "course", soup)
		frappe.db.set_value("NDS Menu Item", {"parent": self.menu_name, "item": self.item_b}, "course", starter)
		try:
			self._as(self.manager)
			res = self._order(
				table=self.t1,
				items=[{"item_code": self.item_a, "qty": 1}, {"item_code": self.item_b, "qty": 1}],
				generate_kot=1,
			)
		finally:
			frappe.set_user("Administrator")
			frappe.db.sql("update `tabNDS Menu Item` set course=null where parent=%s", self.menu_name)
		kot = frappe.get_doc("NDS KOT", res["kots"][0])
		stored = {r.item: (r.course, r.serving_priority) for r in kot.items}
		self.assertEqual(stored[self.item_a], (soup, 2))
		self.assertEqual(stored[self.item_b], (starter, 1))

		self._as(self.manager)
		card = [k for k in kot_api.get_kots(self.production_unit_name) if k.name == kot.name][0]
		self.assertEqual([i["item"] for i in card["items"]], [self.item_b, self.item_a])
		self.assertEqual(card["priority"], 1)
		chips = {i["item"]: (i["serving_priority"], i["indicate_in_kds"]) for i in card["items"]}
		self.assertEqual(chips[self.item_b], (1, 1))
		self.assertEqual(chips[self.item_a], (2, 0))

	def test_addons_stay_with_their_item(self):
		rows = [
			{"item": "soup", "serving_priority": 2, "addon_group_id": "g1", "is_addon": 0},
			{"item": "bread", "serving_priority": None, "addon_group_id": "g1", "is_addon": 1},
			{"item": "starter", "serving_priority": 1, "addon_group_id": "", "is_addon": 0},
			{"item": "water", "serving_priority": None, "addon_group_id": "", "is_addon": 0},
		]
		self.assertEqual(
			[r["item"] for r in kot_api._sort_items_by_priority(rows)], ["starter", "soup", "bread", "water"]
		)
