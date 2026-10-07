"""Workspace visibility policy for ndserp.

After install / migrate, only Ndserp (module) workspaces stay visible. Every
other Frappe/ERPNext/HRMS workspace is set to `public = 0, is_hidden = 1` so
the desk sidebar and apps screen show the Arabic NDS sections only.

This module replaces six one-off scripts (hide_all.py, hide_all_final.py,
final_fix.py, fix_workspaces.py, hide_english.py, reset_sidebar.py) that did
roughly the same thing with hardcoded user emails and raw SQL against the
`tabHas Role` child table.

Usage
-----
    bench --site <site> execute ndserp.setup.workspace_policy.apply
    bench --site <site> execute ndserp.setup.workspace_policy.revert
    bench --site <site> execute ndserp.setup.workspace_policy.status

Opt out of the automatic hide (keep standard workspaces visible):

    bench --site <site> set-config -g ndserp_workspace_policy 0
"""

import frappe

APP_NAME = "ndserp"
APP_MODULE = "Ndserp"  # kept for anything still keying off the original single module by name
SITE_CONFIG_KEY = "ndserp_workspace_policy"

# Ndserp POS workspace (requires pos_next). Replaces the English POSNext
# workspace shipped by that app when both are installed on the same site.
POS_WORKSPACE = "نقاط البيع NDS ERP"
OLD_POS_WORKSPACES = ("POSNext",)

# Ndserp HR workspace (requires hrms). Replaces the English HR / Frappe HR
# desk tiles; the broken "HR NDS" sidebar that only linked to Workspace "HR"
# is rebuilt from this workspace's Link Cards via sidebar_builder.
HR_WORKSPACE = "HR NDS"
OLD_HR_WORKSPACES = ("HR", "Employee Lifecycle", "Leaves", "Expenses", "Recruitment", "Performance", "Tenure", "HR Setup", "Shift & Attendance", "Payroll", "Tax & Benefits", "Salary Payout")

# The order the Ndserp sections must appear in, everywhere they are listed:
# master files -> accounts -> stock -> sales -> purchasing -> assets -> HR -> POS.
#
# Two different fields drive two different surfaces and both are set from this
# one list (see `ensure_order`):
#   * `Workspace.sequence_id`  -> order in the workspace sidebar / switcher
#   * `Desktop Icon.idx`       -> order of the tiles on the apps screen and of
#                                 the sibling list in the sidebar header
#
# Anything belonging to the app but missing from this list keeps a stable place
# after it (sorted by name), so adding another workspace can never scramble
# the ones below - it just lands at the end until it is named here.
WORKSPACE_ORDER = [
	"الملفات الرئيسية NDS ERP",
	"حسابات NDS ERP",
	"مخازن NDS ERP",
	"المبيعات NDS ERP",
	"المشتريات NDS ERP",
	"الاصول NDS ERP",
	HR_WORKSPACE,
	POS_WORKSPACE,
]

# Desktop Icon.idx is a flat, site-wide sort key: Frappe's own icons occupy
# 0-101 ("My Workspaces" is 101). Starting the app's block well past that keeps
# the Ndserp tiles contiguous and in order instead of interleaving with ERPNext's,
# which is what happened while they all sat at the default idx = 0 and fell back
# to an alphabetical tie-break.
DESKTOP_ICON_IDX_BASE = 200

# Workspace.sequence_id is a float and only compared within the sidebar list,
# so any increasing run works; 40+ matches what the fixture already ships.
WORKSPACE_SEQUENCE_BASE = 40


def is_enabled() -> bool:
	"""Policy is on by default so any site with ndserp only shows NDS workspaces.

	Opt out per site with `bench --site <site> set-config -g ndserp_workspace_policy 0`,
	then `execute ndserp.setup.workspace_policy.revert` to restore standard ones.
	"""
	return bool(frappe.conf.get(SITE_CONFIG_KEY, 1))


def get_app_modules() -> list[str]:
	"""Every Module Def that belongs to the ndserp app - today that's just
	"Ndserp", but this is what makes the whole role-scoping/icon/sidebar
	system in `workspace_scope.py` generalise automatically the day someone
	adds a second module (e.g. an "HR" Module Def with `app_name = "ndserp"`)
	instead of only ever recognising the literal string "Ndserp". See
	[[ndserp-app]] for the "role X + module Y, same pattern" request this
	was built for.
	"""
	return frappe.get_all("Module Def", filters={"app_name": APP_NAME}, pluck="name")


