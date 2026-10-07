# Copyright (c) 2026, NDS and contributors
# License: MIT

import frappe
import os
from urllib.parse import quote, unquote

from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(frappe.local.request.path)
		raise frappe.Redirect

	# P4-T7: the KDS needs an NDS role and, for a unit, a seat on that unit's branch.
	from nds_restaurant.utils.access import assert_kds_access, has_kds_role

	unit = unquote((frappe.form_dict.get("app_path") or "").split("/")[0]).strip()
	if unit and frappe.db.exists("NDS Production Unit", unit):
		assert_kds_access(unit)
	elif not has_kds_role():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

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
