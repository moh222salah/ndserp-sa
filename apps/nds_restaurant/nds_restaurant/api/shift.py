# Copyright (c) 2026, NDS and contributors
# License: MIT

"""P7: daily order numbers, the daily-close rule, payment reconciliation and (P7b) shifts from the POS.

Every helper tolerates sites without the P7 schema (shared bench with unmigrated sites).
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now, now_datetime, today

COUNTER = "NDS Order Counter"
NO_RESET_DATE = "1900-01-01"


# ---------------------------------------------------------------------------
# P7-T2: daily order number
# ---------------------------------------------------------------------------


def next_order_no(pos_profile):
	"""Next order number for the profile, atomically (row lock on the counter row).

	With Reset Order Number Daily on, the counter row is keyed by (profile, today); otherwise by
	(profile, 1900-01-01) so numbers keep increasing. Returns None on sites without the counter.
	"""
	if not pos_profile or not frappe.db.table_exists(COUNTER):
		return None
	reset = 0
	if frappe.get_meta("POS Profile").has_field("custom_reset_order_number_daily"):
		reset = cint(frappe.db.get_value("POS Profile", pos_profile, "custom_reset_order_number_daily"))
	day = today() if reset else NO_RESET_DATE
	name = f"{pos_profile}-{day}"
	stamp = now()
	user = frappe.session.user
	# INSERT IGNORE: two tills creating the first order of the day at once both succeed here,
	# and the row lock below serialises them.
	frappe.db.sql(
		"""INSERT IGNORE INTO `tabNDS Order Counter`
			(name, creation, modified, owner, modified_by, docstatus, idx, pos_profile, counter_date, last_no)
		VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s, 0)""",
		(name, stamp, stamp, user, user, pos_profile, day),
	)
	last = frappe.db.sql("SELECT last_no FROM `tabNDS Order Counter` WHERE name=%s FOR UPDATE", name)
	number = cint(last[0][0] if last else 0) + 1
	frappe.db.sql(
		"UPDATE `tabNDS Order Counter` SET last_no=%s, modified=%s, modified_by=%s WHERE name=%s",
		(number, stamp, user, name),
	)
	return number


def assign_order_no(doc):
	"""Assign custom_daily_order_no once (first save of a new invoice)."""
	if not doc.meta.has_field("custom_daily_order_no") or cint(doc.get("custom_daily_order_no")):
		return
	number = next_order_no(doc.pos_profile)
	if number:
		doc.custom_daily_order_no = number


# ---------------------------------------------------------------------------
# P7-T3: previous day must be closed
# ---------------------------------------------------------------------------


def daily_close_required(pos_profile):
	if not pos_profile or not frappe.get_meta("POS Profile").has_field("custom_daily_pos_close"):
		return False
	return bool(cint(frappe.db.get_value("POS Profile", pos_profile, "custom_daily_pos_close")))


def stale_opening(pos_profile, exclude=None):
	"""An Open POS Opening Entry of this profile that started before today."""
	filters = {
		"pos_profile": pos_profile,
		"status": "Open",
		"docstatus": 1,
		"period_start_date": ["<", today()],
	}
	if exclude:
		filters["name"] = ["!=", exclude]
	for name in frappe.get_all("POS Opening Entry", filters=filters, pluck="name", order_by="period_start_date asc"):
		if not sub_closed(name):
			return name
	return None


def assert_previous_day_closed(pos_profile, exclude=None):
	if daily_close_required(pos_profile) and stale_opening(pos_profile, exclude=exclude):
		frappe.throw(_("Previous day POS not closed"), title=_("Daily POS Close"))


def assert_opening_is_today(opening_name, pos_profile):
	"""Orders may not be taken against an opening from an earlier date when daily close is on."""
	if not opening_name or not daily_close_required(pos_profile):
		return
	start = frappe.db.get_value("POS Opening Entry", opening_name, "period_start_date")
	if start and getdate(start) < getdate(today()):
		frappe.throw(_("Previous day POS not closed"), title=_("Daily POS Close"))


# ---------------------------------------------------------------------------
# P7-T1/T4: cashier invoices and payment reconciliation
# ---------------------------------------------------------------------------


def cashier_field():
	return "custom_cashier" if frappe.get_meta("POS Invoice").has_field("custom_cashier") else "owner"


def cashier_invoices(user, pos_profile, since):
	"""Submitted POS Invoices this user took payment for since the opening started."""
	field = cashier_field()  # one of two fixed column names
	return frappe.db.sql(
		f"""SELECT name, posting_date, grand_total, customer, net_total, total_qty, change_amount
		FROM `tabPOS Invoice`
		WHERE `{field}`=%(user)s AND pos_profile=%(profile)s AND docstatus=1
			AND TIMESTAMP(posting_date, posting_time) >= %(since)s
		ORDER BY posting_date ASC, posting_time ASC, name ASC""",
		{"user": user, "profile": pos_profile, "since": get_datetime(since)},
		as_dict=True,
	)


def cashier_drafts(user, pos_profile):
	"""Drafts that block a closing: taken by this user as cashier, or created by them."""
	or_filters = {"owner": user}
	if cashier_field() == "custom_cashier":
		or_filters = [["owner", "=", user], ["custom_cashier", "=", user]]
	return frappe.get_all(
		"POS Invoice",
		filters={"pos_profile": pos_profile, "docstatus": 0},
		or_filters=or_filters,
		pluck="name",
	)


def _cash_modes(modes):
	if not modes:
		return set()
	return set(frappe.get_all("Mode of Payment", filters={"name": ["in", list(modes)], "type": "Cash"}, pluck="name"))


def payment_reconciliation(opening_name, invoice_names, entered=None, include_opening=True):
	"""Rows per mode of payment: opening, expected (= opening + payments − change on cash), closing, difference.

	`entered` maps mode of payment -> a closing amount the user typed; it is preserved, otherwise
	the closing amount defaults to the expected amount.
	"""
	entered = entered or {}
	opening = frappe.get_doc("POS Opening Entry", opening_name)
	opening_amounts = {}
	# a sub-cashier closing on the main cashier's opening doesn't hold its float
	for row in (opening.get("balance_details") or []) if include_opening else []:
		opening_amounts[row.mode_of_payment] = opening_amounts.get(row.mode_of_payment, 0) + flt(row.opening_amount)
	paid = {}
	change = 0
	if invoice_names:
		for row in frappe.db.sql(
			"""SELECT mode_of_payment, SUM(amount) FROM `tabSales Invoice Payment`
			WHERE parenttype='POS Invoice' AND parent IN %(names)s GROUP BY mode_of_payment""",
			{"names": tuple(invoice_names)},
		):
			paid[row[0]] = flt(row[1])
		change = flt(
			frappe.db.sql(
				"SELECT SUM(change_amount) FROM `tabPOS Invoice` WHERE name IN %(names)s",
				{"names": tuple(invoice_names)},
			)[0][0]
		)
	modes = list(dict.fromkeys(list(opening_amounts) + list(paid)))
	cash = _cash_modes(modes)
	change_mode = next((m for m in modes if m in cash), None)
	rows = []
	for mode in modes:
		expected = flt(opening_amounts.get(mode)) + flt(paid.get(mode))
		if mode == change_mode:
			expected -= change
		closing = entered.get(mode)
		closing = expected if closing is None else flt(closing)
		rows.append(
			{
				"mode_of_payment": mode,
				"opening_amount": flt(opening_amounts.get(mode)),
				"expected_amount": expected,
				"closing_amount": closing,
				"difference": closing - expected,
			}
		)
	return rows


# ---------------------------------------------------------------------------
# P7-T5: opening and closing from the POS
# ---------------------------------------------------------------------------

SUB_CLOSING = "Sub POS Closing"


def sub_closed(opening_name):
	"""An opening its own user closed with a Sub POS Closing (pre-v16 sub-cashier openings) counts as closed."""
	if not frappe.db.table_exists(SUB_CLOSING):
		return False
	owner = frappe.db.get_value("POS Opening Entry", opening_name, "user")
	return bool(
		frappe.db.exists(SUB_CLOSING, {"pos_opening_entry": opening_name, "docstatus": 1, "user": owner})
	)


def _last_sub_close(filters):
	"""Latest period_end_date of the matching Sub POS Closings (None if there are none)."""
	rows = frappe.get_all(SUB_CLOSING, filters=filters, fields=["period_end_date"], order_by="period_end_date desc", limit=1)
	return rows[0].period_end_date if rows else None


def sub_period_start(opening_name, user, exclude=None):
	"""Where a sub-cashier's next Sub POS Closing starts: their last one on this opening, or the opening."""
	filters = {"pos_opening_entry": opening_name, "docstatus": 1, "user": user}
	if exclude:
		filters["name"] = ["!=", exclude]
	last = None
	if frappe.db.table_exists(SUB_CLOSING):
		last = _last_sub_close(filters)
	return last or frappe.db.get_value("POS Opening Entry", opening_name, "period_start_date")


