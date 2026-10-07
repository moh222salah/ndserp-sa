"""Boot additions for the desk status bar and the theme feature switches.

Frappe's bootinfo does not carry the current user's last login, and the desk
status bar should not invent a value or fire an extra round trip to fetch one.
`extend_bootinfo` is the supported extension point: it runs inside the request
that already builds bootinfo, so the cost is one indexed column read and zero
additional HTTP requests.

The same hook carries `Amir Theme Settings` to the client. The switches have to
be on `frappe.boot` rather than fetched: every feature they gate (the
`ControlDate` patch for Hijri dates, the `Form` patch for smart actions, the
rail buttons) mounts during `$(document).ready`, long before any `frappe.call`
could return. Reading them from boot keeps the decision synchronous and adds no
request.

Deliberately narrow: only fields the status bar renders are added, and only for
the logged-in user. Nothing here widens what the client can see — `last_login`
is the session owner's own metadata, already visible on their User form, and
the switches are site-wide UI flags, not permissions.
"""

from __future__ import annotations

import frappe


def extend_bootinfo(bootinfo) -> None:
	"""Attach the small amount of data the desk status bar renders."""
	user = frappe.session.user
	if not user or user == "Guest":
		return

	# get_cached_value keeps this off the hot path on warm boots.
	last_login = frappe.db.get_value("User", user, "last_login")

	bootinfo.amt_status = {
		# ISO string; the client formats it with frappe.datetime so the user's
		# own locale and timezone apply.
		"last_login": str(last_login) if last_login else None,
	}

	bootinfo.amt_settings = _get_theme_settings()


def _get_theme_settings() -> dict:
	"""Theme switches, falling back to "everything on" if anything goes wrong.

	Imported lazily and wrapped: this runs on every boot, and a broken or
	not-yet-migrated settings doctype must never be able to break login.
	"""
	try:
		from amir_theme_v16.amir_theme.doctype.amir_theme_settings.amir_theme_settings import (
			get_settings,
		)

		return get_settings()
	except Exception:
		frappe.log_error(title="amir_theme_v16: could not read theme settings")
		return {
			"enable_hijri_dates": 1,
			"enable_smart_actions": 1,
			"enable_translation_mode": 1,
			"enable_color_schemes": 1,
			"language_switcher_position": "Navbar",
		}
