# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
import os
from urllib.parse import quote

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(frappe.local.request.path)
		raise frappe.Redirect

	csrf_token = frappe.sessions.get_csrf_token()
	context.csrf_token = csrf_token
	context.boot = {
		"sitename": frappe.local.site,
		"user": frappe.session.user,
		"csrf_token": csrf_token,
	}
	
	# Cache busting version
	try:
		bundle_path = frappe.get_app_path("nds_restaurant", "public", "kotdisplay", "assets", "index.js")
		context.build_version = int(os.path.getmtime(bundle_path))
	except (OSError, ValueError):
		context.build_version = int(frappe.utils.now_datetime().timestamp())
	
	return context