def unclosed_sub_cashiers(opening_name, pos_profile, main_users):
	"""Non-main users who took payments on this shift after their last Sub POS Closing."""
	if cashier_field() != "custom_cashier" or not frappe.db.table_exists(SUB_CLOSING):
		return []
	start = frappe.db.get_value("POS Opening Entry", opening_name, "period_start_date")
	rows = frappe.db.sql(
		"""SELECT custom_cashier, MAX(TIMESTAMP(posting_date, posting_time)) AS last_paid
		FROM `tabPOS Invoice`
		WHERE pos_profile=%(profile)s AND docstatus=1 AND IFNULL(custom_cashier, '')!=''
			AND TIMESTAMP(posting_date, posting_time) >= %(start)s
		GROUP BY custom_cashier""",
		{"profile": pos_profile, "start": get_datetime(start)},
		as_dict=True,
	)
	pending = []
	for row in rows:
		if row.custom_cashier in main_users:
			continue
		closed_until = _last_sub_close({"pos_opening_entry": opening_name, "docstatus": 1, "user": row.custom_cashier})
		if not closed_until or get_datetime(row.last_paid) > get_datetime(closed_until):
			pending.append(row.custom_cashier)
	return pending


def user_opening(user, pos_profile):
	"""The user's own open POS Opening Entry for the profile ({name, period_start_date}) or None."""
	rows = frappe.get_all(
		"POS Opening Entry",
		filters={"user": user, "pos_profile": pos_profile, "status": "Open", "docstatus": 1},
		fields=["name", "period_start_date"],
		order_by="period_start_date desc",
	)
	for row in rows:
		if not sub_closed(row.name):
			return row
	return None


