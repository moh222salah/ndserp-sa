"""Build rich desk sidebars for the ndserp workspaces.

Why this exists
---------------
Frappe's own `create_workspace_sidebar_for_workspaces()`
(frappe/desk/doctype/workspace_sidebar/workspace_sidebar.py) builds a
`Workspace Sidebar` from a workspace's **Shortcuts only**:

    shortcuts = workspace_doc.shortcuts
    ...
    for s in shortcuts: items.append(...)

It never looks at `Workspace Link` - the "Link Card" rows that make up the
body of the workspace page. A standard ERPNext workspace like *Invoicing*
doesn't notice, because its sidebar is a hand-maintained standard record
shipped on disk (module Accounts, app erpnext) with the sections already
spelled out: a `Section Break` row per group ("Payments", "Receivables", ...)
followed by its members carrying `child = 1`.

The ndserp workspaces have no such shipped file - their sidebars are generated
by the function above, so they came out as *just* a "Home" link (حسابات, which
has zero shortcuts, literally had one single item). That's the near-empty white
sidebar the user reported as unprofessional next to Invoicing's.

What this does
--------------
`rebuild()` regenerates each ndserp workspace's sidebar from the workspace's
own content, mapping the structure that already exists on the page:

    Workspace Link "Card Break"  ->  Sidebar Item "Section Break" (indent=1)
    Workspace Link "Link" under it ->  Sidebar Item "Link" (child=1)

so "الحسابات الرئيسية" and "التقارير المالية" become collapsible sidebar
sections holding exactly the documents already filed under them on the page -
the same shape as Invoicing's "المدفوعات" and its children.

Safety
------
* Only ever touches workspaces returned by `workspace_policy.get_app_workspaces()`
  (i.e. modules whose `app_name = "ndserp"`), never another app's sidebar.
* Additive: the existing Home + Shortcut items are rebuilt exactly as core
  built them, and the card sections are appended after. Nothing that worked
  before is dropped.
* Idempotent: compares a signature of the items it would write against what is
  already stored and skips the `save()` entirely when nothing changed, so it is
  cheap to call from `after_migrate` on every migration.
* Per-item visibility is still enforced downstream by Frappe itself -
  `frappe.boot.get_sidebar_items()` runs every non-Section-Break row through
  `Workspace Sidebar.is_item_allowed()`, so a user only ever sees the rows they
  have real permission for. This module grants nothing.
"""

import json

import frappe

# Shortcut/link types that map cleanly onto Workspace Sidebar Item.link_type
# (DocType, Page, Report, Workspace, Dashboard, URL). Anything outside this set
# is skipped rather than written as a broken row.
VALID_LINK_TYPES = {"DocType", "Page", "Report", "Workspace", "Dashboard", "URL"}


def _card_order(workspace) -> list[str]:
	"""Card labels in the order they visually appear on the workspace page.

	The `content` JSON is the layout the user actually sees; the `links` child
	table is stored in its own (often different) order - e.g. مخازن renders
	الحركات المخزنية before التقارير المخزنية but stores them the other way
	round. The sidebar should follow the page, so content wins and any card
	missing from it is appended afterwards in table order.
	"""
	order = []

	try:
		blocks = json.loads(workspace.content or "[]")
	except (ValueError, TypeError):
		blocks = []

	for block in blocks:
		if block.get("type") == "card":
			label = (block.get("data") or {}).get("card_name")
			if label and label not in order:
				order.append(label)

	return order


def _grouped_links(workspace) -> dict[str, list]:
	"""`{card label: [Workspace Link rows]}` - walk the flat child table and
	attach each Link row to the Card Break above it. Hidden rows are dropped."""
	groups: dict[str, list] = {}
	current = None

	for row in workspace.links:
		if row.type == "Card Break":
			current = row.label
			groups.setdefault(current, [])
		elif row.type == "Link" and current is not None:
			if row.hidden:
				continue
			if row.link_type in VALID_LINK_TYPES and row.link_to:
				groups[current].append(row)

	return groups


