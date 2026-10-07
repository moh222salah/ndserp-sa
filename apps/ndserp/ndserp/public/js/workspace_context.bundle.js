/**
 * Keeps the desk sidebar/breadcrumb on an Ndserp workspace when a link inside
 * it opens a DocType that belongs to a different core module.
 *
 * Example: "المبيعات NDS ERP" links to Customer (module Selling) from a Link
 * Card. Frappe's own `frappe.ui.Sidebar.resolve_sidebar()` would happily keep
 * the current sidebar active for a doctype it's a "candidate" for - but
 * candidates come from `Workspace Sidebar` records, which Frappe only builds
 * from a workspace's top-level Shortcuts, never from Link Card items. Customer
 * is intentionally a Link Card item here (the Shortcuts row is meant to stay a
 * handful of key items), so it's never a candidate and the stock resolver
 * falls back to a standard module workspace (Selling/CRM/...), which is the
 * "jumps to a totally different workspace" behaviour this fixes.
 *
 * `bootinfo.ndserp_workspace_doctypes` (see ndserp.setup.workspace_scope)
 * supplies the full doctype set per Ndserp workspace - Link Cards included -
 * so this only ever *extends* resolution toward a workspace the user is
 * already on. It never overrides Frappe's own choice when the user didn't
 * come from one of these workspaces in the first place, so standard desk
 * navigation is untouched.
 */

function patch_sidebar_resolution() {
	if (!frappe.ui || !frappe.ui.Sidebar || frappe.ui.Sidebar.prototype._ndserp_context_patched) {
		return;
	}

	const original_resolve_sidebar = frappe.ui.Sidebar.prototype.resolve_sidebar;

	frappe.ui.Sidebar.prototype.resolve_sidebar = function (entity, module) {
		const current = this.sidebar_title;
		const doctype_map = frappe.boot.ndserp_workspace_doctypes || {};

		if (current && doctype_map[current] && doctype_map[current].includes(entity)) {
			let candidates = this.get_workspace_sidebars(entity);
			if (!candidates.includes(current)) {
				candidates = candidates.concat([current]);
			}
			this.preferred_sidebars = candidates;
			return current;
		}

		return original_resolve_sidebar.call(this, entity, module);
	};

	frappe.ui.Sidebar.prototype._ndserp_context_patched = true;
}

// `frappe.ui.Sidebar` is a class defined in frappe's own core bundle, which
// loads before app_include_js scripts, so this can run immediately - the
// `app_ready` listener is only a safety net for any load-order edge case.
patch_sidebar_resolution();
$(document).on("app_ready", patch_sidebar_resolution);