def profile_opening(pos_profile):
	"""Any open opening of the profile (multi-cashier mode lets captains work on the main shift)."""
	for name in frappe.get_all(
		"POS Opening Entry",
		filters={"pos_profile": pos_profile, "status": "Open", "docstatus": 1},
		pluck="name",
		order_by="period_start_date desc",
	):
		if not sub_closed(name):
			return name
	return None


def closing_kind(profile_doc, user):
	"""Sub POS Closing for a sub-cashier in multi-cashier mode, otherwise ERPNext's POS Closing Entry."""
	if not cint(profile_doc.get("custom_enable_multiple_cashier")) or not frappe.db.table_exists(SUB_CLOSING):
		return "POS Closing Entry"
	mains = [r.user for r in profile_doc.applicable_for_users if r.get("custom_main_cashier")]
	if mains and user not in mains:
		return SUB_CLOSING
	return "POS Closing Entry"


def _shift_profile(pos_profile):
	"""Profile access plus the billing right (cashiers and managers run shifts; captains don't)."""
	from nds_restaurant.api.pos import _assert_pos_profile_access
	from nds_restaurant.utils.access import get_capabilities

	if frappe.session.user == "Guest":
		frappe.throw(_("Login required"), frappe.PermissionError)
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))
	_assert_pos_profile_access(pos_profile)
	profile = frappe.get_doc("POS Profile", pos_profile)
	caps = get_capabilities(frappe.session.user, profile)
	if not (caps.get("can_bill") or caps.get("is_manager")):
		frappe.throw(_("Only cashiers and managers can open or close a POS shift"), frappe.PermissionError)
	return profile


def _amounts(value):
	"""{mode_of_payment: amount} from a dict, a list of rows or their JSON."""
	if isinstance(value, str):
		value = json.loads(value) if value.strip() else {}
	out = {}
	if isinstance(value, list):
		for row in value:
			row = row or {}
			mode = row.get("mode_of_payment")
			if not mode:
				continue
			amount = row.get("amount")
			if amount is None:
				amount = row.get("opening_amount", row.get("closing_amount"))
			out[mode] = flt(amount)
	elif isinstance(value, dict):
		out = {k: flt(v) for k, v in value.items() if k}
	for mode, amount in out.items():
		if amount < 0:
			frappe.throw(_("Amount for {0} can't be negative").format(mode))
	return out


def _profile_modes(profile):
	"""Profile modes of payment that have a default account for the company (ERPNext requires one)."""
	modes = []
	for row in profile.payments:
		mode = row.mode_of_payment
		if not mode or mode in modes:
			continue
		if frappe.db.get_value(
			"Mode of Payment Account", {"parent": mode, "company": profile.company}, "default_account"
		):
			modes.append(mode)
	return modes


