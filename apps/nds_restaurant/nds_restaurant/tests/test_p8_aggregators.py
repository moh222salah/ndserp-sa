# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P8: aggregator orders (Branch > Aggregator Settings): pricing, no-tax, naming, paid and Keep Unpaid
settlement, KOT/Orders/receipt visibility. Isolated NDSUT fixtures only."""

from unittest import mock

import frappe
from frappe.utils import flt

from nds_restaurant.api import aggregators
from nds_restaurant.api.pos import create_or_update_order, get_invoice, get_orders, get_pos_context
from nds_restaurant.tests.test_helpers import code, delete_if_exists
from nds_restaurant.tests.test_p4_roles import P4Base


class TestP8Aggregators(P4Base):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.agg_customer = None
		cls.agg_price_list = None
		cls.agg_item_price = None
		if not cls.pos_profile:
			return
		frappe.set_user("Administrator")
		cls.addClassCleanup(cls._cleanup_p8)
		group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		cust = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": code(cls.run_id, "Talabat"),
				"customer_group": group,
				"territory": territory,
			}
		).insert(ignore_permissions=True)
		cls.agg_customer = cust.name
		currency = frappe.db.get_value("Company", cls.company, "default_currency")
		cls.agg_price_list = code(cls.run_id, "AGG-PL")
		if not frappe.db.exists("Price List", cls.agg_price_list):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": cls.agg_price_list,
					"currency": currency,
					"selling": 1,
					"enabled": 1,
				}
			).insert(ignore_permissions=True)
		cls.agg_item_price = (
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": cls.item_a,
					"price_list": cls.agg_price_list,
					"price_list_rate": 55,
					"currency": currency,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def _cleanup_p8(cls):
		frappe.set_user("Administrator")
		if frappe.db.exists("Branch", cls.branch) and frappe.get_meta("Branch").has_field("nds_aggregator_settings"):
			branch = frappe.get_doc("Branch", cls.branch)
			branch.set("nds_aggregator_settings", [])
			branch.save(ignore_permissions=True)
		delete_if_exists("Item Price", cls.agg_item_price)
		delete_if_exists("Price List", cls.agg_price_list)
		delete_if_exists("Customer", cls.agg_customer)

	def setUp(self):
		super().setUp()
		if not frappe.get_meta("POS Invoice").has_field("custom_aggregator_order_id"):
			self.skipTest("P8 fields not migrated")
		frappe.set_user("Administrator")
		self.sales_invoices = []
		self.mop = frappe.get_all(
			"POS Opening Entry Detail",
			filters={"parent": frappe.db.get_value("POS Opening Entry", {"user": self.cashier, "pos_profile": self.pos_profile, "status": "Open", "docstatus": 1}, "name")},
			pluck="mode_of_payment",
			order_by="idx",
		)[0]
		self._set_row(keep_unpaid=0, without_tax=1)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in self.sales_invoices:
			self._drop_sales_invoice(name)
		super().tearDown()

	# helpers -------------------------------------------------------------
	def _set_row(self, **values):
		frappe.set_user("Administrator")
		branch = frappe.get_doc("Branch", self.branch)
		branch.set(
			"nds_aggregator_settings",
			[
				{
					"customer": self.agg_customer,
					"price_list": self.agg_price_list,
					"mode_of_payment": self.mop,
					"keep_unpaid": values.get("keep_unpaid", 0),
					"without_tax": values.get("without_tax", 1),
				}
			],
		)
		branch.save(ignore_permissions=True)

	def _drop_sales_invoice(self, name):
		if not frappe.db.exists("Sales Invoice", name):
			return
		doc = frappe.get_doc("Sales Invoice", name)
		if doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()  # before_cancel unlinks the KOTs
		self.assertFalse(frappe.db.exists("NDS KOT", {"sales_invoice": name}))
		for dt in ("GL Entry", "Payment Ledger Entry", "Stock Ledger Entry"):
			if frappe.db.table_exists(dt):
				frappe.db.delete(dt, {"voucher_type": "Sales Invoice", "voucher_no": name})
		frappe.delete_doc("Sales Invoice", name, force=True, ignore_permissions=True)

	def _agg_order(self, order_id="T-123", generate_kot=0, invoice=None, items=None):
		res = create_or_update_order(
			pos_profile=self.pos_profile,
			items=items or [{"item_code": self.item_a, "qty": 2}],
			order_type="Aggregator",
			aggregator=self.agg_customer,
			aggregator_order_id=order_id,
			invoice=invoice,
			generate_kot=generate_kot,
		)
		if res["invoice"] not in self.created_invoices:
			self.created_invoices.append(res["invoice"])
		return res

	# tests ---------------------------------------------------------------
	def test_context_lists_aggregators_with_rates(self):
		self._as(self.cashier)
		ctx = get_pos_context(self.pos_profile)
		rows = [a for a in ctx["aggregators"] if a["customer"] == self.agg_customer]
		self.assertEqual(len(rows), 1)
		self.assertEqual(flt(rows[0]["rates"].get(self.item_a)), 55)
		self.assertEqual((rows[0]["keep_unpaid"], rows[0]["without_tax"]), (0, 1))
		self.assertIn("Aggregator Unpaid", ctx["settings"]["tabs"])
		self._as(self.captain_a)
		self.assertNotIn("Aggregator Unpaid", get_pos_context(self.pos_profile)["settings"]["tabs"])

	def test_aggregator_order_prices_customer_tax_and_name(self):
		frappe.set_user("Administrator")
		rest_prefix = frappe.db.get_value("NDS Restaurant", self.restaurant_name, "aggregator_series_prefix")
		profile_flag = frappe.db.get_value("POS Profile", self.pos_profile, "custom_use_invoice_series_prefix")
		frappe.db.set_value("NDS Restaurant", self.restaurant_name, "aggregator_series_prefix", "AGGUT")
		frappe.db.set_value("POS Profile", self.pos_profile, "custom_use_invoice_series_prefix", 1)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		frappe.clear_document_cache("NDS Restaurant", self.restaurant_name)
		try:
			self._as(self.cashier)
			res = self._agg_order()
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("NDS Restaurant", self.restaurant_name, "aggregator_series_prefix", rest_prefix)
			frappe.db.set_value("POS Profile", self.pos_profile, "custom_use_invoice_series_prefix", profile_flag or 0)
			frappe.clear_document_cache("POS Profile", self.pos_profile)
			frappe.clear_document_cache("NDS Restaurant", self.restaurant_name)
		doc = frappe.get_doc("POS Invoice", res["invoice"])
		self.assertTrue(doc.name.startswith("AGGUT-"), doc.name)
		self.assertEqual((doc.customer, doc.custom_aggregator, doc.custom_nds_order_type), (self.agg_customer, self.agg_customer, "Aggregator"))
		self.assertEqual(doc.custom_aggregator_order_id, "T-123")
		self.assertEqual([flt(r.rate) for r in doc.items], [55])
		self.assertEqual(doc.selling_price_list, self.agg_price_list)
		self.assertFalse(doc.taxes_and_charges)
		self.assertEqual(len(doc.taxes), 0)
		self.assertFalse(doc.custom_nds_table)
		# Orders: aggregator filter and badge data; detail payload
		rows = get_orders(self.pos_profile, status="Draft", aggregator=self.agg_customer)
		self.assertEqual([r["name"] for r in rows], [doc.name])
		self.assertEqual((rows[0]["aggregator"], rows[0]["aggregator_order_id"]), (self.agg_customer, "T-123"))
		self.assertEqual(get_invoice(doc.name)["aggregator_order_id"], "T-123")
		# an unconfigured aggregator is refused
		self._as(self.cashier)
		with self.assertRaisesRegex(frappe.ValidationError, "not configured"):
			create_or_update_order(
				pos_profile=self.pos_profile,
				items=[{"item_code": self.item_a, "qty": 1}],
				order_type="Aggregator",
				aggregator="NDSUT-no-such-aggregator",
			)

	def test_paid_settlement_uses_aggregator_mode_of_payment(self):
		self._set_row(keep_unpaid=0, without_tax=1)
		self._as(self.cashier)
		inv = self._agg_order(generate_kot=1)["invoice"]
		res = aggregators.settle_aggregator(inv)
		self.assertEqual((res["keep_unpaid"], res["mode_of_payment"]), (0, self.mop))
		frappe.set_user("Administrator")
		doc = frappe.get_doc("POS Invoice", inv)
		self.assertEqual((doc.docstatus, doc.status), (1, "Paid"))
		self.assertEqual([p.mode_of_payment for p in doc.payments if flt(p.amount)], [self.mop])
		self.assertEqual(len(doc.taxes), 0)
		self.assertEqual(flt(doc.grand_total), 110)
		# KOT and receipt carry the platform badge
		kot = frappe.get_all("NDS KOT", filters={"pos_invoice": inv}, fields=["aggregator", "aggregator_order_id"])[0]
		self.assertEqual((kot.aggregator_order_id, bool(kot.aggregator)), ("T-123", True))
		html = frappe.get_print("POS Invoice", inv, print_format="NDS Receipt", no_letterhead=1)
		self.assertIn("#T-123", html)

	def test_keep_unpaid_becomes_receivable_sales_invoice(self):
		self._set_row(keep_unpaid=1, without_tax=1)
		self._as(self.cashier)
		inv = self._agg_order(order_id="T-777", generate_kot=1)["invoice"]
		frappe.set_user("Administrator")
		kots = frappe.get_all("NDS KOT", filters={"pos_invoice": inv, "docstatus": 1}, pluck="name")
		self.assertTrue(kots)
		self._as(self.cashier)
		with mock.patch("nds_restaurant.api.recipe.issue_recipe_stock") as issued:
			res = aggregators.settle_aggregator(inv)
		frappe.set_user("Administrator")
		self.sales_invoices.append(res["sales_invoice"])
		self.assertEqual(res["keep_unpaid"], 1)
		self.assertFalse(frappe.db.exists("POS Invoice", inv))
		si = frappe.get_doc("Sales Invoice", res["sales_invoice"])
		self.assertEqual((si.docstatus, si.is_pos, si.customer), (1, 0, self.agg_customer))
		self.assertEqual((si.custom_source_pos_invoice, si.custom_aggregator_order_id), (inv, "T-777"))
		self.assertEqual(flt(si.outstanding_amount), flt(si.grand_total))
		self.assertEqual(flt(si.grand_total), 110)
		self.assertEqual(len(si.taxes), 0)
		# ingredients are issued for the Sales Invoice (recipe hook on submit)
		self.assertTrue(issued.called)
		self.assertEqual(issued.call_args[0][0].name, si.name)
		# the kitchen keeps its tickets (no Cancelled KOT), now linked to the Sales Invoice
		self.assertEqual(
			sorted(frappe.get_all("NDS KOT", filters={"sales_invoice": si.name}, pluck="name")), sorted(kots)
		)
		self.assertFalse(frappe.db.exists("NDS KOT", {"pos_invoice": inv, "kot_type": ["in", ["Cancelled", "Partially Cancelled"]]}))
		# Orders lists it as Unpaid (aggregator)
		self._as(self.cashier)
		rows = get_orders(self.pos_profile, status="Aggregator Unpaid")
		mine = [r for r in rows if r["name"] == si.name]
		self.assertEqual(len(mine), 1)
		self.assertEqual((mine[0]["order_status"], mine[0]["aggregator_order_id"]), ("Unpaid (aggregator)", "T-777"))
		self._as(self.captain_a)
		with self.assertRaises(frappe.PermissionError):
			get_orders(self.pos_profile, status="Aggregator Unpaid")

	def test_settle_rules(self):
		self._as(self.cashier)
		normal = self._order()["invoice"]
		with self.assertRaisesRegex(frappe.ValidationError, "not an aggregator order"):
			aggregators.settle_aggregator(normal)
		inv = self._agg_order()["invoice"]
		self._as(self.captain_a)
		with self.assertRaises(frappe.PermissionError):
			aggregators.settle_aggregator(inv)

	def test_recipe_hook_ignores_ordinary_sales_invoices(self):
		ordinary = frappe._dict(meta=frappe.get_meta("Sales Invoice"), custom_source_pos_invoice=None)
		ordinary.get = lambda k, d=None: None
		with mock.patch("nds_restaurant.api.recipe.issue_recipe_stock") as issued:
			aggregators.on_sales_invoice_submit(ordinary)
		self.assertFalse(issued.called)
