"""Per-user workspace scoping for ndserp.

Three problems, solved here together because they all hinge on the same "is
this user meant to live entirely inside the Ndserp workspaces" question:

1. **Hiding foreign workspaces from Ndserp-only users.** Frappe's own
   `Workspace.is_permitted()` (`frappe.desk.desktop`) is allow-list only: a
   workspace with an empty `Roles` table is visible to *everyone*. There is no
   built-in way to say "hide this workspace FROM users who have role X" - which
   is what a user scoped to a single Ndserp role/workspace needs, since the
   standard Frappe/ERPNext workspaces (Home, Selling, Buying, ...) ship with no
   Roles restriction at all. `patch_workspace_permission()` adds that exclusion
   by wrapping `Workspace.is_permitted`, narrowly: it only fires for a user who
   (a) holds at least one of the six Ndserp workspace roles and (b) holds none
   of `UNRESTRICTED_ROLES`. Everyone else - Administrator, System Managers, and
   any regular staff member without an Ndserp role - gets stock Frappe
   behaviour, untouched. Site-wide hide of foreign workspaces is handled
   separately by `workspace_policy.apply()` (on by default after install).

2. **Keeping the sidebar/breadcrumb on the Ndserp workspace when a link inside
   it opens a DocType whose own module is something else** (e.g. Customer,
   module Selling, opened from "المبيعات NDS ERP"). Frappe's client-side
   `frappe.ui.Sidebar.resolve_sidebar()` (frappe/public/js/frappe/ui/sidebar/
   sidebar.js) *would* keep the current sidebar if the current sidebar is a
   "candidate" for that doctype - but candidates come from `Workspace Sidebar`
   records, which Frappe's `create_workspace_sidebar_for_workspaces()` builds
   only from a workspace's top-level Shortcuts, never from the DocType links
   nested inside its Link Cards. Customer et al. are only reachable from a Link
   Card in these workspaces (by design - the Shortcuts row is meant to stay a
   handful of key items), so they never become resolver candidates and the
   client falls back to a standard module workspace (Selling, CRM, ...).
   `get_workspace_doctype_map()` exposes the *full* doctype set (Link Cards
   included) per Ndserp workspace via `bootinfo.ndserp_workspace_doctypes`; the
   client-side patch in `workspace_context.bundle.js` uses it to extend, not
   replace, Frappe's own resolution: it only ever short-circuits toward an
   Ndserp workspace the user is already on, everything else defers to stock
   behaviour.

3. **The `/desk` Desktop icon grid still shows everything.** Problem 1 only
   fixes `frappe.desk.desktop.get_workspaces()` - the Workspaces *list*. The
   Desktop landing page (module/app icon grid) is built from a *different*
   pipeline: `bootinfo.desktop_icons` and `bootinfo.workspace_sidebar_item`
   (`frappe/boot.py: load_desktop_data`, `frappe/desk/doctype/desktop_icon/
   desktop_icon.py: get_desktop_icons`). Its per-item visibility is governed
   by `Workspace Sidebar.is_item_allowed()`, which for a DocType-type item
   checks raw DocType read permission (`frappe.has_permission`), completely
   independent of which Workspace the item happens to be organised under.
   A scoped user who ALSO holds real operational roles (Purchase Manager,
   Purchase User, ... - needed for the DocTypes inside their own workspace to
   actually work) therefore still gets sidebar entries for the *standard*
   Buying/Selling/... categories, because they genuinely can read Purchase
   Order, Item, Supplier etc. - the workspace-level Roles restriction from
   problem 1 never enters into that check. `restrict_bootinfo_desktop()`
   fixes this the practical way: rather than fighting that permission
   pipeline node by node, it prunes `bootinfo.desktop_icons` and
   `bootinfo.workspace_sidebar_item` down to exactly the workspace(s) already
   present in `bootinfo.workspaces["pages"]` (problem 1's already-correct
   output) - single source of truth, applied post-hoc since both fields are
   computed before `boot_session` hooks run.
"""

import frappe
from frappe.utils.caching import request_cache

# Roles that mean "this person needs full desk access" - never scope them
# down to a single Ndserp workspace, no matter what else is on their role list.
UNRESTRICTED_ROLES = {"Administrator", "System Manager", "Workspace Manager"}


@request_cache
def get_app_modules() -> set[str]:
	"""Every module this scoping system recognises as "ours" - not just the
	literal "Ndserp" module. Generalised so a future Module Def belonging to
	this app (e.g. an "HR" module, same idea as "المشتريات NDS ERP") is picked
	up automatically, with no code change here. `request_cache` keeps this to
	one query per HTTP request even though `is_permitted`/`get_allowed_modules`
	call it once per workspace being evaluated.
	"""
	from ndserp.setup.workspace_policy import get_app_modules as _get_app_modules

	return set(_get_app_modules())


def get_scope_roles() -> set[str]:
	"""The Ndserp workspace roles - one per workspace, Role name == Workspace
	name (Workspace.autoname = field:label, see [[ndserp-app]]). Covers every
	workspace under every module in `get_app_modules()`, not just the original
	six under "Ndserp"."""
	from ndserp.setup.workspace_policy import get_app_workspaces

	return set(get_app_workspaces())