@frappe.whitelist(methods=["POST"])
def create_opening(pos_profile, balance_details=None):
	"""P7-T5: insert and submit a POS Opening Entry for the session user (hooks and P7-T3 still run)."""
	profile = _shift_profile(pos_profile)
	user = frappe.session.user
	existing = user_opening(user, pos_profile)
	if existing:
		frappe.throw(_("You already have an open POS shift ({0})").format(existing.name))
	amounts = _amounts(balance_details)
	modes = _profile_modes(profile)
	if not modes:
		frappe.throw(_("No mode of payment of POS Profile {0} has a default account").format(pos_profile))
	unknown = [m for m, amount in amounts.items() if m not in modes and amount]
	if unknown:
		frappe.throw(_("Mode of payment {0} is not in POS Profile {1}").format(", ".join(unknown), pos_profile))
	doc = frappe.new_doc("POS Opening Entry")
	doc.period_start_date = now_datetime()
	doc.posting_date = today()
	doc.user = user
	doc.pos_profile = pos_profile
	doc.company = profile.company
	for mode in modes:
		doc.append("balance_details", {"mode_of_payment": mode, "opening_amount": amounts.get(mode, 0)})
	# the API above is the permission gate (cashier roles have no Desk rights on POS Opening Entry)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return {"name": doc.name, "period_start_date": str(doc.period_start_date)}


def _open_shift(pos_profile, kind):
	"""The shift being closed: the user's own opening, or (sub-cashier) the main cashier's opening.

	ERPNext v16 allows one open POS Opening Entry per profile, so sub-cashiers work and close on it.
	Returns {name, period_start_date, user, since, include_opening}.
	"""
	user = frappe.session.user
	opening = user_opening(user, pos_profile)
	if opening:
		name = opening.name
	elif kind == SUB_CLOSING:
		name = profile_opening(pos_profile)
	else:
		name = None
	if not name:
		frappe.throw(_("You have no open POS shift"))
	row = frappe._dict(
		frappe.db.get_value("POS Opening Entry", name, ["name", "period_start_date", "user"], as_dict=True)
	)
	own = row.user == user
	row.include_opening = own
	row.since = row.period_start_date if own else sub_period_start(name, user)
	return row


@frappe.whitelist()
def get_closing_preview(pos_profile):
	"""P7-T5: expected amounts per mode of payment for the session user's open shift."""
	profile = _shift_profile(pos_profile)
	user = frappe.session.user
	kind = closing_kind(profile, user)
	opening = _open_shift(pos_profile, kind)
	invoices = cashier_invoices(user, pos_profile, opening.since)
	return {
		"opening": opening.name,
		"period_start_date": str(opening.since),
		"kind": kind,
		"drafts": cashier_drafts(user, pos_profile),
		"invoice_count": len(invoices),
		"grand_total": sum(flt(i.grand_total) for i in invoices),
		"payments": payment_reconciliation(
			opening.name, [i.name for i in invoices], include_opening=opening.include_opening
		),
	}


@frappe.whitelist(methods=["POST"])
def _throw_closing_rights():
	frappe.throw(
		_(
			"Closing this shift creates the consolidated Sales Invoice, which needs Sales Invoice read/create/submit"
			" rights (for example the Accounts User role). Ask a manager to close the shift."
		),
		frappe.PermissionError,
	)


def close_shift(pos_profile, closing_amounts=None):
	"""P7-T5: close the session user's shift.

	A sub-cashier in multi-cashier mode submits a Sub POS Closing; everyone else gets ERPNext's
	POS Closing Entry (make_closing_entry_from_opening), with the reconciliation filled from the
	invoices they took payment for and the amounts they counted.
	"""
	profile = _shift_profile(pos_profile)
	user = frappe.session.user
	kind = closing_kind(profile, user)
	opening = _open_shift(pos_profile, kind)
	drafts = cashier_drafts(user, pos_profile)
	if drafts:
		frappe.throw(_("Submit/Delete Draft Invoices: {0}").format(", ".join(drafts)), title=_("Draft Invoices"))
	entered = _amounts(closing_amounts)
	if kind == SUB_CLOSING:
		doc = frappe.new_doc(SUB_CLOSING)
		doc.pos_opening_entry = opening.name
		doc.user = user
		for mode, amount in entered.items():
			doc.append("payment_reconciliation", {"mode_of_payment": mode, "closing_amount": amount})
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		return {"doctype": SUB_CLOSING, "name": doc.name}

	from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

	# ERPNext reads the shift's invoices with Sales Invoice read rights, then merges them into a
	# Sales Invoice as the closing user
	if not frappe.has_permission("Sales Invoice", "read"):
		_throw_closing_rights()
	closing = make_closing_entry_from_opening(frappe.get_doc("POS Opening Entry", opening.name))
	if closing.get("pos_invoices") and not (
		frappe.has_permission("Sales Invoice", "create") and frappe.has_permission("Sales Invoice", "submit")
	):
		_throw_closing_rights()
	invoices = cashier_invoices(user, pos_profile, opening.period_start_date)
	closing.set("payment_reconciliation", payment_reconciliation(opening.name, [i.name for i in invoices], entered))
	closing.flags.ignore_permissions = True
	closing.insert()
	closing.submit()
	return {"doctype": "POS Closing Entry", "name": closing.name}