def build_items(workspace) -> list[dict]:
	"""The full sidebar item list for one workspace, in final order.

	Field values mirror what a standard shipped sidebar (Invoicing) uses, so
	these render identically to core's: everything `collapsible = 1`, group
	headers as `Section Break` with `indent = 1`, group members as `Link` with
	`child = 1`.
	"""
	items: list[dict] = [
		# Core puts the workspace itself at the top as "Home"; keep that exactly.
		{
			"type": "Link",
			"label": "Home",
			"link_type": "Workspace",
			"link_to": workspace.name,
			"collapsible": 1,
		}
	]

	# Shortcuts stay top-level, above the sections - same as core's generator
	# and the same as Invoicing's leading rows.
	for shortcut in workspace.shortcuts:
		if shortcut.type not in VALID_LINK_TYPES:
			continue

		# URL shortcuts store the target in Workspace Shortcut.url / Sidebar
		# Item.url - `link_to` is a Dynamic Link keyed off link_type, so writing
		# "/pos/" into link_to with link_type="URL" makes Document validation
		# look up DocType "URL" and fail.
		if shortcut.type == "URL":
			if not shortcut.url:
				continue
			items.append(
				{
					"type": "Link",
					"label": shortcut.label,
					"link_type": "URL",
					"url": shortcut.url,
					"icon": shortcut.icon,
					"collapsible": 1,
				}
			)
			continue

		if not shortcut.link_to:
			continue

		items.append(
			{
				"type": "Link",
				"label": shortcut.label,
				"link_type": shortcut.type,
				"link_to": shortcut.link_to,
				"icon": shortcut.icon,
				"collapsible": 1,
			}
		)

	groups = _grouped_links(workspace)
	ordered = _card_order(workspace)
	# Cards present in `links` but absent from `content` still deserve a section.
	ordered += [label for label in groups if label not in ordered]

	for label in ordered:
		rows = groups.get(label)
		if not rows:
			# Empty card - a header with nothing under it would just be noise.
			continue

		items.append({"type": "Section Break", "label": label, "indent": 1, "collapsible": 1})

		for row in rows:
			items.append(
				{
					"type": "Link",
					"label": row.label,
					"link_type": row.link_type,
					"link_to": row.link_to,
					"icon": row.icon,
					"child": 1,
					"collapsible": 1,
				}
			)

	return items


def _signature(items) -> list[tuple]:
	"""Comparable form of an item list, for the idempotency check.

	`link_type`/`link_to` are deliberately blanked for non-Link rows: the
	Select field carries a "DocType" default, so a Section Break we write with
	no link_type comes back from the DB as `link_type = "DocType"` (which is
	also why the shipped Invoicing sidebar shows it on its section headers).
	Comparing those would make every run look "changed" forever.
	"""

	def field(item, name, default=None):
		return (item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)) or default

	signed = []
	for item in items:
		row_type = field(item, "type", "") or ""
		is_link = row_type == "Link"
		link_type = (field(item, "link_type", "") or "") if is_link else ""
		# URL rows use `url`, not `link_to` (Dynamic Link cannot target "URL").
		target = ""
		if is_link:
			target = (
				(field(item, "url", "") or "")
				if link_type == "URL"
				else (field(item, "link_to", "") or "")
			)
		signed.append(
			(
				row_type,
				field(item, "label", "") or "",
				link_type,
				target,
				int(field(item, "child", 0) or 0),
				int(field(item, "indent", 0) or 0),
			)
		)

	return signed


def rebuild(verbose: bool = True) -> dict:
	"""Regenerate the sidebar of every ndserp workspace. Idempotent.

	    bench --site <site> execute ndserp.setup.sidebar_builder.rebuild
	"""
	from ndserp.setup.workspace_policy import APP_NAME, get_app_workspaces

	changed, skipped = [], []

	for name in get_app_workspaces():
		workspace = frappe.get_doc("Workspace", name)
		wanted = build_items(workspace)

		exists = frappe.db.exists("Workspace Sidebar", name)
		if exists:
			sidebar = frappe.get_doc("Workspace Sidebar", name)
		else:
			sidebar = frappe.new_doc("Workspace Sidebar")
			sidebar.title = name

		# `module` is set once by core from whatever the shortcut targets happened
		# to be, which leaves e.g. the Purchases sidebar claiming module "Stock".
		# Pin it (and `app`) to what the workspace actually is - this is also what
		# keeps `bootinfo.workspace_sidebar_item[...].app` consistent with the
		# Desktop Icon fix in workspace_policy.ensure_desktop_icon_apps().
		wanted_meta = (workspace.module, APP_NAME, workspace.icon or sidebar.header_icon)
		meta_drifted = (sidebar.module, sidebar.app, sidebar.header_icon) != wanted_meta
		sidebar.module, sidebar.app, sidebar.header_icon = wanted_meta

		if exists and not meta_drifted and _signature(sidebar.items) == _signature(wanted):
			skipped.append(name)
			continue

		sidebar.set("items", [])
		for idx, item in enumerate(wanted, start=1):
			sidebar.append("items", {**item, "idx": idx})

		sidebar.save(ignore_permissions=True)
		changed.append((name, len(wanted)))

	if changed:
		frappe.db.commit()
		frappe.clear_cache()

	if verbose:
		for name, count in changed:
			print(f"ndserp: rebuilt sidebar for {name} ({count} items)")
		if skipped:
			print(f"ndserp: {len(skipped)} sidebar(s) already up to date")

	return {"changed": [c[0] for c in changed], "skipped": skipped}
