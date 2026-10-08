/**
 * NDS browser identity
 *
 * Browser-tab presentation only:
 *   [favicon: /files/logo.jpeg] NDS | Current Module
 *
 * The current module is resolved from the active Workspace first, then the
 * current DocType/page metadata. No server calls, database writes, or core
 * patches are used.
 */

const SYSTEM_NAME = "NDS ERP";
const LOGO_PATH = "/files/logo.jpeg";

const DOCTYPE_ROUTES = new Set([
  "List",
  "Form",
  "Tree",
  "Report",
  "Gantt",
  "Calendar",
  "Kanban",
  "Image",
  "Map",
  "Inbox",
]);

function translate(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  try {
    return typeof window.__ === "function" ? window.__(text) : text;
  } catch {
    return text;
  }
}

function findWorkspace(name) {
  const frappe = window.frappe;
  if (!frappe || !name) return null;

  const workspaces = frappe.workspaces || {};
  return (
    workspaces[name] ||
    (frappe.router?.slug ? workspaces[frappe.router.slug(name)] : null) ||
    Object.values(workspaces).find(
      (workspace) =>
        workspace?.name === name ||
        workspace?.title === name ||
        workspace?.label === name
    ) ||
    null
  );
}

function getCurrentRoute() {
  const frappe = window.frappe;
  if (!frappe) return [];

  try {
    const route = frappe.get_route?.() || frappe.router?.current_route || [];
    return Array.isArray(route) ? route : [];
  } catch {
    return [];
  }
}

function cleanWorkspaceSectionLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "";

  const translated = translate(text);

  // NDS custom workspaces use a visible "NDS ERP" suffix. It is branding
  // inside the Workspace label, not part of the browser-tab section name.
  return translated
    .replace(/\s+NDS ERP\s*$/i, "")
    .trim();
}

function getCurrentModule() {
  const frappe = window.frappe;
  if (!frappe) return "";

  const route = getCurrentRoute();

  // For NDS custom Workspace routes, the visible Workspace label is the
  // authoritative section name. Their database module is "Ndserp", which is
  // an app namespace and must never leak into the browser tab.
  if (route[0] === "Workspaces" && route[1]) {
    const workspace = findWorkspace(route[1]);
    if (workspace) {
      const workspaceLabel =
        workspace.label || workspace.title || workspace.name || "";
      const cleaned = cleanWorkspaceSectionLabel(workspaceLabel);
      if (cleaned) return cleaned;
    }
  }

  // DocType routes expose the functional module through loaded metadata.
  if (DOCTYPE_ROUTES.has(route[0]) && route[1]) {
    try {
      const meta = frappe.get_meta?.(route[1]);
      if (meta?.module) return meta.module;
    } catch {
      // Metadata may not be available yet; use the active workspace below.
    }
  }

  // Custom pages/workspace view may expose the module on the live page object.
  const currentPage = frappe.container?.page;
  if (currentPage?._page?.module) return currentPage._page.module;
  if (currentPage?.module) return currentPage.module;

  // Query reports and custom pages can inherit the active workspace module.
  const page = route[0] ? frappe.pages?.[route[0]] : null;
  if (page?.module) return page.module;

  // The sidebar workspace is the best route-independent fallback.
  const sidebarWorkspace = findWorkspace(frappe.app?.sidebar?.sidebar_title);
  if (sidebarWorkspace) {
    const workspaceLabel =
      sidebarWorkspace.label ||
      sidebarWorkspace.title ||
      sidebarWorkspace.name ||
      "";
    const cleaned = cleanWorkspaceSectionLabel(workspaceLabel);
    if (cleaned) return cleaned;
    if (sidebarWorkspace.module) return sidebarWorkspace.module;
  }

  const savedWorkspace = localStorage.getItem("current_page");
  const savedPage = findWorkspace(savedWorkspace);
  if (savedPage) {
    const workspaceLabel =
      savedPage.label || savedPage.title || savedPage.name || "";
    const cleaned = cleanWorkspaceSectionLabel(workspaceLabel);
    if (cleaned) return cleaned;
    if (savedPage.module) return savedPage.module;
  }

  return "";
}

function setFavicon() {
  if (!document.head) return;

  const links = Array.from(document.head.querySelectorAll('link[rel~="icon"]'));

  if (!links.length) {
    const link = document.createElement("link");
    link.rel = "icon";
    link.type = "image/jpeg";
    link.href = LOGO_PATH;
    document.head.appendChild(link);
    return;
  }

  links.forEach((link) => {
    link.rel = "icon";
    link.type = "image/jpeg";
    if (link.getAttribute("href") !== LOGO_PATH) {
      link.setAttribute("href", LOGO_PATH);
    }
  });
}

function currentLanguage() {
  const frappe = window.frappe;
  const lang =
    frappe?.boot?.lang ||
    document.documentElement.getAttribute("lang") ||
    "en";

  return String(lang).toLowerCase().startsWith("ar") ? "ar" : "en";
}

function desiredTitle() {
  const moduleName = getCurrentModule();
  const moduleLabel = translate(moduleName);

  if (!moduleLabel) return SYSTEM_NAME;

  return currentLanguage() === "ar"
    ? `${SYSTEM_NAME} | ${moduleLabel}`
    : `${moduleLabel} | ${SYSTEM_NAME}`;
}

function applyTitle() {
  const nextTitle = desiredTitle();
  if (document.title !== nextTitle) {
    document.title = nextTitle;
  }
  setFavicon();
}

export const browserIdentity = {
  mount() {
    if (window.__ndsBrowserIdentityMounted) return;
    window.__ndsBrowserIdentityMounted = true;

    const mountNow = () => {
      applyTitle();

      const frappe = window.frappe;
      if (frappe?.router?.on) {
        frappe.router.on("change", () => {
          requestAnimationFrame(applyTitle);
        });
      }

      // Frappe updates the title again after some page factories render.
      // Keep the branded tab identity authoritative without patching Core.
      if (document.head) {
        const observer = new MutationObserver(() => {
          applyTitle();
        });
        observer.observe(document.head, {
          childList: true,
          characterData: true,
          subtree: true,
        });
      }
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mountNow, { once: true });
    } else {
      mountNow();
    }
  },
};
