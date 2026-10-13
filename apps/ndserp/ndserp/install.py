"""Install / migrate / uninstall hooks for ndserp."""

import frappe

from ndserp.setup import sidebar_builder, workspace_policy


def after_install():
	"""Runs once, on `bench install-app ndserp`.

	Runs BEFORE `sync_fixtures` (see `after_migrate`'s docstring for the full
	install-order story), so zero Ndserp workspaces exist yet at this point.
	Pull the fixtures in ourselves first so this hook is self-sufficient on a
	single `bench install-app ndserp` - core will harmlessly re-sync them
	again right after this hook returns.

	Sets up ndserp workspaces/sidebars, then (by default) hides every
	non-Ndserp workspace so the site desk shows only NDS modules. Opt out
	with `ndserp_workspace_policy 0` - see `workspace_policy.is_enabled()`.
	"""
	from frappe.utils.fixtures import sync_fixtures

	sync_fixtures(app="ndserp")
	workspace_policy.ensure_hr_workspace()
	workspace_policy.ensure_pos_workspace()
	workspace_policy.ensure_sidebars()
	workspace_policy.ensure_desktop_icon_apps()
	workspace_policy.ensure_order()
	workspace_policy.ensure_workspace_roles()
	sidebar_builder.rebuild()

	if workspace_policy.is_enabled():
		workspace_policy.apply()
		workspace_policy.ensure_hr_workspace()
		workspace_policy.ensure_pos_workspace()


def after_migrate():
	"""Runs on every `bench migrate`.

	`bench migrate` runs `remove_orphan_entities()` between the fixture sync
	step and this hook. It deletes every *public* Workspace whose module
	resolves to an app (which ours do, since `module = Ndserp`) unless that
	workspace is backed by a `<module>/workspace/<name>/<name>.json` file on
	disk - fixture-shipped workspaces never are, so all Ndserp Arabic workspaces
	get deleted on every single migrate, right before this hook runs. Re-sync
	the Workspace fixture here to recreate them, and ensure they still have
	their sidebars, regardless of the visibility policy below.

	By default every non-Ndserp workspace is hidden again after migrate
	(Frappe/ERPNext re-sync can unhide them). Opt out:
	bench --site <site> set-config -g ndserp_workspace_policy 0
	"""
	try:
		from frappe.utils.fixtures import sync_fixtures

		sync_fixtures(app="ndserp")
	except Exception:
		frappe.log_error(title="ndserp: workspace fixture re-sync failed", message=frappe.get_traceback())

	try:
		from ndserp.setup import sales_invoice_payment

		sales_invoice_payment.ensure_custom_fields()
	except Exception:
		frappe.log_error(title="ndserp: sales invoice custom fields failed", message=frappe.get_traceback())

	try:
		# Show/hide the POS workspace and retire English POSNext when pos_next
		# is installed (no-op hide of the Ndserp POS tile when it is not).
		workspace_policy.ensure_pos_workspace(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: POS workspace policy failed", message=frappe.get_traceback())

	try:
		# Create / repair HR NDS (real Workspace + icon) when hrms is installed.
		workspace_policy.ensure_hr_workspace(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: HR workspace policy failed", message=frappe.get_traceback())

	try:
		workspace_policy.ensure_sidebars(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: workspace sidebar creation failed", message=frappe.get_traceback())

	try:
		workspace_policy.ensure_desktop_icon_apps(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: desktop icon app fix failed", message=frappe.get_traceback())

	try:
		# Must run after `ensure_desktop_icon_apps`, which is what creates the
		# missing Desktop Icon rows this then sorts.
		workspace_policy.ensure_order(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: workspace ordering failed", message=frappe.get_traceback())

	try:
		# The fixture re-sync above can reintroduce a stale/wrong role on the
		# workspace's Roles restriction table (see docstring); put the correct
		# same-named role back every time, not just once by hand.
		workspace_policy.ensure_workspace_roles(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: workspace role fix failed", message=frappe.get_traceback())

	try:
		# Workspace content is re-synced from the fixture just above, so the
		# sidebars have to be regenerated from it here or they'd drift out of
		# date whenever a card/link is added to a workspace.
		sidebar_builder.rebuild(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: sidebar rebuild failed", message=frappe.get_traceback())

	if not workspace_policy.is_enabled():
		return

	try:
		workspace_policy.apply(verbose=False)
	except Exception:
		# A failing cosmetic hook must never abort a migration.
		frappe.log_error(title="ndserp: workspace policy failed", message=frappe.get_traceback())

	try:
		# Re-apply after `apply()` so a blanket show of Ndserp workspaces cannot
		# resurrect POS when pos_next is missing, or un-hide English POSNext.
		workspace_policy.ensure_pos_workspace(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: POS workspace policy (post-apply) failed", message=frappe.get_traceback())

	try:
		workspace_policy.ensure_hr_workspace(verbose=False)
	except Exception:
		frappe.log_error(title="ndserp: HR workspace policy (post-apply) failed", message=frappe.get_traceback())


def before_uninstall():
	"""Leave the site in a usable state when the app is removed."""
	workspace_policy.revert(verbose=False)
