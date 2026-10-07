import frappe
from frappe.auth import LoginManager

from ndserp.api.utils import (
	error,
	get_api_credentials,
	get_company,
	get_permitted_doctypes,
	get_stock,
	resolve_assignment,
)


# ── Endpoint ─────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def login(user, password):
	# 1. Verify credentials WITHOUT committing the login yet
	lm = LoginManager()
	try:
		lm.authenticate(user=user, pwd=password)
	except frappe.AuthenticationError:
		return error(401, "Invalid credentials")

	# 2. Validate account setup BEFORE logging in
	branch, warehouse, errors = resolve_assignment(user)
	if errors:
		return error(403, "Account setup incomplete", errors=errors)

	# 3. Everything checks out — now commit the login and issue tokens
	lm.post_login()
	api_key, api_secret = get_api_credentials(user)

	# 4. Response
	frappe.clear_messages()
	return {
		"success": True,
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name"),
		"api_key": api_key,
		"api_secret": api_secret,
		"company": get_company(warehouse),
		"branch": branch,
		"stock_warehouse": warehouse,
		"stock": get_stock(warehouse),
		"permitted_doctypes": get_permitted_doctypes(user),
	}
