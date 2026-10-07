# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P6a: bill routing to network printers, KOT print format per printer row, KOT reprint through a
Duplicate KOT (P5-T5), and the NDS KOT print format. Network printing is mocked (no CUPS job is
sent); only NDSUT fixtures are used."""

from unittest.mock import patch

import frappe

from nds_restaurant.api import kot as kot_api
from nds_restaurant.api import printing
from nds_restaurant.api.pos import cancel_order, get_invoice, get_pos_context
from nds_restaurant.tests.test_helpers import code, delete_if_exists
from nds_restaurant.tests.test_p4_roles import P4Base

PRINT_BY_SERVER = "frappe.utils.print_format.print_by_server"


class P6Base(P4Base):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.printers = {}
		cls.alt_format = None
		# Class cleanups run LIFO, so printer rows go before the room/profile/unit fixtures.
		cls.addClassCleanup(cls._p6_cleanup)
		if not getattr(cls, "pos_profile", None):
			return
		for key in ("ROOM", "PROFILE", "UNIT"):
			name = code(cls.run_id, f"PRN-{key}")
			if not frappe.db.exists("Network Printer Settings", name):
				doc = frappe.get_doc(
					{
						"doctype": "Network Printer Settings",
						"server_ip": "127.0.0.1",
						"port": 631,
						"printer_name": "ndsut-fake",
					}
				)
				doc.flags.ignore_mandatory = True
				doc.insert(ignore_permissions=True, set_name=name)
			cls.printers[key] = name
		cls.alt_format = code(cls.run_id, "KOT-ALT")
		if not frappe.db.exists("Print Format", cls.alt_format):
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": cls.alt_format,
					"doc_type": "NDS KOT",
					"module": "NDS Restaurant",
					"standard": "No",
					"custom_format": 1,
					"print_format_type": "Jinja",
					"html": "<div>ALT {{ doc.name }}</div>",
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _p6_cleanup(cls):
		frappe.set_user("Administrator")
		if getattr(cls, "pos_profile", None):
			cls._clear_printer_rows()
		delete_if_exists("Print Format", getattr(cls, "alt_format", None))
		for name in getattr(cls, "printers", {}).values():
			delete_if_exists("Network Printer Settings", name)

	@classmethod
	def _clear_printer_rows(cls):
		for doctype, name, field in (
			("NDS Room", cls.room_name, "printer_settings"),
			("NDS Production Unit", cls.production_unit_name, "printer_settings"),
			("POS Profile", cls.pos_profile, "custom_printer_settings"),
		):
			if name and frappe.db.exists(doctype, name) and frappe.get_meta(doctype).has_field(field):
				doc = frappe.get_doc(doctype, name)
				if doc.get(field):
					doc.set(field, [])
					doc.save(ignore_permissions=True)
				frappe.clear_document_cache(doctype, name)

	def setUp(self):
		super().setUp()
		if not frappe.get_meta("POS Profile").has_field("custom_enable_kot_reprint"):
			self.skipTest("custom_enable_kot_reprint not migrated")
		self._clear_printer_rows()
		self._set_profile("custom_enable_kot_reprint", 0)
		self._set_profile("custom_reprint_kot_format", None)

	def tearDown(self):
		super().tearDown()
		self._clear_printer_rows()
		self._set_profile("custom_enable_kot_reprint", 0)
		self._set_profile("custom_reprint_kot_format", None)
		frappe.db.delete("Error Log", {"method": "NDS Network Print", "creation": (">=", self._started)})

	def run(self, result=None):
		self._started = frappe.utils.now_datetime()
		return super().run(result)

	def _printer_row(self, doctype, name, field, printer, bill=0, kot=0, kot_format=None):
		current = frappe.session.user
		frappe.set_user("Administrator")
		doc = frappe.get_doc(doctype, name)
		doc.append(field, {"printer": printer, "bill": bill, "kot": kot, "kot_print_format": kot_format})
		doc.save(ignore_permissions=True)
		frappe.clear_document_cache(doctype, name)
		frappe.set_user(current)


class TestP6BillRouting(P6Base):
	def test_room_printer_then_profile_printer_then_browser(self):
		self._as(self.manager)
		inv = self._order(table=self.t1)["invoice"]
		fmt = frappe.db.get_value("POS Profile", self.pos_profile, "print_format") or "NDS Receipt"

		self._printer_row("NDS Room", self.room_name, "printer_settings", self.printers["ROOM"], bill=1)
		self._printer_row("POS Profile", self.pos_profile, "custom_printer_settings", self.printers["PROFILE"], bill=1)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.print_bill(inv)
		self.assertTrue(res["printed"])
		self.assertEqual(res["printer"], self.printers["ROOM"])
		pbs.assert_called_once_with("POS Invoice", inv, self.printers["ROOM"], print_format=fmt, no_letterhead=1)
		self.assertEqual(res["invoice_printed"], 1)
		self.assertEqual(frappe.db.get_value("POS Invoice", inv, "custom_invoice_printed"), 1)

		# No bill printer on the room: the POS Profile printer is used.
		frappe.set_user("Administrator")
		room = frappe.get_doc("NDS Room", self.room_name)
		room.set("printer_settings", [])
		room.save(ignore_permissions=True)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.print_bill(inv)
		self.assertEqual(res["printer"], self.printers["PROFILE"])
		self.assertTrue(res["printed"])

		# Neither: the POS prints through the browser.
		frappe.set_user("Administrator")
		self._clear_printer_rows()
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.print_bill(inv)
		pbs.assert_not_called()
		self.assertFalse(res["printed"])
		self.assertEqual(res["method"], "browser")
		self.assertIn("/printview?doctype=POS%20Invoice", res["print_url"])
		self.assertIn(inv, res["print_url"])

	def test_kot_only_rows_are_not_bill_printers_and_failures_fall_back(self):
		self._as(self.manager)
		inv = self._order(table=self.t1)["invoice"]
		self._printer_row("NDS Room", self.room_name, "printer_settings", self.printers["UNIT"], kot=1)
		self._printer_row("POS Profile", self.pos_profile, "custom_printer_settings", self.printers["PROFILE"], bill=1)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER, side_effect=Exception("cups down")):
			res = printing.print_bill(inv)
		self.assertEqual(res["printer"], self.printers["PROFILE"])
		self.assertFalse(res["printed"])
		self.assertEqual(res["reason"], "print_failed")
		self.assertTrue(res["print_url"])
		# The bill still counts as printed (the browser prints it).
		self.assertEqual(res["invoice_printed"], 1)

	def test_print_bill_requires_profile_access(self):
		self._as(self.manager)
		inv = self._order(table=self.t1)["invoice"]
		self._as(self.no_role)
		with self.assertRaises(frappe.PermissionError):
			printing.print_bill(inv)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("POS Invoice", inv, "custom_invoice_printed"))


class TestP6KotPrinting(P6Base):
	def test_kot_uses_printer_row_format(self):
		self._printer_row(
			"NDS Production Unit", self.production_unit_name, "printer_settings", self.printers["UNIT"], kot=1, kot_format="NDS KOT"
		)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._kots(inv)[0].name
		expected_fmt = "NDS KOT" if frappe.db.exists("Print Format", "NDS KOT") else None
		pbs.assert_called_once_with("NDS KOT", kot, self.printers["UNIT"], print_format=expected_fmt, no_letterhead=1)

		# Another format on the row prints in that one.
		frappe.set_user("Administrator")
		unit = frappe.get_doc("NDS Production Unit", self.production_unit_name)
		unit.printer_settings[0].kot_print_format = self.alt_format
		unit.save(ignore_permissions=True)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.print_kot(kot)
		self.assertTrue(res["printed"])
		pbs.assert_called_once_with("NDS KOT", kot, self.printers["UNIT"], print_format=self.alt_format, no_letterhead=1)

	def test_no_printer_returns_no_printer(self):
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			inv = self._order(table=self.t1, generate_kot=1)["invoice"]
			res = printing.print_kot(self._kots(inv)[0].name)
		pbs.assert_not_called()
		self.assertFalse(res["printed"])
		self.assertEqual(res["reason"], "no_printer")

	def test_nds_kot_format_renders_banner(self):
		if not frappe.db.exists("Print Format", "NDS KOT"):
			self.skipTest("NDS KOT print format not synced")
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._kots(inv)[0].name
		frappe.set_user("Administrator")
		html = frappe.get_print("NDS KOT", kot, print_format="NDS KOT", no_letterhead=1)
		item_name = frappe.db.get_value("Item", self.item_a, "item_name")
		self.assertIn(kot, html)
		self.assertIn(item_name, html)
		self.assertNotIn("DUPLICATE", html)

		self._as(self.manager)
		res = cancel_order(inv, reason="p6 test")
		frappe.set_user("Administrator")
		html = frappe.get_print("NDS KOT", res["kots"][0], print_format="NDS KOT", no_letterhead=1)
		self.assertIn("CANCELLED", html)


class TestP6KotReprint(P6Base):
	def test_reprint_disabled_hides_button_and_raises(self):
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._kots(inv)[0].name
		self.assertEqual(get_invoice(inv)["can_reprint_kot"], 0)
		self.assertEqual(get_pos_context(self.pos_profile)["settings"]["kot_reprint"], 0)
		with self.assertRaises(frappe.ValidationError):
			printing.reprint_kot(kot)
		self.assertEqual(len(self._kots(inv)), 1)

	def test_reprint_creates_duplicate_in_reprint_format(self):
		self._set_profile("custom_enable_kot_reprint", 1)
		self._set_profile("custom_reprint_kot_format", self.alt_format)
		self._printer_row(
			"NDS Production Unit", self.production_unit_name, "printer_settings", self.printers["UNIT"], kot=1, kot_format="NDS KOT"
		)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER):
			inv = self._order(table=self.t1, items=[{"item_code": self.item_a, "qty": 2}], generate_kot=1)["invoice"]
		kot = self._kots(inv)[0].name
		before = kot_api.sent_quantities(inv)

		self._as(self.cashier)
		self.assertEqual(get_invoice(inv)["can_reprint_kot"], 1)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.reprint_kot(kot)
		self.assertTrue(res["printed"])
		self.assertEqual(res["original_kot"], kot)
		dup = frappe.get_doc("NDS KOT", res["kot"])
		pbs.assert_called_once_with("NDS KOT", dup.name, self.printers["UNIT"], print_format=self.alt_format, no_letterhead=1)
		self.assertEqual(dup.kot_type, "Duplicate")
		self.assertEqual(dup.docstatus, 1)
		self.assertEqual(dup.original_kot, kot)
		self.assertEqual(dup.pos_invoice, inv)
		self.assertEqual(dup.production_unit, self.production_unit_name)
		self.assertEqual([(r.item, r.qty) for r in dup.items], [(self.item_a, 2)])

		# The kitchen sees it, linked to the original.
		self._as(self.manager)
		kds = {k.name: k for k in kot_api.get_kots(self.production_unit_name)}
		self.assertIn(dup.name, kds)
		self.assertEqual(kds[dup.name].get("original_kot"), kot)

		# Reprinting the duplicate links back to the original KOT.
		self._as(self.cashier)
		with patch(PRINT_BY_SERVER):
			again = printing.reprint_kot(dup.name)
		self.assertEqual(again["original_kot"], kot)

		# Duplicates don't change the kitchen baseline: the next edit diffs correctly.
		self.assertEqual(kot_api.sent_quantities(inv), before)
		self._as(self.manager)
		with patch(PRINT_BY_SERVER):
			self._order(table=self.t1, invoice=inv, items=[{"item_code": self.item_a, "qty": 3}], generate_kot=1)
		latest = frappe.get_doc("NDS KOT", self._kots(inv)[-1].name)
		self.assertEqual(latest.kot_type, "Modified")
		self.assertEqual([(r.item, r.qty, r.old_qty) for r in latest.items], [(self.item_a, 3, 2)])

	def test_reprint_permissions_and_browser_fallback(self):
		self._set_profile("custom_enable_kot_reprint", 1)
		self._as(self.captain_a)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		kot = self._kots(inv)[0].name
		# A captain whose role isn't allowed to bill can't reprint.
		self.assertEqual(get_invoice(inv)["can_reprint_kot"], 0)
		with self.assertRaises(frappe.PermissionError):
			printing.reprint_kot(kot)

		# Manager, no printer configured: a Duplicate is still created and the browser prints it.
		self._as(self.manager)
		with patch(PRINT_BY_SERVER) as pbs:
			res = printing.reprint_kot(kot)
		pbs.assert_not_called()
		self.assertFalse(res["printed"])
		self.assertIn("/printview?doctype=NDS%20KOT", res["print_url"])
		self.assertIn(res["kot"], res["print_url"])

	def test_reprint_cancel_kot_of_voided_order(self):
		self._set_profile("custom_enable_kot_reprint", 1)
		self._as(self.manager)
		inv = self._order(table=self.t1, generate_kot=1)["invoice"]
		cancel_kot = cancel_order(inv, reason="p6 test")["kots"][0]
		self.assertFalse(frappe.db.exists("POS Invoice", inv))
		with patch(PRINT_BY_SERVER):
			res = printing.reprint_kot(cancel_kot)
		dup = frappe.get_doc("NDS KOT", res["kot"])
		self.assertEqual(dup.kot_type, "Duplicate")
		self.assertEqual(dup.original_kot, cancel_kot)
