/* Scope the sales-workspace visual layer without changing route or workspace behavior. */
(() => {
  "use strict";

  const WORKSPACE_NAME = "المبيعات NDS ERP";
  const BODY_CLASS = "nds-sales-workspace-redesign";

  function isSalesWorkspace() {
    try {
      if (window.frappe && typeof window.frappe.get_route === "function") {
        const route = window.frappe.get_route() || [];
        return route[0] === "Workspaces" && route.slice(1).join("/") === WORKSPACE_NAME;
      }
    } catch (_) {
      // Keep the theme non-blocking if the route API is not ready.
    }
    const path = decodeURIComponent(window.location.pathname || "");
    return path.includes("/desk/Workspaces/" + WORKSPACE_NAME);
  }

  function applyScope() {
    if (!document.body) return;
    document.body.classList.toggle(BODY_CLASS, isSalesWorkspace());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyScope, { once: true });
  } else {
    applyScope();
  }

  if (window.frappe && window.frappe.router && typeof window.frappe.router.on === "function") {
    window.frappe.router.on("change", applyScope);
  }

  // Frappe may replace the page shell during client-side navigation.
  const observer = new MutationObserver(applyScope);
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
