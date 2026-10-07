# Copyright (c) 2026, amir_theme_v16
# License: MIT

import frappe
from frappe.model.document import Document

# Every switch this doctype owns, with the value used when the record has never
# been saved (or the doctype isn't installed yet - see `get_settings`). Keeping
# the defaults here, rather than only in the JSON, means the client gets a
# complete, correctly-typed payload on a brand-new site where the Singles table
# still has no rows: the theme keeps behaving exactly as it did before this
# doctype existed, i.e. everything on.
DEFAULTS = {
	"enable_hijri_dates": 1,
	"enable_smart_actions": 1,
	"enable_translation_mode": 1,
	"enable_color_schemes": 1,
	"language_switcher_position": "Navbar",
}

CHECK_FIELDS = (
	"enable_hijri_dates",
	"enable_smart_actions",
	"enable_translation_mode",
	"enable_color_schemes",
)

# Where each branding field has to land for the framework to actually use it.
#
# Frappe reads brand assets from three unrelated singles, and a value set in one
# is invisible to the surfaces served by the others - which is why uploading a
# logo in one place used to change some screens and not others:
#
#   Website Settings.favicon      -> <link rel="icon"> on BOTH www/desk.html and
#                                    templates/base.html (the browser tab icon)
#   Website Settings.app_name     -> <title> of the desk
#   Website Settings.splash_image -> templates/includes/splash_screen.html
#   Website Settings.app_logo /
#   Navbar Settings.app_logo      -> navbar_settings.get_app_logo(), which is
#                                    `frappe.get_website_settings("app_logo") or
#                                    the Navbar single` - both are written so the
#                                    result is the same whichever one wins
#   Login Page Settings.logo      -> this app's own branded login card
#
# `(doctype, fieldname)` pairs, keyed by our field. Order is irrelevant; every
# target is written independently.
BRANDING_TARGETS = {
	"favicon": [("Website Settings", "favicon")],
	"app_name": [("Website Settings", "app_name")],
	"splash_image": [("Website Settings", "splash_image")],
	"app_logo": [
		("Website Settings", "app_logo"),
		("Navbar Settings", "app_logo"),
	],
}

# The login card falls back to the app logo when no login-specific one is given,
# so one upload is enough to brand everything.
LOGIN_LOGO_SOURCES = ("login_logo", "app_logo")


class AmirThemeSettings(Document):
	def on_update(self):
		self.apply_branding()
		# The switches are read from `bootinfo`, which Frappe caches per user.
		# Without this, a changed setting would only reach a user after their
		# cached boot expired - the reload prompted in the UI would still show
		# the old behaviour, which reads as "the toggle doesn't work".
		frappe.clear_cache()

	def apply_branding(self) -> None:
		"""Write the branding fields through to the singles Frappe reads.

		Empty is "not configured", never "clear it": a site that already set a
		favicon in Website Settings and has not filled this form in must keep
		what it has. That also makes the hook safe to re-run - saving an
		unrelated switch never disturbs branding.

		`db_set` on the single rather than `get_doc().save()`: these are plain
		scalar columns with no validation of their own, and a full save of
		Website Settings would fire its own `on_update` (route clearing, sitemap
		work) as a side effect of ticking a theme checkbox.
		"""
		for fieldname, targets in BRANDING_TARGETS.items():
			value = (self.get(fieldname) or "").strip()
			if not value:
				continue
			for doctype, target_field in targets:
				_set_single_value(doctype, target_field, value)

		login_logo = next((v for v in (self.get(f) for f in LOGIN_LOGO_SOURCES) if v), None)
		if login_logo:
			_set_single_value("Login Page Settings", "logo", login_logo.strip())


def _set_single_value(doctype: str, fieldname: str, value: str) -> None:
	"""Set one field on a Single, tolerating a doctype that isn't there.

	`Login Page Settings` is this app's own and `Navbar Settings` is core, but
	both are read defensively: branding is cosmetic and must never be able to
	make saving the settings form fail.
	"""
	try:
		if frappe.db.get_single_value(doctype, fieldname) == value:
			return
		# `set_single_value` clears the document cache for the single itself, so
		# `get_cached_doc`/`get_website_settings` readers pick the new value up
		# without any extra invalidation here.
		frappe.db.set_single_value(doctype, fieldname, value)
	except Exception:
		frappe.log_error(title=f"amir_theme_v16: could not apply branding to {doctype}")


def get_settings() -> dict:
	"""The settings as a plain dict, safe to call at any point in a request.

	Falls back to `DEFAULTS` whenever the value can't be read - during the
	migration that first installs this doctype, on a site where the app was
	just added, or if the Singles row is missing. Boot must never fail because
	a cosmetic settings record isn't there yet.
	"""
	try:
		doc = frappe.get_cached_doc("Amir Theme Settings", "Amir Theme Settings")
	except Exception:
		return dict(DEFAULTS)

	settings = {}

	for field in CHECK_FIELDS:
		value = doc.get(field)
		# A never-saved Single returns None for its fields; that means "not
		# configured", which must resolve to the default, not to "off".
		settings[field] = int(DEFAULTS[field] if value is None else value)

	position = doc.get("language_switcher_position")
	settings["language_switcher_position"] = position or DEFAULTS["language_switcher_position"]

	return settings