def get_app_workspaces() -> list[str]:
	modules = get_app_modules()
	if not modules:
		return []
	return frappe.get_all("Workspace", filters={"module": ["in", modules]}, pluck="name")


def get_foreign_workspaces() -> list[str]:
	modules = get_app_modules()
	filters = {"module": ["not in", modules]} if modules else {}
	return frappe.get_all("Workspace", filters=filters, pluck="name")


def is_pos_next_installed() -> bool:
	return "pos_next" in frappe.get_installed_apps()


# Desk App / Folder tiles that survive workspace hide (they are not Workspace
# Link icons). Explicit list so Framework / Frappe Framework / Accounts and
# similar roots are always removed even if a child Link somehow stays.
FOREIGN_DESKTOP_ROOTS = (
	"Framework",
	"Frappe Framework",
	"Accounts",
	"Frappe HR",
	"ERPNext",
)

# Extra desk tiles to keep alongside Ndserp workspaces. HR NDS becomes a real
# module=Ndserp Workspace via ensure_hr_workspace(); keep the label here so a
# leftover icon is not wiped if the workspace row is briefly missing mid-migrate.
#
# ZATCA (ksa_compliance) is kept when that app is installed: ndserp ships the
# ZATCA Tax Invoice print format and Phase 1 helpers, so Saudi sites need the
# tile. Hiding it left a Workspace Sidebar whose first link points at a
# workspace absent from `frappe.workspaces`, so desk navigated to `/desk/undefined`.
ZATCA_WORKSPACE = "ZATCA"

KEEP_DESKTOP_ICONS = (
	HR_WORKSPACE,
	ZATCA_WORKSPACE,
)


def is_hrms_installed() -> bool:
	return "hrms" in frappe.get_installed_apps()


def is_ksa_compliance_installed() -> bool:
	return "ksa_compliance" in frappe.get_installed_apps()


def get_keep_desktop_icons() -> tuple[str, ...]:
	"""Labels that stay visible with Ndserp tiles (depends on installed apps)."""
	keep = [HR_WORKSPACE]
	if is_ksa_compliance_installed():
		keep.append(ZATCA_WORKSPACE)
	return tuple(keep)


def _hide_desktop_icons(label: str) -> int:
	"""Mark every Desktop Icon for `label` as hidden (any icon_type)."""
	changed = 0
	for icon_name in frappe.get_all("Desktop Icon", filters={"label": label}, pluck="name"):
		if not frappe.db.get_value("Desktop Icon", icon_name, "hidden"):
			frappe.db.set_value("Desktop Icon", icon_name, "hidden", 1, update_modified=False)
			changed += 1
	return changed


def _show_desktop_icons(label: str) -> int:
	changed = 0
	for icon_name in frappe.get_all("Desktop Icon", filters={"label": label}, pluck="name"):
		if frappe.db.get_value("Desktop Icon", icon_name, "hidden"):
			frappe.db.set_value("Desktop Icon", icon_name, "hidden", 0, update_modified=False)
			changed += 1
	return changed


def hide_foreign_desktop_icons(verbose: bool = True) -> dict:
	"""Leave only Ndserp (+ get_keep_desktop_icons()) tiles on the desk apps screen.

	Hides App/Folder roots (Framework, Frappe Framework, Accounts, …), their
	child Link icons, My Workspaces, and any other Desktop Icon whose label is
	not an Ndserp workspace or an explicit keep entry. Idempotent.
	"""
	keep = set(get_app_workspaces()) | set(get_keep_desktop_icons())
	# POS / HR tiles stay hidden when their required apps are missing.
	if not is_pos_next_installed():
		keep.discard(POS_WORKSPACE)
	if not is_hrms_installed():
		keep.discard(HR_WORKSPACE)

	# If a kept label is also a Workspace, make sure it stays visible.
	for name in get_keep_desktop_icons():
		if frappe.db.exists("Workspace", name):
			_set(name, public=1, is_hidden=0)


	hidden_labels: list[str] = []
	shown_labels: list[str] = []

	for icon in frappe.get_all(
		"Desktop Icon",
		fields=["name", "label", "parent_icon", "hidden"],
	):
		keep_icon = icon.label in keep and not icon.parent_icon
		want_hidden = 0 if keep_icon else 1
		if int(icon.hidden or 0) == want_hidden:
			continue
		frappe.db.set_value(
			"Desktop Icon", icon.name, "hidden", want_hidden, update_modified=False
		)
		(shown_labels if keep_icon else hidden_labels).append(icon.label)

	# Belt-and-suspenders for the named roots the desk still showed after
	# workspace-only hiding (App / Folder types, not Workspace Links).
	for label in FOREIGN_DESKTOP_ROOTS:
		if label in keep:
			continue
		_hide_desktop_icons(label)
		for child in frappe.get_all(
			"Desktop Icon", filters={"parent_icon": label}, pluck="label"
		):
			if child in keep:
				continue
			_hide_desktop_icons(child)

	if hidden_labels or shown_labels:
		frappe.db.commit()
		frappe.clear_cache()

	if verbose:
		print(
			f"ndserp: desktop icons hidden={len(hidden_labels)} shown={len(shown_labels)} "
			f"(kept {len(keep)} tiles)"
		)

	return {"hidden": hidden_labels, "shown": shown_labels, "kept": sorted(keep)}


