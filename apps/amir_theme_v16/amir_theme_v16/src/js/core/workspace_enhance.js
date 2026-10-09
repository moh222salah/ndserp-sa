/**
 * Workspace / white-sidebar enhancements.
 *
 *  (a) A "＋ new" affordance beside every white-sidebar link that points at a
 *      creatable Document doctype (never a child table, single, report or
 *      dashboard). Click → opens a fresh document of that type.
 *  (b) A topic-matched icon before every link-card group title, so a wall of
 *      cards reads at a glance.
 *
 * Both run through one debounced MutationObserver and are idempotent (each node
 * is marked once), so they survive the workspace's async render and every
 * workspace switch without leaking work or looping.
 */

// One shared module→glyph map, owned by the launcher (see (d) below).
import { MODULE_ICONS, FALLBACK_ICON } from "./desk_launcher.js";

function iconSvg(name, size) {
	return (
		`<svg class="icon icon-${size || "sm"}" aria-hidden="true">` +
		`<use href="#icon-${name}"></use></svg>`
	);
}

// --- (a) creatable-doctype detection ---------------------------------------
// Built once from frappe.boot (no per-link meta fetches): the user's creatable
// doctypes, minus singles, keyed by their route slug.
let slugMap = null;
function getSlugMap() {
	if (slugMap) return slugMap;
	slugMap = {};
	try {
		const singles = new Set(frappe.boot.single_types || []);
		(frappe.boot.user.can_create || []).forEach((dt) => {
			if (!singles.has(dt)) slugMap[frappe.router.slug(dt)] = dt;
		});
	} catch (e) { /* leave empty → no plus buttons */ }
	return slugMap;
}

// A link is a creatable list route only when it is exactly /app|desk/<slug> or
// /app|desk/<slug>/view/… — a specific-doc, report or dashboard route is not.
function listDoctypeFromHref(href) {
	try {
		const parts = new URL(href, location.origin).pathname.split("/").filter(Boolean);
		if (parts.length < 2 || (parts[0] !== "app" && parts[0] !== "desk")) return null;
		if (parts.length > 2 && parts[2] !== "view") return null;
		return getSlugMap()[parts[1]] || null;
	} catch (e) { return null; }
}

function enhanceSidebar() {
	document
		.querySelectorAll(".body-sidebar .standard-sidebar-item a.item-anchor")
		.forEach((a) => {
			if (a.dataset.amtPlus) return; // done once
			const dt = listDoctypeFromHref(a.getAttribute("href"));
			if (!dt) { a.dataset.amtPlus = "0"; return; }
			a.dataset.amtPlus = "1";

			const btn = document.createElement("span");
			btn.className = "amt-sidebar-new";
			btn.title = `${__("New")} ${__(dt)}`;
			btn.setAttribute("role", "button");
			btn.setAttribute("aria-label", `${__("New")} ${__(dt)}`);
			btn.innerHTML = iconSvg("plus", "sm");
			btn.addEventListener("click", (e) => {
				// Don't let the click also follow the row's list link.
				e.preventDefault();
				e.stopPropagation();
				frappe.new_doc(dt);
			});
			a.appendChild(btn);
		});
}

