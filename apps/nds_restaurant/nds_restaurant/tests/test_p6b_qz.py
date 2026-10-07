# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P6-T5: optional QZ Tray printing (server-side signing) and the PR #11 POS Settings guard.
Isolated NDSUT fixtures; NDS QZ Settings is only touched when it is empty, and is emptied again."""

import base64
from unittest import mock

import frappe

from nds_restaurant.api import printing
from nds_restaurant.api.pos import get_pos_context
from nds_restaurant.tests.test_p4_roles import P4Base

QZ = "NDS QZ Settings"


def _new_key_pem():
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import rsa

	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	pem = key.private_bytes(
		serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
	).decode()
	return key, pem


class TestP6bQz(P4Base):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("DocType", QZ):
			self.skipTest("NDS QZ Settings not migrated")
		if frappe.db.get_single_value(QZ, "certificate") or printing._qz_private_key():
			self.skipTest("Real QZ signing material is configured; not touching it")
		self._profile_orig = frappe.db.get_value(
			"POS Profile", self.pos_profile, ["custom_qz_print", "custom_qz_host", "custom_qz_printer"], as_dict=True
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		self._clear_qz()
		frappe.db.set_value("POS Profile", self.pos_profile, dict(self._profile_orig))
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		super().tearDown()

	def _clear_qz(self):
		frappe.db.set_single_value(QZ, "certificate", None)
		frappe.db.delete("__Auth", {"doctype": QZ})
		frappe.clear_document_cache(QZ, QZ)

	def _configure(self, certificate="-----BEGIN CERTIFICATE-----\nNDSUT\n-----END CERTIFICATE-----", pem=None):
		frappe.set_user("Administrator")
		doc = frappe.get_single(QZ)
		doc.certificate = certificate
		if pem is not None:
			doc.private_key = pem
		doc.save(ignore_permissions=True)

	def test_settings_are_system_manager_only(self):
		self.assertFalse(frappe.has_permission(QZ, "read", user=self.captain_a))
		self.assertFalse(frappe.has_permission(QZ, "read", user=self.cashier))
		self.assertTrue(frappe.has_permission(QZ, "read", user="Administrator"))

	def test_unsigned_mode_when_nothing_is_configured(self):
		self._as(self.captain_a)
		self.assertIsNone(printing.qz_certificate())
		self.assertIsNone(printing.qz_sign("abc"))

	def test_certificate_and_signature_roundtrip(self):
		from cryptography.hazmat.primitives import hashes
		from cryptography.hazmat.primitives.asymmetric import padding

		key, pem = _new_key_pem()
		self._configure(pem=pem)
		self._as(self.cashier)
		self.assertIn("NDSUT", printing.qz_certificate())
		message = "qz-request-1234"
		sig = base64.b64decode(printing.qz_sign(message))
		# raises InvalidSignature when wrong
		key.public_key().verify(sig, message.encode(), padding.PKCS1v15(), hashes.SHA512())
		# the private key is never part of any payload the POS receives
		frappe.set_user("Administrator")
		self.assertNotIn("PRIVATE KEY", frappe.as_json(printing.get_print_config(self.pos_profile)))

	def test_bad_key_and_bad_message_are_rejected(self):
		self._configure(pem="not a key")
		self._as(self.captain_a)
		with self.assertRaises(frappe.ValidationError):
			printing.qz_sign("abc")
		with self.assertRaises(frappe.ValidationError):
			printing.qz_sign("")

	def test_qz_endpoints_need_a_pos_role(self):
		for user in ("Guest", self.no_role, self.kitchen):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				printing.qz_certificate()
			with self.assertRaises(frappe.PermissionError):
				printing.qz_sign("abc")

	def test_bill_html_uses_profile_format_and_checks_access(self):
		self._as(self.captain_a)
		inv = self._order(table=self.t1)["invoice"]
		html = printing.get_bill_html(inv)
		self.assertIsInstance(html, str)
		self.assertIn(inv, html)
		self._as(self.no_role)
		with self.assertRaises(frappe.PermissionError):
			printing.get_bill_html(inv)

	def test_context_exposes_qz_settings_per_profile(self):
		self._as(self.captain_a)
		settings = get_pos_context(self.pos_profile)["settings"]
		self.assertFalse(settings.get("qz_print"))
		frappe.set_user("Administrator")
		frappe.db.set_value(
			"POS Profile",
			self.pos_profile,
			{"custom_qz_print": 1, "custom_qz_host": "", "custom_qz_printer": "NDSUT-THERMAL"},
		)
		frappe.clear_document_cache("POS Profile", self.pos_profile)
		self._as(self.captain_a)
		settings = get_pos_context(self.pos_profile)["settings"]
		self.assertEqual(settings["qz_print"], 1)
		self.assertEqual(settings["qz_host"], "localhost")
		self.assertEqual(settings["qz_printer"], "NDSUT-THERMAL")


class TestPosSettingsGuard(P4Base):
	def test_context_works_without_invoice_type_field(self):
		"""Salvaged from PR #11: older ERPNext has no POS Settings.invoice_type."""
		real = frappe.get_meta

		class _NoInvoiceType:
			def has_field(self, fieldname):
				return False

		def fake(dt, *a, **k):
			return _NoInvoiceType() if dt == "POS Settings" else real(dt, *a, **k)

		self._as(self.captain_a)
		with mock.patch("frappe.get_meta", side_effect=fake), mock.patch(
			"frappe.db.get_single_value", wraps=frappe.db.get_single_value
		) as gsv:
			ctx = get_pos_context(self.pos_profile)
		self.assertEqual(ctx["pos_profile"], self.pos_profile)
		self.assertNotIn(mock.call("POS Settings", "invoice_type"), gsv.call_args_list)