def is_scoped_user(user: str | None = None) -> bool:
	"""True if `user` should see only Ndserp (module=Ndserp) workspaces."""
	user = user or frappe.session.user

	if user == "Administrator":
		return False

	roles = set(frappe.get_roles(user))

	if roles & UNRESTRICTED_ROLES:
		return False

	return bool(roles & get_scope_roles())


def patch_workspace_permission() -> None:
	"""Wrap two `frappe.desk.desktop.Workspace` methods once per process.

	Idempotent (guarded by an attribute on the class) so it's safe to call from
	both `ndserp/__init__.py` (belt) and `after_install`/`after_migrate` (braces)
	without double-wrapping.

	Two separate gates needed patching, not one:

	* `get_allowed_modules` - `Workspace.__init__` raises `PermissionError`
	  outright for a workspace whose module isn't in `user.allow_modules`,
	  unless the user holds "Workspace Manager". `allow_modules` is built from
	  DocTypes the user can read (`frappe.utils.user.build_permissions`) - and
	  a module that ships no DocTypes of its own (like "Ndserp" - see
	  hooks.py) can *never* land there. Without this, nobody except a
	  Workspace Manager could open one of these workspaces at all, regardless
	  of the Role already on the workspace itself. This only unlocks
	  *workspace visibility* for the module - actual DocType access is
	  untouched, still governed entirely by the normal Role Permissions
	  Manager.
	* `is_permitted` - the actual per-workspace Roles check (problem 1 in the
	  module docstring): adds the "hide FROM this role" exclusion stock
	  Frappe has no hook for.

	Both are generalised over `get_app_modules()` (any Module Def with
	`app_name = "ndserp"`), not hardcoded to "Ndserp" - see that function's
	docstring.
	"""
	from frappe.desk.desktop import Workspace as DesktopWorkspace

	if getattr(DesktopWorkspace, "_ndserp_scoped", False):
		return

	original_get_allowed_modules = DesktopWorkspace.get_allowed_modules
	original_is_permitted = DesktopWorkspace.is_permitted

	def get_allowed_modules(self):
		modules = original_get_allowed_modules(self)
		if get_scope_roles() & set(frappe.get_roles()):
			missing = get_app_modules() - set(modules)
			if missing:
				return [*modules, *missing]
		return modules

	def is_permitted(self):
		if not original_is_permitted(self):
			return False
		if is_scoped_user() and (self.doc.module or None) not in get_app_modules():
			return False
		return True

	DesktopWorkspace.get_allowed_modules = get_allowed_modules
	DesktopWorkspace.is_permitted = is_permitted
	DesktopWorkspace._ndserp_scoped = True


def get_workspace_doctype_map() -> dict:
	"""`{workspace_name: [doctype, ...]}` for every Ndserp workspace, covering
	DocType links wherever they live in the workspace - Shortcuts *and* the
	nested Links inside Link Cards. Used only to extend the client's own
	sidebar-resolution candidates (see module docstring, problem 2); never
	rendered as-is, so it doesn't need to match anything visible on the canvas.
	"""
	from ndserp.setup.workspace_policy import get_app_workspaces

	names = get_app_workspaces()
	if not names:
		return {}

	out = {name: set() for name in names}

	shortcuts = frappe.get_all(
		"Workspace Shortcut",
		filters={"parent": ["in", names], "type": "DocType"},
		fields=["parent", "link_to"],
	)
	links = frappe.get_all(
		"Workspace Link",
		filters={"parent": ["in", names], "link_type": "DocType"},
		fields=["parent", "link_to"],
	)

	for row in [*shortcuts, *links]:
		if row.link_to:
			out[row.parent].add(row.link_to)

	return {name: sorted(doctypes) for name, doctypes in out.items() if doctypes}


def restrict_bootinfo_desktop(bootinfo) -> None:
	"""Prune the Desktop icon-grid / sidebar-rail boot data to exactly the
	workspace(s) the user's roles unlock (problem 3 in the module docstring).

	No-op for anyone `is_scoped_user()` excludes. Uses `bootinfo.workspaces
	["pages"]` (already correctly filtered by `patch_workspace_permission`'s
	`is_permitted` patch) as the single source of truth for "what this user is
	allowed to see", instead of re-deriving it from roles a second time.
	"""
	if not is_scoped_user():
		return

	allowed_names = {page["name"] for page in bootinfo.get("workspaces", {}).get("pages", [])}
	allowed_lower = {name.lower() for name in allowed_names}

	if bootinfo.get("workspace_sidebar_item"):
		bootinfo.workspace_sidebar_item = {
			key: value for key, value in bootinfo.workspace_sidebar_item.items() if key in allowed_lower
		}

	if bootinfo.get("desktop_icons"):
		bootinfo.desktop_icons = [
			icon for icon in bootinfo.desktop_icons if icon.get("label") in allowed_names
		]


def extend_bootinfo(bootinfo) -> None:
	"""`boot_session` hook - see hooks.py. Adds the doctype map from problem 2
	and applies problem 3's pruning; problem 1's fix lives entirely
	server-side in `patch_workspace_permission` and needs nothing in boot
	data.
	"""
	bootinfo.ndserp_workspace_doctypes = get_workspace_doctype_map()
	restrict_bootinfo_desktop(bootinfo)