// --- (b) card-title icons ---------------------------------------------------
// First regex that matches the (translated) title or its English keyword wins;
// order runs specific → generic. Every icon id is verified to exist in the
// Lucide sprite this build ships.
// [regex, lucide-icon-id, hue] — hue is one of Frappe's own semantic colour
// tokens (--{hue}-500/600/100, defined in desk.bundle and NOT redefined for
// dark mode — verified live, so a single hue reads correctly in both themes).
// Reusing Frappe's own palette (rather than inventing hex) keeps every chip
// visually "native" to the framework. Grouped by ERP domain so related topics
// share a family (e.g. every stock-movement flavour is teal) while distinct
// domains stay visually distinct — matching the reference: tools=orange,
// settings=gray, serial/batch=purple, stock ledger=teal.
const CARD_ICONS = [
	// specific report/setup phrasings first so they don't fall to a generic topic
	[/الرقم التسلسلي|التشغيلة|serial no|batch|lot tracking/i, "fingerprint", "purple"],
	[/كتالوج|catalog|قائمة الأصناف/i, "book", "blue"],
	[/قائمة الأسعار|price list|أسعار/i, "receipt", "amber"],
	[/حركة المخزون|قيود.*مخزون|stock ledger|stock entr/i, "arrow-left-right", "teal"],
	[/مجموعة الأصناف|item group/i, "boxes", "violet"],
	[/نقطة البيع|pos|point of sale/i, "monitor", "blue"],
	[/ولاء|loyalty|قسيمة|كوبون|coupon/i, "gift", "pink"],
	[/إشعار|notification/i, "bell", "amber"],
	[/عنوان|address|جهة الاتصال|contact info/i, "map-pin", "red"],
	[/منطقة|territory/i, "map", "teal"],
	[/حملة|campaign/i, "megaphone", "pink"],
	[/قالب|template/i, "layout-template", "gray"],
	[/شروط|أحكام|terms/i, "file-text", "gray"],
	[/مصدر utm|utm/i, "link", "cyan"],
	// broad ERP domains
	[/محاسب|حساب|قيد يومي|ledger|accounting|journal/i, "calculator", "violet"],
	[/مدفوع|سداد|دفع|payment|pay/i, "banknote", "green"],
	[/ضريب|ضرائب|tax|vat|withhold/i, "percent", "amber"],
	[/مصرفي|بنك|bank/i, "landmark", "teal"],
	[/ميزاني|موازن|budget/i, "scale", "gray"],
	[/مشتري|شراء|procure|buying|purchase/i, "shopping-cart", "cyan"],
	[/تعاقد.*باطن|subcontract/i, "handshake", "orange"],
	[/مبيع|بيع|selling|sales/i, "trending-up", "green"],
	[/علاقات|عملاء محتمل|فرص|crm|lead|opportunity/i, "users", "pink"],
	[/مورّد|مورد|supplier/i, "truck", "cyan"],
	[/عميل|customer|جهة/i, "contact", "pink"],
	[/مخزون|مستودع|inventory|warehouse|stock/i, "warehouse", "blue"],
	[/أصناف|صنف|item/i, "package", "violet"],
	[/تسليم|توصيل|شحن|توزيع|delivery|shipping/i, "truck", "teal"],
	[/تصنيع|إنتاج|أمر عمل|manufactur|production|work order|bom/i, "factory", "orange"],
	[/جودة|فحص|quality|inspection/i, "shield-check", "teal"],
	[/صيانة|إصلاح|أدوات|maintenance|repair|asset servic|tools?\b/i, "wrench", "orange"],
	[/أصول|asset/i, "building-2", "gray"],
	[/مشروع|مشاريع|مهمة|مهام|project|task|timesheet/i, "briefcase", "violet"],
	[/موارد بشري|موظف|رواتب|hr|human|employee|payroll/i, "user", "teal"],
	[/تقرير رئيسي|main report|التقارير الرئيسية/i, "chart-column", "blue"],
	[/تقارير أخرى|other report/i, "chart-pie", "blue"],
	[/تقرير|تقارير|إحصاء|تحليل|report|analytic|statement/i, "chart-column", "blue"],
	[/لوحة|dashboard/i, "layout-dashboard", "blue"],
	[/مستخدم|صلاحي|أدوار|user|role|permission|audit/i, "users", "gray"],
	[/موقع|ويب|website|web|portal/i, "globe", "cyan"],
	[/دعم|تذكرة|مشكلة|support|ticket|issue|help/i, "life-buoy", "red"],
	[/إعداد|تهيئة|ضبط|settings|setup|config|integration/i, "settings-2", "gray"],
];

// Distinct, visually-different (icon, hue) pairs to fall back to when a page
// would otherwise repeat one — so no two cards on the same screen wear the
// same glyph AND colour.
const FALLBACK_POOL = [
	["layers", "blue"], ["grid", "violet"], ["boxes", "teal"], ["tag", "pink"],
	["clipboard-list", "gray"], ["book", "amber"], ["archive", "orange"],
	["folder-open", "cyan"], ["list", "green"], ["gauge", "red"],
	["wallet", "amber"], ["coins", "green"], ["receipt", "violet"],
	["scale", "gray"], ["ticket", "pink"], ["package", "blue"],
	["briefcase", "teal"], ["component", "cyan"], ["database", "gray"],
	["columns-3", "orange"],
];