def ensure_pos_workspace(verbose: bool = True) -> dict:
	"""Wire the Ndserp POS workspace to `pos_next` when that app is installed.

	* pos_next installed: keep `نقاط البيع NDS ERP` public, hide the English
	  `POSNext` workspace (and its desktop tile) so users only see the Arabic
	  Ndserp section with icon + sidebar.
	* pos_next missing: hide the Ndserp POS workspace (its DocType links would
	  be broken) and leave any leftover POSNext alone.

	Idempotent. Safe to call from after_install / after_migrate.
	"""
	result = {
		"pos_next_installed": is_pos_next_installed(),
		"shown": [],
		"hidden": [],
		"removed_sidebars": [],
	}

	if result["pos_next_installed"]:
		if frappe.db.exists("Workspace", POS_WORKSPACE):
			if _set(POS_WORKSPACE, public=1, is_hidden=0):
				result["shown"].append(POS_WORKSPACE)
			_show_desktop_icons(POS_WORKSPACE)

		for name in OLD_POS_WORKSPACES:
			if not frappe.db.exists("Workspace", name):
				continue
			if _set(name, public=0, is_hidden=1):
				result["hidden"].append(name)
			_hide_desktop_icons(name)
			# Drop the old app's sidebar rail entry so dual-sidebar themes don't
			# keep advertising POSNext next to the new Arabic workspace.
			if frappe.db.exists("Workspace Sidebar", name):
				frappe.delete_doc("Workspace Sidebar", name, ignore_permissions=True, force=True)
				result["removed_sidebars"].append(name)
	elif frappe.db.exists("Workspace", POS_WORKSPACE):
		if _set(POS_WORKSPACE, public=0, is_hidden=1):
			result["hidden"].append(POS_WORKSPACE)
		_hide_desktop_icons(POS_WORKSPACE)

	frappe.db.commit()
	frappe.clear_cache()

	if verbose:
		state = "installed" if result["pos_next_installed"] else "not installed"
		print(
			f"ndserp: pos_next {state}; "
			f"shown={result['shown'] or '-'} hidden={result['hidden'] or '-'} "
			f"removed_sidebars={result['removed_sidebars'] or '-'}"
		)

	return result


def _hr_sections() -> list[tuple[str, list[tuple[str, str, str]]]]:
	"""Card sections for the HR NDS workspace: (card label, [(label, link_type, link_to)])."""
	return [
		(
			"الموظفين",
			[
				("Employee", "DocType", "Employee"),
				("Employee Group", "DocType", "Employee Group"),
				("Department", "DocType", "Department"),
				("Designation", "DocType", "Designation"),
				("Branch", "DocType", "Branch"),
				("Employment Type", "DocType", "Employment Type"),
				("Employee Grade", "DocType", "Employee Grade"),
			],
		),
		(
			"الحضور والورديات",
			[
				("Attendance", "DocType", "Attendance"),
				("Attendance Request", "DocType", "Attendance Request"),
				("Employee Checkin", "DocType", "Employee Checkin"),
				("Shift Type", "DocType", "Shift Type"),
				("Shift Assignment", "DocType", "Shift Assignment"),
			],
		),
		(
			"الإجازات",
			[
				("Leave Application", "DocType", "Leave Application"),
				("Compensatory Leave Request", "DocType", "Compensatory Leave Request"),
				("Leave Allocation", "DocType", "Leave Allocation"),
				("Leave Type", "DocType", "Leave Type"),
				("Leave Period", "DocType", "Leave Period"),
				("Leave Policy", "DocType", "Leave Policy"),
				("Holiday List", "DocType", "Holiday List"),
				("Employee Leave Balance", "Report", "Employee Leave Balance"),
			],
		),
		(
			"المصروفات",
			[
				("Expense Claim", "DocType", "Expense Claim"),
				("Employee Advance", "DocType", "Employee Advance"),
			],
		),
		(
			"الرواتب",
			[
				("Salary Slip", "DocType", "Salary Slip"),
				("Payroll Entry", "DocType", "Payroll Entry"),
				("Salary Structure", "DocType", "Salary Structure"),
				("Salary Structure Assignment", "DocType", "Salary Structure Assignment"),
				("Salary Component", "DocType", "Salary Component"),
			],
		),
		(
			"التوظيف ودورة حياة الموظف",
			[
				("Job Opening", "DocType", "Job Opening"),
				("Job Applicant", "DocType", "Job Applicant"),
				("Employee Onboarding", "DocType", "Employee Onboarding"),
				("Employee Separation", "DocType", "Employee Separation"),
			],
		),
		(
			"الإعدادات",
			[
				("HR Settings", "DocType", "HR Settings"),
			],
		),
	]


