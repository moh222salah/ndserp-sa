# Copyright (c) 2026, amir_theme_v16
# License: MIT

import frappe
from frappe.model.document import Document


class LoginPageSettings(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_public_settings():
	"""Public read-only view of the login-page settings for guests."""
	try:
		doc = frappe.get_cached_doc("Login Page Settings", "Login Page Settings")
	except Exception:
		return {"enabled": 0}

	if not doc.get("enabled"):
		return {"enabled": 0}

	def url(value):
		if not value:
			return ""
		if value.startswith("/") or value.startswith("http"):
			return value
		return "/" + value.lstrip("/")

	return {
		"enabled": 1,
		"company_name": doc.get("company_name") or "",
		"company_name_ar": doc.get("company_name_ar") or "",
		"tagline": doc.get("tagline") or "",
		"tagline_ar": doc.get("tagline_ar") or "",
		"logo": url(doc.get("logo")),
		"background_image": url(doc.get("background_image")),
		"accent_color": doc.get("accent_color") or "",
		"panel_position": doc.get("panel_position") or "right",
		"description": doc.get("description") or "",
		"description_ar": doc.get("description_ar") or "",
		"address": doc.get("address") or "",
		"address_ar": doc.get("address_ar") or "",
		"phone": doc.get("phone") or "",
		"email": doc.get("email") or "",
		"website": doc.get("website") or "",
		"show_social": 1 if doc.get("show_social") else 0,
		"facebook_url": doc.get("facebook_url") or "",
		"twitter_url": doc.get("twitter_url") or "",
		"linkedin_url": doc.get("linkedin_url") or "",
		"instagram_url": doc.get("instagram_url") or "",
	}
