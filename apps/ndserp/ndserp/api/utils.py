import frappe
from frappe.utils.user import UserPermissions


# ── Response helpers ─────────────────────────────────────────────
def error(status_code, message, **extra):
	frappe.local.response["http_status_code"] = status_code
	return {"success": False, "message": message, **extra}


def parse_paging(page, page_size, max_size=500):
	"""(page, page_size, error): page >= 1, 1 <= page_size <= max_size; error is a message or None."""
	try:
		return max(int(page), 1), min(max(int(page_size), 1), max_size), None
	except (TypeError, ValueError):
		return 1, 50, "page and page_size must be whole numbers"


# ── User helpers ─────────────────────────────────────────────────
def resolve_assignment(user):
	"""Read the user's single Branch + Warehouse from User Permission.
	Returns (branch, warehouse, errors)."""
	def pick(doctype):
		vals = frappe.get_all(
			"User Permission",
			filters={"user": user, "allow": doctype},
			pluck="for_value",
		)
		if len(vals) == 0:
			errors.append(f"No {doctype} permission assigned")
		elif len(vals) > 1:
			errors.append(f"Multiple {doctype} permissions found ({len(vals)})")
		return vals[0] if vals else None

	errors = []
	branch = pick("Branch")
	warehouse = pick("Warehouse")
	return branch, warehouse, errors


def get_api_credentials(user):
	"""Return (api_key, api_secret). Generates and stores the pair if missing.
	The plaintext secret is only available at generation time."""
	user_doc = frappe.get_doc("User", user)
	existing_secret = user_doc.get_password("api_secret") if user_doc.api_key else None
	if existing_secret:
		return user_doc.api_key, existing_secret

	api_secret = frappe.generate_hash(length=15)
	if not user_doc.api_key:
		user_doc.api_key = frappe.generate_hash(length=15)

	user_doc.api_secret = api_secret
	user_doc.save(ignore_permissions=True)
	frappe.db.commit()

	return user_doc.api_key, api_secret


def get_permitted_doctypes(user: str) -> list[dict]:
	"""Doctypes the user can Read or Create (permlevel 0, via roles or shares)."""
	perms = UserPermissions(user)
	perms.build_permissions()

	can_read = set(perms.can_read)
	can_create = set(perms.can_create)  # excludes child tables, singles, "User Cannot Create"

	return [
		{
			"doctype": dt,
			"read": dt in can_read,
			"create": dt in can_create,
		}
		for dt in sorted(can_read | can_create)
	]


# ── Company / stock helpers ──────────────────────────────────────
def get_company(warehouse):
	"""Company that owns the user's warehouse (Warehouse.company is mandatory)."""
	return frappe.db.get_value("Warehouse", warehouse, "company")


def default_price_lists():
	"""Selling / buying price lists from Selling & Buying Settings."""
	selling = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	buying = frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"
	return selling, buying


def get_stock(warehouse):
	bins = frappe.get_all(
		"Bin",
		filters={"warehouse": warehouse, "actual_qty": [">", 0]},
		fields=["item_code", "actual_qty", "reserved_qty", "projected_qty"],
	)
	if not bins:
		return []

	items = frappe.get_all(
		"Item",
		filters={"name": ["in", [b.item_code for b in bins]]},
		fields=["name", "item_name", "stock_uom"],
	)
	item_map = {i.name: i for i in items}

	return [
		{
			"item_code": b.item_code,
			"item_name": item_map.get(b.item_code, {}).get("item_name"),
			"uom": item_map.get(b.item_code, {}).get("stock_uom"),
			"actual_qty": b.actual_qty,
			"reserved_qty": b.reserved_qty,
			"available_qty": (b.actual_qty or 0) - (b.reserved_qty or 0),
		}
		for b in bins
	]