function pickCardIcon(title) {
	for (const [re, icon, hue] of CARD_ICONS) if (re.test(title)) return { icon, hue };
	return { icon: "folder-open", hue: "gray" };
}

function enhanceCards() {
	// Icons already on the page (from earlier observer runs) count as "used" so a
	// re-render never duplicates a glyph.
	const used = new Set(
		[...document.querySelectorAll(".amt-card-icon use")].map((u) =>
			(u.getAttribute("href") || "").replace("#icon-", "")
		)
	);
	document
		.querySelectorAll(".widget.links-widget-box .widget-head .widget-title")
		.forEach((titleEl) => {
			if (titleEl.dataset.amtIcon) return;
			titleEl.dataset.amtIcon = "1";
			const label = (titleEl.textContent || "").trim();
			if (!label) return;
			let { icon, hue } = pickCardIcon(label);
			if (used.has(icon)) {
				const fallback = FALLBACK_POOL.find(([f]) => !used.has(f));
				if (fallback) [icon, hue] = fallback;
			}
			used.add(icon);
			const span = document.createElement("span");
			span.className = "amt-card-icon";
			span.dataset.hue = hue;
			span.innerHTML = iconSvg(icon, "sm");
			// Prepend: the icon leads (sits at the header's outer/start edge) and
			// the title text follows on its inner side — the conventional
			// icon-then-label reading order the user asked for.
			titleEl.insertBefore(span, titleEl.firstChild);
		});
}

// --- (c) a plain leading "←" marker before every card link row's label -----
// Frappe's native arrow sits AFTER the label (a diagonal "external-link" glyph,
// `es-line-arrow-up-right`), so its horizontal position depends on that row's
// own text width — every row's arrow lands at a different X, no column at all.
// User-requested fix: a plain (no border/background — just a small icon) LEFT-
// pointing arrow placed BEFORE the label instead. Because `.link-content` is a
// fixed-width, `white-space:nowrap`, `text-align:right` block, a marker
// PREPENDED as its first inline child always renders flush against that same
// right edge regardless of the label's length — every row's arrow lines up in
// one straight vertical column for free, with no manual alignment math needed.
// The native trailing svg is kept in the DOM (untouched, for a11y/semantics)
// but visually hidden via CSS, rather than removed — reversible, zero risk to
// any listener Frappe might attach to it.
function enhanceLinkArrows() {
	document
		.querySelectorAll(".widget.links-widget-box .widget-body > a.link-item")
		.forEach((a) => {
			if (a.dataset.amtArrow) return;
			const content = a.querySelector(":scope > .link-content");
			const nativeSvg = content ? content.querySelector(":scope > svg") : null;
			if (!content || !nativeSvg) { a.dataset.amtArrow = "0"; return; }
			a.dataset.amtArrow = "1";
			nativeSvg.classList.add("amt-native-arrow-hidden");
			const lead = document.createElement("span");
			lead.className = "amt-link-lead-arrow";
			lead.innerHTML = iconSvg("arrow-left", "xs");
			content.insertBefore(lead, content.firstChild);
		});
}

// --- (d) tie the sidebar's module badge icon to the active colour scheme ---
// `.body-sidebar .sidebar-header` shows the current workspace's own ERPNext
// "solid" icon (e.g. buying.svg) via a plain <img>. That file is a two-shape
// SVG — a rounded-square backdrop hard-coded `fill="#0289F7"` (etc, one fixed
// hex per module) plus a white glyph on top — and a browser CANNOT reach
// inside an <img>'s SVG to recolour it from CSS. The only way to make the
// backdrop follow the active scheme is to fetch the raw SVG markup, inline it
// as real DOM (not an <img>), and clear that first path's hard-coded fill so
// `var(--primary)` (set in CSS) takes over. The white glyph path(s) are left
// untouched, so the module stays recognisable — only its backdrop re-colours.
// Fetches are cached by URL (module icons repeat across workspace switches),
// and any failure silently leaves the original <img> in place — this is a
// cosmetic upgrade, never allowed to block or break the sidebar header.
const SVG_NS = "http://www.w3.org/2000/svg";
// ERPNext draws the badge on a 54-unit canvas; keep that so the swap is a
// drop-in and the 36×36 CSS box in _workspace-enhance.scss still applies.
const BADGE_VB = 54;
const BADGE_GLYPH = 26; // Lucide box inside the plate — leaves an 14u margin

