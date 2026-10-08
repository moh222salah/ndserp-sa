"""Server-side additions to web (non-desk) pages.

Why this exists
---------------
The branded login page is built in the browser by `login_brand.js`, which is
served through `web_include_js` - and Frappe renders `web_include_js` at the
BOTTOM of `<body>` (templates/base.html), not in `<head>`. So the sequence on
every logout was:

    1. server sends Frappe's stock login card
    2. browser paints it            <- the "it goes back to default" flash
    3. bottom-of-body script runs
    4. script fetches Login Page Settings over HTTP   <- the "I have to wait"
    5. settings arrive, the card is rebuilt as the branded one

Steps 2 and 4 are the whole complaint, and neither is fixable from inside the
script. Both are removed here, from `<head>`, before the first paint:

  * the settings are inlined into the document, so step 4 - a full network
    round trip on a page the user is staring at - disappears entirely;
  * a `amt-lb-pending` class hides the stock card until the script has replaced
    it, so step 2 never happens.

Fail-safe by construction: the class is only added when the branded login page
is actually enabled, and a timer in the same inline script removes it
unconditionally after 2.5s. If the bundle 404s, throws, or is blocked, the
worst case is a brief blank card followed by Frappe's own login form - never a
page the user cannot log in from.
"""

from __future__ import annotations

import frappe
from markupsafe import Markup

# The routes `login_brand.js:isLoginPage()` decorates. Kept in sync by hand;
# a path that is missing here simply keeps today's behaviour (flash + fetch),
# it does not break.
LOGIN_PATHS = ("/login", "/login-with-email-link")

# Long enough for the bundle to parse and run on a slow connection, short
# enough that a broken build is an annoyance rather than a lockout.
FAILSAFE_MS = 2500


def update_website_context(context):
	"""Inline login branding into the `<head>` for every Frappe login rendering."""
	if not _is_login_path(context):
		return

	try:
		from amir_theme_v16.amir_theme.doctype.login_page_settings.login_page_settings import (
			get_public_settings,
		)

		settings = get_public_settings()
	except Exception:
		# A cosmetic pre-load must never be able to break the login page.
		frappe.log_error(title="amir_theme_v16: could not preload login settings")
		return

	if not settings or not settings.get("enabled"):
		return

	# NOT `context.head_include`: frappe/www/login.html overrides
	# `{% block head_include %}` to inject its own stylesheet, which discards
	# whatever that variable holds. See templates/base_login.html.
	context.amt_login_head = Markup(_head_html(settings))
	context.base_template_path = "amir_theme_v16/templates/base_login.html"


def _is_login_path(context=None) -> bool:
	request = getattr(frappe.local, "request", None)
	path = getattr(request, "path", "") or ""
	# Frappe serves the login routes both with and without a trailing slash.
	if ("/" + path.strip("/")) in LOGIN_PATHS:
		return True

	# The email-link UI is hash-routed from "/", so the URL fragment is not sent
	# to the server. Detect the actual login template instead of trusting "/"
	# as a public homepage. This remains limited to the Login template.
	return bool(context and context.get("for_test") == "login.html")


def _head_html(settings: dict) -> str:
	# `</` inside a <script> body would close the tag early no matter how the
	# JSON is quoted - this is the standard escape, not defensive padding.
	payload = frappe.as_json(settings).replace("</", "<\\/")

	return f"""
<style id="amt-login-preload">
html.amt-lb-pending .login-content,
html.amt-lb-pending .page-card-container,
html.amt-lb-pending .for-login,
html.amt-lb-pending .for-forgot,
html.amt-lb-pending .for-login-with-email-link {{ visibility: hidden !important; }}
</style>
<script id="amt-login-settings">
window.__amtLoginSettings = {payload};
(function () {{
	var root = document.documentElement;
	root.classList.add("amt-lb-pending");
	// Unconditional release: whatever happens to the bundle below, the login
	// form becomes visible.
	setTimeout(function () {{ root.classList.remove("amt-lb-pending"); }}, {FAILSAFE_MS});
}})();
</script>
"""
