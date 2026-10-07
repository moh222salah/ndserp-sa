"""Whitelisted language switching for the navbar globe toggle.

Writes Frappe's own `User.language` field — that is what actually drives
translation and the html dir/lang attributes. There is deliberately no
separate theme-owned language field to drift out of sync with it.
"""

from __future__ import annotations

import frappe
from frappe import _

# Only the two languages this theme ships a bundled dictionary for.
SUPPORTED_LANGS = ("en", "ar")


def _require_login() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Login required"), frappe.AuthenticationError)
	return user


@frappe.whitelist()
def get_language() -> dict:
	user = _require_login()
	lang = frappe.db.get_value("User", user, "language") or "en"
	return {"lang": lang if lang in SUPPORTED_LANGS else "en"}


@frappe.whitelist()
def set_language(lang: str) -> dict:
	"""Persist the user's language. Returns the applied value."""
	user = _require_login()

	if lang not in SUPPORTED_LANGS:
		frappe.throw(_("Unsupported language: {0}").format(frappe.utils.escape_html(str(lang))))

	frappe.db.set_value("User", user, "language", lang, update_modified=False)
	frappe.db.commit()

	# Without this the old translations keep being served from cache on reload.
	try:
		frappe.clear_cache(user=user)
	except Exception:
		frappe.log_error(title="amir_theme_v16: language cache clear failed")

	return {"lang": lang}
