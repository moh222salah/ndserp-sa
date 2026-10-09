/* NDS ERP Saudi — Sales Workspace route scope.
 * Loaded by amir_theme.bundle.js so the existing hashed bundle serves this code.
 * Presentation only: no workspace data, route, permissions, or business logic changes.
 */
const SALES_WORKSPACE_NAME = "المبيعات NDS ERP";
const SALES_WORKSPACE_CLASS = "nds-sales-workspace-redesign";

function isSalesWorkspaceRoute() {
	const path = decodeURIComponent(window.location.pathname || "");
	if (path.includes("/desk/Workspaces/" + SALES_WORKSPACE_NAME)) return true;

	try {
		const route = window.frappe && typeof window.frappe.get_route === "function"
			? window.frappe.get_route()
			: [];
		return Array.isArray(route)
			&& route[0] === "Workspaces"
			&& route.slice(1).join("/") === SALES_WORKSPACE_NAME;
	} catch (error) {
		return false;
	}
}

function applySalesWorkspaceScope() {
	if (!document.body) return;
	document.body.classList.toggle(SALES_WORKSPACE_CLASS, isSalesWorkspaceRoute());
}

function scheduleSalesWorkspaceScope() {
	// The Frappe route and page shell settle over the next few frames on Desk navigation.
	[0, 100, 350].forEach((delay) => window.setTimeout(applySalesWorkspaceScope, delay));
}

if (document.readyState === "loading") {
	document.addEventListener("DOMContentLoaded", scheduleSalesWorkspaceScope, { once: true });
} else {
	scheduleSalesWorkspaceScope();
}

if (typeof window.$ === "function") {
	window.$(document).on("page-change", scheduleSalesWorkspaceScope);
}
window.addEventListener("popstate", scheduleSalesWorkspaceScope);
