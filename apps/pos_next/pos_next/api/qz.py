# -*- coding: utf-8 -*-
# Copyright (c) 2026, POS Next and contributors
# For license information, please see license.txt

"""
QZ Tray certificate + message signing helpers.

Credentials are auto-generated under:
  private/files/qz/digital-certificate.txt
  private/files/qz/private-key.pem

Optional overrides via site_config.json:
  "qz_digital_certificate": "-----BEGIN CERTIFICATE-----\\n..."
  "qz_private_key": "-----BEGIN PRIVATE KEY-----\\n..."

After first generation, install the certificate into QZ Tray once:
  QZ Tray → Advanced → Site Manager → drag digital-certificate.txt
"""

from __future__ import unicode_literals

import base64
import os
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _


QZ_DIR_PARTS = ("private", "files", "qz")
CERT_FILENAME = "digital-certificate.txt"
KEY_FILENAME = "private-key.pem"


def _qz_dir():
	path = frappe.get_site_path(*QZ_DIR_PARTS)
	os.makedirs(path, exist_ok=True)
	return path


def _cert_path():
	return os.path.join(_qz_dir(), CERT_FILENAME)


def _key_path():
	return os.path.join(_qz_dir(), KEY_FILENAME)


def _read_text_file(path):
	if os.path.isfile(path):
		with open(path, encoding="utf-8") as handle:
			return handle.read().strip()
	return None


def _write_text_file(path, content):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(content.strip() + "\n")
	try:
		os.chmod(path, 0o600)
	except OSError:
		pass


def _get_certificate_text():
	cert = frappe.conf.get("qz_digital_certificate")
	if cert:
		return str(cert).strip()
	return _read_text_file(_cert_path())


def _get_private_key_text():
	key = frappe.conf.get("qz_private_key")
	if key:
		return str(key).strip()
	return _read_text_file(_key_path())


def _generate_qz_credentials():
	"""Create a site-local self-signed cert + RSA private key for QZ signing."""
	from cryptography import x509
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import rsa
	from cryptography.x509.oid import NameOID

	site = frappe.local.site or "pos-next"
	private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

	subject = issuer = x509.Name(
		[
			x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
			x509.NameAttribute(NameOID.ORGANIZATION_NAME, "POS Next"),
			x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "QZ Tray"),
			x509.NameAttribute(NameOID.COMMON_NAME, f"POS Next QZ ({site})"),
		]
	)

	now = datetime.now(timezone.utc)
	certificate = (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(issuer)
		.public_key(private_key.public_key())
		.serial_number(x509.random_serial_number())
		.not_valid_before(now - timedelta(minutes=1))
		.not_valid_after(now + timedelta(days=3650))
		.add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
		.sign(private_key, hashes.SHA256())
	)

	cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")
	key_pem = private_key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.PKCS8,
		encryption_algorithm=serialization.NoEncryption(),
	).decode("utf-8")

	_write_text_file(_cert_path(), cert_pem)
	_write_text_file(_key_path(), key_pem)
	return cert_pem, key_pem


def ensure_qz_credentials(force=False):
	"""
	Ensure certificate + private key exist on this site.
	Returns (certificate_pem, private_key_pem, created_bool).
	"""
	if frappe.conf.get("qz_digital_certificate") and frappe.conf.get("qz_private_key"):
		return (
			str(frappe.conf.qz_digital_certificate).strip(),
			str(frappe.conf.qz_private_key).strip(),
			False,
		)

	cert = _read_text_file(_cert_path())
	key = _read_text_file(_key_path())

	if cert and key and not force:
		return cert, key, False

	cert, key = _generate_qz_credentials()
	return cert, key, True


@frappe.whitelist()
def get_qz_certificate(ensure=1):
	"""
	Return the QZ digital certificate PEM/text.

	By default auto-creates site credentials so the browser can always
	resolve setCertificatePromise (avoids "Failed to get certificate: undefined").
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	created = False
	if cint_truthy(ensure):
		cert, key, created = ensure_qz_credentials()
	else:
		cert = _get_certificate_text()
		key = _get_private_key_text()

	return {
		"certificate": cert or "",
		"configured": bool(cert),
		"signing_available": bool(cert and key),
		"created": created,
		"install_hint": _(
			"Download the certificate and add it in QZ Tray → Advanced → Site Manager "
			"(drag & drop). Then click Allow / Remember once."
		),
	}


@frappe.whitelist()
def setup_qz_credentials(force=0):
	"""Create or regenerate QZ signing credentials for this site."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	if not frappe.has_permission("POS Profile", "write") and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted to set up QZ credentials"))

	cert, key, created = ensure_qz_credentials(force=cint_truthy(force))
	return {
		"success": True,
		"created": created,
		"configured": True,
		"signing_available": True,
		"certificate": cert,
		"message": _("QZ credentials ready") if not created else _("QZ credentials created"),
	}


@frappe.whitelist()
def download_qz_certificate():
	"""Download digital-certificate.txt for QZ Tray Site Manager install."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	cert, _key, _created = ensure_qz_credentials()
	frappe.local.response.filename = "digital-certificate.txt"
	frappe.local.response.filecontent = cert
	frappe.local.response.type = "download"


@frappe.whitelist()
def sign_qz_request(request=None):
	"""
	Sign a QZ Tray request string with the site private key (SHA512).

	Returns base64 signature text expected by qz.security.setSignaturePromise.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	if not request:
		frappe.throw(_("Missing QZ signing request"))

	_cert, private_key_pem, _created = ensure_qz_credentials()
	if not private_key_pem:
		frappe.throw(_("QZ private key is not available"))

	try:
		from cryptography.hazmat.backends import default_backend
		from cryptography.hazmat.primitives import hashes, serialization
		from cryptography.hazmat.primitives.asymmetric import padding
	except ImportError:
		frappe.throw(_("cryptography package is required for QZ signing"))

	try:
		private_key = serialization.load_pem_private_key(
			private_key_pem.encode("utf-8"),
			password=None,
			backend=default_backend(),
		)
		signature = private_key.sign(
			str(request).encode("utf-8"),
			padding.PKCS1v15(),
			hashes.SHA512(),
		)
		return base64.b64encode(signature).decode("ascii")
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "QZ Sign Request Error")
		frappe.throw(_("Failed to sign QZ request: {0}").format(str(exc)))


def cint_truthy(value):
	if isinstance(value, str):
		return value.lower() in ("1", "true", "yes", "on")
	return bool(value)