/**
 * Frappe's own untranslated workspace key. `sidebar_title` is what Frappe
 * itself compares against `data-workspace`, so it is the authoritative name —
 * never read the visible heading, which is translated.
 */
function currentWorkspaceKey() {
	const sb = window.frappe && frappe.app && frappe.app.sidebar;
	if (sb && typeof sb.sidebar_title === "string" && sb.sidebar_title) return sb.sidebar_title;
	// Fallback: the rail marks the active workspace with the same untranslated key.
	const active = document.querySelector(".amt-rail-item.active[data-workspace]");
	return active ? active.getAttribute("data-workspace") : null;
}

/**
 * Build the badge ourselves instead of patching ERPNext's artwork.
 *
 * ERPNext ships each workspace icon as a two-shape "solid" SVG: a rounded-square
 * backdrop with a hard-coded fill, plus a small white glyph on top. The glyph is
 * the weak part — coarse, inconsistent between modules, and drawn for a canvas
 * far smaller than the 36px it renders at. Recolouring the backdrop (what this
 * function used to do) left that glyph untouched, so the badge stayed crude.
 *
 * Drawing the plate as a <rect> and pulling the glyph from the Lucide sprite
 * Frappe ALREADY inlines gives a crisp vector at any size, and — because the
 * glyph name comes from the same MODULE_ICONS map the desk launcher uses — the
 * badge, the launcher tile and the rail all show one consistent symbol per
 * module. No icon library, no network fetch, no external asset.
 */
function buildBadge(glyph) {
	const svg = document.createElementNS(SVG_NS, "svg");
	svg.setAttribute("class", "amt-module-badge-svg");
	svg.setAttribute("viewBox", `0 0 ${BADGE_VB} ${BADGE_VB}`);
	svg.setAttribute("aria-hidden", "true");
	svg.setAttribute("focusable", "false");
	svg.dataset.amtBadge = glyph;

	const plate = document.createElementNS(SVG_NS, "rect");
	plate.setAttribute("width", BADGE_VB);
	plate.setAttribute("height", BADGE_VB);
	plate.setAttribute("rx", "15"); // same squircle radius as the launcher tiles
	plate.setAttribute("fill", "var(--primary)");
	svg.appendChild(plate);

	// Centre a Lucide symbol on the plate.
	//
	// The x/y/width/height here are load-bearing, not decoration. A <symbol>
	// carries its own viewBox ("0 0 24 24") and maps it onto the <use>'s box; a
	// <use> with no width/height defaults to 100% of the nearest viewport, which
	// is this 54-unit canvas — so the glyph silently inflates to 54 and spills
	// past the plate. Wrapping it in a scaled <g> does NOT fix that (the symbol
	// re-fits to 54 first, then the <g> scales the already-wrong size). Giving
	// the <use> an explicit box is what actually maps 24 units onto 26.
	//
	// Stroke colour/width stay in CSS so the badge follows the active colour
	// scheme (and the dark theme's inverted ink) without a JS branch.
	const use = document.createElementNS(SVG_NS, "use");
	// Same-document reference — a cross-file `href="sprite.svg#id"` would be blocked.
	use.setAttribute("href", `#icon-${glyph}`);
	const offset = (BADGE_VB - BADGE_GLYPH) / 2;
	use.setAttribute("x", offset);
	use.setAttribute("y", offset);
	use.setAttribute("width", BADGE_GLYPH);
	use.setAttribute("height", BADGE_GLYPH);
	svg.appendChild(use);

	return svg;
}

function enhanceModuleBadge() {
	const logo = document.querySelector(".body-sidebar .sidebar-header .header-logo");
	if (!logo) return;

	const key = currentWorkspaceKey();
	if (!key) return; // unknown workspace — leave Frappe's artwork exactly as drawn

	let glyph = MODULE_ICONS[key];
	if (!glyph || !document.getElementById(`icon-${glyph}`)) glyph = FALLBACK_ICON;
	if (!document.getElementById(`icon-${glyph}`)) return; // sprite unavailable — stay inert

	const existing = logo.querySelector(".amt-module-badge-svg");
	if (existing && existing.dataset.amtBadge === glyph) return; // already correct

	// Replace whatever is there: Frappe's <img> on first paint, or our own badge
	// from the previously-open workspace after a switch.
	const target = existing || logo.querySelector("img");
	if (!target) return;
	target.replaceWith(buildBadge(glyph));
}