def _hr_shortcuts() -> list[tuple[str, str, str]]:
	"""(label, type, link_to) shortcuts shown on the HR NDS page."""
	return [
		("Employee", "DocType", "Employee"),
		("Attendance", "DocType", "Attendance"),
		("Leave Application", "DocType", "Leave Application"),
		("Expense Claim", "DocType", "Expense Claim"),
		("Salary Slip", "DocType", "Salary Slip"),
		("Payroll Entry", "DocType", "Payroll Entry"),
		("Employee Information", "Report", "Employee Information"),
	]


def _filter_existing_targets(
	rows: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
	"""Drop DocType/Report links whose target is not installed on this site."""
	out = []
	for label, link_type, link_to in rows:
		if link_type == "DocType" and not frappe.db.exists("DocType", link_to):
			continue
		if link_type == "Report" and not frappe.db.exists("Report", link_to):
			continue
		out.append((label, link_type, link_to))
	return out


def _build_hr_workspace_doc(doc):
	"""Fill an HR NDS Workspace doc with shortcuts, link cards and content JSON."""
	import json
	import secrets

	def _id() -> str:
		return secrets.token_urlsafe(8)[:10]

	doc.module = APP_MODULE
	doc.app = APP_NAME
	doc.public = 1
	doc.is_hidden = 0
	doc.icon = "users-round"
	doc.title = HR_WORKSPACE
	doc.label = HR_WORKSPACE

	shortcuts = _filter_existing_targets(_hr_shortcuts())
	doc.set("shortcuts", [])
	for label, link_type, link_to in shortcuts:
		doc.append(
			"shortcuts",
			{
				"label": label,
				"type": link_type,
				"link_to": link_to,
				"doc_view": "List",
			},
		)

	doc.set("links", [])
	card_names: list[str] = []
	for card_label, items in _hr_sections():
		existing = _filter_existing_targets(items)
		if not existing:
			continue
		card_names.append(card_label)
		doc.append(
			"links",
			{
				"type": "Card Break",
				"label": card_label,
				"link_count": len(existing),
			},
		)
		for label, link_type, link_to in existing:
			row = {
				"type": "Link",
				"label": label,
				"link_type": link_type,
				"link_to": link_to,
			}
			if link_type == "Report":
				row["is_query_report"] = 1
			doc.append("links", row)

	blocks = [
		{"id": _id(), "type": "header", "data": {"text": f'<span class="h4">{HR_WORKSPACE}</span>', "col": 12}},
	]
	for label, _link_type, _link_to in shortcuts:
		blocks.append(
			{"id": _id(), "type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
		)
	if card_names:
		blocks.append({"id": _id(), "type": "spacer", "data": {"col": 12}})
		for card_label in card_names:
			blocks.append(
				{"id": _id(), "type": "card", "data": {"card_name": card_label, "col": 4}}
			)
	doc.content = json.dumps(blocks)

	# Gate by the dedicated role (created in ensure_workspace_roles if needed).
	if not frappe.db.exists("Role", HR_WORKSPACE):
		frappe.get_doc({"doctype": "Role", "role_name": HR_WORKSPACE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
	doc.set("roles", [])
	doc.append("roles", {"role": HR_WORKSPACE})


def ensure_hr_workspace(verbose: bool = True) -> dict:
	"""Create / repair the Ndserp HR workspace and retire English HRMS tiles.

	The desk previously had a Desktop Icon + Workspace Sidebar named "HR NDS"
	whose only sidebar row linked to the stock (hidden) Workspace "HR" — so
	the tile appeared but navigating it did nothing useful. This builds a real
	`module = Ndserp` Workspace with Link Cards, then relies on
	`sidebar_builder.rebuild()` to regenerate the sidebar from those cards.

	Idempotent. Safe to call from after_install / after_migrate.
	"""
	result = {
		"hrms_installed": is_hrms_installed(),
		"created": False,
		"updated": False,
		"shown": [],
		"hidden": [],
	}

	if result["hrms_installed"]:
		if frappe.db.exists("Workspace", HR_WORKSPACE):
			doc = frappe.get_doc("Workspace", HR_WORKSPACE)
			# Rebuild when empty / still pointing at nothing useful, or module drifted.
			needs_rebuild = (
				doc.module != APP_MODULE
				or not doc.links
				or doc.is_hidden
				or not doc.public
			)
			if needs_rebuild:
				_build_hr_workspace_doc(doc)
				doc.flags.ignore_permissions = True
				doc.save()
				result["updated"] = True
			elif _set(HR_WORKSPACE, public=1, is_hidden=0, module=APP_MODULE, app=APP_NAME, icon="users-round"):
				result["updated"] = True
		else:
			doc = frappe.new_doc("Workspace")
			_build_hr_workspace_doc(doc)
			doc.insert(ignore_permissions=True)
			result["created"] = True

		result["shown"].append(HR_WORKSPACE)
		_show_desktop_icons(HR_WORKSPACE)

		# Fix a Desktop Icon that still claims app=hrms / wrong link target.
		for icon_name in frappe.get_all("Desktop Icon", filters={"label": HR_WORKSPACE}, pluck="name"):
			wanted = {
				"app": APP_NAME,
				"link_type": "Workspace Sidebar",
				"link_to": HR_WORKSPACE,
				"icon": "users-round",
				"hidden": 0,
			}
			current = frappe.db.get_value("Desktop Icon", icon_name, list(wanted.keys()), as_dict=True)
			changes = {k: v for k, v in wanted.items() if current and current.get(k) != v}
			if changes:
				frappe.db.set_value("Desktop Icon", icon_name, changes, update_modified=False)

		for name in OLD_HR_WORKSPACES:
			if not frappe.db.exists("Workspace", name):
				continue
			if _set(name, public=0, is_hidden=1):
				result["hidden"].append(name)
			_hide_desktop_icons(name)
	elif frappe.db.exists("Workspace", HR_WORKSPACE):
		if _set(HR_WORKSPACE, public=0, is_hidden=1):
			result["hidden"].append(HR_WORKSPACE)
		_hide_desktop_icons(HR_WORKSPACE)

	frappe.db.commit()
	frappe.clear_cache()

	if verbose:
		state = "installed" if result["hrms_installed"] else "not installed"
		print(
			f"ndserp: hrms {state}; created={result['created']} updated={result['updated']} "
			f"shown={result['shown'] or '-'} hidden={result['hidden'] or '-'}"
		)

	return result


def _set(workspace: str, **values) -> bool:
	"""Write only the values that actually differ. Returns True if anything changed."""
	current = frappe.db.get_value("Workspace", workspace, list(values.keys()), as_dict=True)
	changes = {k: v for k, v in values.items() if current and current.get(k) != v}

	if not changes:
		return False

	frappe.db.set_value("Workspace", workspace, changes, update_modified=False)
	return True


def apply(verbose: bool = True) -> dict:
	"""Show the Ndserp workspaces, hide every other one.

	Idempotent: running it twice reports zero changes the second time.
	Foreign workspaces are set to `public = 0, is_hidden = 1`, which removes
	them from the sidebar and from the awesomebar search without touching their
	role assignments. Matching Desktop Icon tiles are hidden the same way so
	the apps screen matches the sidebar.
	"""
	shown, hidden = 0, 0

	for name in get_app_workspaces():
		# POS DocType links only exist when pos_next is installed.
		if name == POS_WORKSPACE and not is_pos_next_installed():
			if _set(name, public=0, is_hidden=1):
				hidden += 1
			_hide_desktop_icons(name)
			continue
		# HR NDS DocType links only exist when hrms is installed.
		if name == HR_WORKSPACE and not is_hrms_installed():
			if _set(name, public=0, is_hidden=1):
				hidden += 1
			_hide_desktop_icons(name)
			continue
		if _set(name, public=1, is_hidden=0):
			shown += 1
		_show_desktop_icons(name)

	keep_extra = set(get_keep_desktop_icons())
	for name in get_foreign_workspaces():
		if name in keep_extra:
			# Kept extras (HR NDS, ZATCA when ksa_compliance is installed).
			if _set(name, public=1, is_hidden=0):
				shown += 1
			_show_desktop_icons(name)
			continue
		if _set(name, public=0, is_hidden=1):
			hidden += 1
		_hide_desktop_icons(name)

	# App / Folder tiles (Framework, Frappe Framework, Accounts, …) are not
	# Workspace records - hide them separately so the apps screen is NDS-only.
	icons = hide_foreign_desktop_icons(verbose=False)

	frappe.db.commit()
	frappe.clear_cache()

	result = {
		"shown": shown,
		"hidden": hidden,
		"app_workspaces": len(get_app_workspaces()),
		"desktop_icons_hidden": len(icons["hidden"]),
	}

	if verbose:
		print(
			f"ndserp: {result['app_workspaces']} Ndserp workspaces active, "
			f"{hidden} foreign workspaces hidden, "
			f"{result['desktop_icons_hidden']} foreign desktop icons hidden"
		)

	return result


def ensure_sidebars(verbose: bool = True) -> dict:
	"""Create the missing `Workspace Sidebar` record for each Ndserp workspace.

	Frappe's install-time step (`auto_generate_icons_and_sidebar`, wired up as
	an `after_app_install` hook) runs BEFORE `sync_fixtures` - so on a fresh
	`bench install-app ndserp` it scans the DB while zero Ndserp workspaces
	exist yet and skips them entirely. Without a sidebar record, dual-sidebar
	themes (amir_theme_v16) have no rail entry for these workspaces at all,
	which is what made them look like they weren't a real, separate section.

	Cheap to call from both `after_install` and `after_migrate`: it only does
	the (relatively expensive) full-workspace scan when something is actually
	missing, and core's own creator skips any workspace that already has one.
	"""
	missing = set(get_app_workspaces()) - set(frappe.get_all("Workspace Sidebar", pluck="title"))

	if not missing:
		if verbose:
			print("ndserp: all workspace sidebars present")
		return {"created": 0}

	from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import (
		create_workspace_sidebar_for_workspaces,
	)

	create_workspace_sidebar_for_workspaces()
	frappe.db.commit()

	if verbose:
		print(f"ndserp: created {len(missing)} workspace sidebar(s): {', '.join(sorted(missing))}")

	return {"created": len(missing), "names": sorted(missing)}


def ensure_desktop_icon_apps(verbose: bool = True) -> dict:
	"""Sync `app` and `icon` onto each Ndserp workspace's `Desktop Icon` record.

	Creates a missing Desktop Icon for any Ndserp workspace that does not yet
	have one (e.g. a newly added fixture workspace after migrate, when Frappe's
	`create_desktop_icons_from_workspace()` already ran against the old set).

	`icon` is copied from the workspace on every run because Frappe only ever
	writes it once, in `create_desktop_icons_from_workspace()` at creation time.
	Changing `Workspace.icon` afterwards - which is exactly what the v14-era
	Font Awesome names ("fas fa-cart-plus") in the fixture needed, since v16
	resolves the value as `<use href="#icon-NAME">` against an inlined sprite
	that has no such symbol and therefore drew an empty box - would otherwise
	never reach the tile.

	Frappe's own `create_desktop_icons_from_workspace()` (frappe/desk/doctype/
	desktop_icon/desktop_icon.py) sets `icon.app_name = app_name` when creating
	these - but "app_name" isn't a real field on Desktop Icon (only "app" is;
	confirmed against desktop_icon.json), so that assignment is silently
	dropped and `app` stays NULL on every workspace-derived Desktop Icon,
	regardless of which app the workspace belongs to. This isn't
	ndserp-specific, it's a gap in stock Frappe - but it matters here because
	`frappe.utils.get_desktop_icon()` (public/js/frappe/utils/utils.js) hard
	-requires `icon.app` to be truthy before it will even look for a custom
	SVG, so without this fix our icons under `public/icons/desktop_icons/`
	would never be found no matter how correctly they're named - the Desktop
	page falls back to a plain gray box instead. (Blank rather than a lettered
	avatar because that fallback's sprite sheet only has glyphs for Latin
	letters - an Arabic label's first letter has nothing to render.)

	Idempotent and cheap - only writes rows whose values are wrong.
	"""
	created, updated = 0, 0

	for name in get_app_workspaces():
		workspace_icon = frappe.db.get_value("Workspace", name, "icon")
		wanted = {"app": APP_NAME, "icon": workspace_icon}

		icon_names = frappe.get_all(
			"Desktop Icon", filters={"label": name, "icon_type": "Link"}, pluck="name"
		)

		if not icon_names:
			# Skip hidden POS / HR workspaces when their apps are not installed.
			if name == POS_WORKSPACE and not is_pos_next_installed():
				continue
			if name == HR_WORKSPACE and not is_hrms_installed():
				continue
			if frappe.db.get_value("Workspace", name, "is_hidden"):
				continue

			icon = frappe.new_doc("Desktop Icon")
			icon.label = name
			icon.icon_type = "Link"
			icon.link_type = "Workspace Sidebar"
			icon.link_to = name
			icon.app = APP_NAME
			icon.icon = workspace_icon
			icon.insert(ignore_permissions=True, ignore_if_duplicate=True)
			created += 1
			continue

		for icon_name in icon_names:
			current = frappe.db.get_value("Desktop Icon", icon_name, list(wanted.keys()), as_dict=True)
			changes = {k: v for k, v in wanted.items() if current and current.get(k) != v}
			if changes:
				frappe.db.set_value("Desktop Icon", icon_name, changes, update_modified=False)
				updated += 1

	if created or updated:
		frappe.db.commit()
		frappe.clear_cache()

	if verbose:
		print(f"ndserp: desktop icons created={created} app/icon fixed={updated}")

	return {"created": created, "updated": updated}


def get_ordered_app_workspaces() -> list[str]:
	"""The app's workspaces in `WORKSPACE_ORDER`, unlisted ones appended by name."""
	existing = set(get_app_workspaces())
	ordered = [name for name in WORKSPACE_ORDER if name in existing]
	ordered += sorted(existing - set(ordered))
	return ordered


def ensure_order(verbose: bool = True) -> dict:
	"""Pin the display order of the Ndserp sections. Idempotent.

	    bench --site <site> execute ndserp.setup.workspace_policy.ensure_order

	Both surfaces are written from the single `WORKSPACE_ORDER` list so the
	apps screen, the sidebar rail and the workspace switcher can never disagree
	about what comes after what.
	"""
	updated = 0

	for position, name in enumerate(get_ordered_app_workspaces()):
		if _set(name, sequence_id=float(WORKSPACE_SEQUENCE_BASE + position)):
			updated += 1

		idx = DESKTOP_ICON_IDX_BASE + position
		# `label` rather than `name`: a Desktop Icon is named after its label but
		# renaming one would not update the link, and the workspace-derived icons
		# are matched by label everywhere else in this module.
		for icon_name in frappe.get_all(
			"Desktop Icon", filters={"label": name, "icon_type": "Link"}, pluck="name"
		):
			if frappe.db.get_value("Desktop Icon", icon_name, "idx") != idx:
				frappe.db.set_value("Desktop Icon", icon_name, "idx", idx, update_modified=False)
				updated += 1

	if updated:
		frappe.db.commit()
		# Both "desktop_icons" and "bootinfo" are per-user cache keys, so a
		# targeted `clear_desktop_icons_cache()` would only ever fix the user who
		# ran the migration. `clear_cache()` with no arguments drops them for
		# every user, which is what an order change has to do.
		frappe.clear_cache()

	if verbose:
		print(f"ndserp: ordered {len(get_ordered_app_workspaces())} section(s), {updated} value(s) changed")

	return {"order": get_ordered_app_workspaces(), "updated": updated}


def ensure_workspace_roles(verbose: bool = True) -> dict:
	"""Gate every Ndserp workspace by ITS OWN dedicated role, not a borrowed one.

	`workspace_scope.get_scope_roles()` already assumes "Role name == Workspace
	name" (Workspace.autoname = field:label) to decide who is a scoped
	Ndserp-only user. That pairing depends on the workspace's own `Roles`
	restriction table actually containing that role - but on this site it
	carried generic operational roles instead (`حسابات NDS ERP` -> "Accounts
	User", `الاصول NDS ERP` -> "Accounts User" too, `مخازن NDS ERP` -> "Stock
	User"/"Stock Manager", ...), even though the matching dedicated roles
	already exist and are already assigned to the Ndserp test users. Core
	Frappe's `Workspace.is_permitted()` has no special case for System Manager
	or Administrator - it is a plain `has_common(user_roles, workspace.roles)` -
	so the wrong role there is a real visibility bug, not a cosmetic one.

	Creates the matching Role first if it is somehow missing, then replaces
	the workspace's Roles table with exactly that one role. Idempotent, and
	re-applied on every `bench migrate` (see after_migrate) so neither a
	fixture re-sync nor a manual edit in the UI can silently reintroduce the
	wrong role.
	"""
	fixed = []

	for name in get_app_workspaces():
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(
				ignore_permissions=True
			)

		doc = frappe.get_doc("Workspace", name)
		current = [r.role for r in doc.roles]
		if current == [name]:
			continue

		doc.set("roles", [])
		doc.append("roles", {"role": name})
		doc.flags.ignore_permissions = True
		doc.save()
		fixed.append({"workspace": name, "was": current, "now": [name]})

	if fixed:
		frappe.db.commit()
		frappe.clear_cache()

	if verbose:
		if fixed:
			for row in fixed:
				print(f"ndserp: {row['workspace']}: roles {row['was']} -> {row['now']}")
		else:
			print("ndserp: all workspace roles already correct")

	return {"fixed": fixed}


def revert(verbose: bool = True) -> dict:
	"""Undo `apply()` - restore every non-Ndserp workspace to exactly the
	`public`/`is_hidden` values it ships with on disk (its `<module>/workspace/
	<name>/<name>.json` file), not just a blanket "make everything visible".
	Some standard workspaces legitimately ship `is_hidden = 1`; a blanket
	unhide would un-hide those too, which isn't "the default state".

	Falls back to `public = 1, is_hidden = 0` only for a workspace with no
	backing file found (shouldn't happen for genuinely standard ones).

	Used by `before_uninstall`, and as an escape hatch if `apply()` hid
	something you still need.
	"""
	from frappe.model.sync import create_entity_file_map
	from frappe.modules.import_file import read_doc_from_file

	file_map = create_entity_file_map(["Workspace"]).get("Workspace", {})
	restored = 0

	for name in get_foreign_workspaces():
		wants = {"public": 1, "is_hidden": 0}
		path = file_map.get(name)
		if path:
			doc = read_doc_from_file(path)
			if isinstance(doc, list):
				doc = doc[0] if doc else {}
			wants = {"public": doc.get("public", 1), "is_hidden": doc.get("is_hidden", 0)}

		if _set(name, **wants):
			restored += 1
		# Undo the Desktop Icon hide from apply(); leave legitimately hidden
		# workspace tiles alone when the shipped workspace itself is hidden.
		if not wants.get("is_hidden"):
			_show_desktop_icons(name)

	# Restore App / Folder roots and any other non-workspace tiles we hid.
	icons_restored = 0
	keep = set(get_app_workspaces())
	for icon in frappe.get_all(
		"Desktop Icon",
		fields=["name", "label", "hidden"],
		filters={"hidden": 1},
	):
		if icon.label in keep:
			continue
		frappe.db.set_value("Desktop Icon", icon.name, "hidden", 0, update_modified=False)
		icons_restored += 1

	frappe.db.commit()
	frappe.clear_cache()

	if verbose:
		print(
			f"ndserp: restored {restored} workspace(s) and {icons_restored} desktop icon(s) "
			f"to their shipped defaults"
		)

	return {"restored": restored, "desktop_icons_restored": icons_restored}


def status() -> dict:
	"""Report what the policy would do, without changing anything."""
	app = get_app_workspaces()
	modules = get_app_modules()
	filters = {"module": ["not in", modules], "is_hidden": 0} if modules else {"is_hidden": 0}
	visible_foreign = frappe.get_all("Workspace", filters=filters, pluck="name")

	print(f"policy enabled : {is_enabled()}")
	print(f"Ndserp spaces  : {len(app)} -> {', '.join(app) or '(none)'}")
	print(f"still visible  : {len(visible_foreign)} foreign workspace(s)")

	return {"enabled": is_enabled(), "app_workspaces": app, "visible_foreign": visible_foreign}


def clear_module_blocks(user: str) -> None:
	"""Clear a user's blocked modules.

	The old scripts hardcoded `geust@nds.com` here. Blocking modules also blocks
	the links *inside* the Arabic workspaces, so this is the fix when a user
	sees empty workspaces.

	    bench --site <site> execute ndserp.setup.workspace_policy.clear_module_blocks \\
	        --kwargs '{"user": "someone@example.com"}'
	"""
	doc = frappe.get_doc("User", user)
	doc.set("block_modules", [])
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache(user=user)
	print(f"ndserp: cleared blocked modules for {user}")
