import frappe
from frappe.utils import today
from ndserp.api.utils import default_price_lists, error, get_stock, parse_paging, resolve_assignment


def _get_prices(item_codes, price_list):
	"""Return {item_code: {uom: rate}} for currently valid prices, latest valid_from wins."""
	if not item_codes:
		return {}

	rows = frappe.get_all(
		"Item Price",
		filters={"item_code": ["in", item_codes], "price_list": price_list},
		or_filters=[["valid_upto", "is", "not set"], ["valid_upto", ">=", today()]],
		fields=["item_code", "uom", "price_list_rate", "valid_from"],
		order_by="valid_from desc",
	)

	prices, now = {}, today()
	for r in rows:
		if r.valid_from and str(r.valid_from) > now:
			continue
		prices.setdefault(r.item_code, {}).setdefault(r.uom or "", r.price_list_rate)
	return prices


def _pick(prices, item_code, uom):
	"""Price for the item's stock UOM; fall back to a UOM-less price."""
	item_prices = prices.get(item_code, {})
	return item_prices.get(uom, item_prices.get("", 0.0))


@frappe.whitelist(methods=["GET"])
def get_items(search=None, page=1, page_size=50):
	page, page_size, paging_error = parse_paging(page, page_size)
	if paging_error:
		return error(417, "Invalid request", error_code="INVALID_REQUEST", errors=[paging_error])

	# 1. User's warehouse (same as login)
	_branch, warehouse, errors = resolve_assignment(frappe.session.user)
	if errors:
		frappe.clear_messages()
		return error(403, "Account setup incomplete", errors=errors)

	# 2. Stock in that warehouse (same as login)
	stock = get_stock(warehouse)

	if search:
		s = search.lower()
		stock = [i for i in stock if s in i["item_code"].lower() or s in (i["item_name"] or "").lower()]

	stock.sort(key=lambda i: (i["item_name"] or "").lower())
	start = (page - 1) * page_size
	page_items = stock[start:start + page_size]

	# 3. Prices for this page only
	codes = [i["item_code"] for i in page_items]
	selling_list, buying_list = default_price_lists()
	sell = _get_prices(codes, selling_list)
	buy = _get_prices(codes, buying_list)

	data = [
		{
			"item_code": i["item_code"],
			"item_name": i["item_name"],
			"unit": i["uom"],
			"cost_price": _pick(buy, i["item_code"], i["uom"]),
			"sales_price": _pick(sell, i["item_code"], i["uom"]),
			"available_qty": i["available_qty"],
		}
		for i in page_items
	]

	frappe.clear_messages()
	return {
		"success": True,
		"warehouse": warehouse,
		"page": page,
		"page_size": page_size,
		"total": len(stock),
		"data": data,
	}