// --- driver -----------------------------------------------------------------
// --- accounts workspace visual scope ---------------------------------------
// Marks only the NDS Accounts workspace so its stylesheet cannot affect other
// Workspaces, forms, reports, or the rest of Desk.
const ACCOUNTS_WORKSPACE_NAME = "حسابات NDS ERP";

function syncAccountsWorkspaceScope() {
	let route = [];
	try {
		route = typeof frappe.get_route === "function" ? frappe.get_route() : [];
	} catch (e) {
		route = [];
	}

	const routeKind = String(route[0] || "").trim().toLowerCase();
	const routeName = String(route[1] || "").trim();
	let expectedSlug = ACCOUNTS_WORKSPACE_NAME;
	try {
		if (frappe.router && typeof frappe.router.slug === "function") {
			expectedSlug = frappe.router.slug(ACCOUNTS_WORKSPACE_NAME);
		}
	} catch (e) {
		// The raw workspace name remains a valid fallback.
	}

	const activeTitle = document.querySelector(".workspace-title")?.textContent?.trim() || "";
	const nameMatches =
		routeName.toLowerCase() === ACCOUNTS_WORKSPACE_NAME.toLowerCase() ||
		routeName.toLowerCase() === String(expectedSlug).toLowerCase() ||
		activeTitle.toLowerCase() === ACCOUNTS_WORKSPACE_NAME.toLowerCase();

	document.body.classList.toggle(
		"amt-accounts-workspace",
		routeKind === "workspaces" && nameMatches
	);
}

// Mark only the NDS Purchase Workspace so its visual layer cannot affect other pages.
const PURCHASE_WORKSPACE_NAME = "المشتريات NDS ERP";

function syncPurchaseWorkspaceScope() {
	let route = [];
	try {
		route = typeof frappe.get_route === "function" ? frappe.get_route() : [];
	} catch (e) {
		route = [];
	}

	const routeKind = String(route[0] || "").trim().toLowerCase();
	const routeName = String(route[1] || "").trim();
	let expectedSlug = PURCHASE_WORKSPACE_NAME;
	try {
		if (frappe.router && typeof frappe.router.slug === "function") {
			expectedSlug = frappe.router.slug(PURCHASE_WORKSPACE_NAME);
		}
	} catch (e) {
		// Keep the untranslated Workspace name as a safe fallback.
	}

	const activeTitle = document.querySelector(".workspace-title")?.textContent?.trim() || "";
	const activeKey = currentWorkspaceKey() || "";
	const expectedNames = [
		PURCHASE_WORKSPACE_NAME.toLowerCase(),
		String(expectedSlug).toLowerCase(),
	];
	const nameMatches = [routeName, activeTitle, activeKey]
		.some((value) => expectedNames.includes(String(value).trim().toLowerCase()));

	document.body.classList.toggle(
		"nds-purchase-workspace-redesign",
		routeKind === "workspaces" && nameMatches
	);
}

// Mark only the NDS Sales Workspace so its layout styles cannot affect other Desk pages.
const SALES_WORKSPACE_NAME = "المبيعات NDS ERP";

function syncSalesWorkspaceScope() {
	let route = [];
	try {
		route = typeof frappe.get_route === "function" ? frappe.get_route() : [];
	} catch (e) {
		route = [];
	}

	const routeKind = String(route[0] || "").trim().toLowerCase();
	const routeName = String(route[1] || "").trim();
	let expectedSlug = SALES_WORKSPACE_NAME;
	try {
		if (frappe.router && typeof frappe.router.slug === "function") {
			expectedSlug = frappe.router.slug(SALES_WORKSPACE_NAME);
		}
	} catch (e) {
		// The raw workspace name remains a valid fallback.
	}

	const activeTitle = document.querySelector(".workspace-title")?.textContent?.trim() || "";
	const activeKey = currentWorkspaceKey() || "";
	const expectedNames = [
		SALES_WORKSPACE_NAME.toLowerCase(),
		String(expectedSlug).toLowerCase(),
	];
	const nameMatches = [routeName, activeTitle, activeKey]
		.some((value) => expectedNames.includes(String(value).trim().toLowerCase()));

	document.body.classList.toggle(
		"nds-sales-workspace-redesign",
		routeKind === "workspaces" && nameMatches
	);
}

let scheduled = false;
/**
 * Apply a visual-only CSS scope on the warehouse Workspace route.
 * This never changes Workspace data, metrics, links, permissions or business logic.
 */
function syncWarehouseWorkspaceScope() {
	const route = window.frappe && typeof frappe.get_route === "function" ? frappe.get_route() : [];
	const active = Array.isArray(route)
		&& route[0] === "Workspaces"
		&& currentWorkspaceKey() === "مخازن NDS ERP";
	document.documentElement.classList.toggle("nds-warehouse-workspace", Boolean(active));
}

function run() {
	scheduled = false;
	try { syncAccountsWorkspaceScope(); } catch (e) { console.error("[amir_theme] accounts workspace scope failed:", e); }
	try { syncPurchaseWorkspaceScope(); } catch (e) { console.error("[amir_theme] purchase workspace scope failed:", e); }
	try { syncWarehouseWorkspaceScope(); } catch (e) { console.error("[amir_theme] warehouse scope failed:", e); }
	try { syncSalesWorkspaceScope(); } catch (e) { console.error("[amir_theme] sales workspace scope failed:", e); }
	try { enhanceSidebar(); } catch (e) { /* eslint-disable-next-line no-console */ console.error("[amir_theme] sidebar-new failed:", e); }
	try { enhanceCards(); } catch (e) { console.error("[amir_theme] card-icons failed:", e); }
	try { enhanceLinkArrows(); } catch (e) { console.error("[amir_theme] link-arrow chip failed:", e); }
	try { enhanceModuleBadge(); } catch (e) { console.error("[amir_theme] module-badge tint failed:", e); }
}
function schedule() {
	if (scheduled) return;
	scheduled = true;
	setTimeout(run, 250);
}

/*
 * Workspace cards are painted once, asynchronously, when a workspace page
 * loads — so a route change plus a few bounded follow-ups covers them without
 * anything left running afterwards. Same idea (and same delays) as the settle
 * passes in core/desk_host.js.
 */
const SETTLE_DELAYS_MS = [0, 250, 600, 1200];
let settleTimers = [];
function scheduleSettle() {
	settleTimers.forEach(clearTimeout);
	settleTimers = SETTLE_DELAYS_MS.map((ms) => setTimeout(schedule, ms));
}

export const workspaceEnhance = {
	mount() {
		schedule();

		// Route changes cover the workspace body: switching workspace goes through
		// frappe.set_route("Workspaces", …), so every card render is preceded by
		// one of these.
		$(document).on("page-change", scheduleSettle);

		// A persistent observer is still needed for the white sidebar, which
		// re-renders on workspace switch without always changing route — but it is
		// scoped to the sidebar container, NOT the whole layout.
		//
		// This previously read `document.querySelector(".layout-main") || document.body`
		// inside mount(), which runs at $(document).ready — before Frappe has
		// rendered anything. `.layout-main` never existed at that moment, so it
		// ALWAYS fell through to document.body and observed the entire desk,
		// childList+subtree, for the whole session and was never disconnected.
		// Every datatable row of every report re-triggered this driver's four
		// document-wide querySelectorAll sweeps.
		//
		// The container is replaced when Frappe rebuilds the sidebar, so it is
		// tracked by identity and rebound, as in core/desk_host.js.
		let observer = null;
		let watched = null;

		const rebindSidebar = () => {
			const root = document.querySelector(".body-sidebar-container");
			if (!root || !root.isConnected) return;
			if (watched === root) return;
			if (observer) observer.disconnect();
			watched = root;
			observer = new MutationObserver(schedule);
			observer.observe(root, { childList: true, subtree: true });
			schedule();
		};

		rebindSidebar();
		$(document).on("page-change sidebar_setup", () => setTimeout(rebindSidebar, 0));

		// The sidebar container itself does not exist at document.ready either, so
		// wait for it once, then stop. Bounded: gives up after 15s like desk_host.
		if (!document.querySelector(".body-sidebar-container")) {
			const boot = new MutationObserver(() => {
				if (!document.querySelector(".body-sidebar-container")) return;
				boot.disconnect();
				rebindSidebar();
			});
			boot.observe(document.body, { childList: true, subtree: true });
			setTimeout(() => boot.disconnect(), 15000);
		}
	},
};
