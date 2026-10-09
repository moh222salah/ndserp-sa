import { deskLauncher } from "./core/desk_launcher.js";
import { quickActions } from "./core/desk_quick_actions.js";
import { deskStatusBar } from "./core/desk_statusbar.js";
import { refreshDeskHost } from "./core/desk_host.js";
import { hijriDate } from "./core/hijri_date.js";
import { reportAutofit } from "./core/report_autofit.js";
import { colorScheme } from "./core/color_scheme.js";
import { workspaceEnhance } from "./core/workspace_enhance.js";
import { smartSubmitActions } from "./core/smart_submit_actions.js";
import { translationToggle } from "./core/translation_toggle.js";
import { progressBar } from "./core/progress_bar.js";
import { consoleHygiene } from "./core/console_hygiene.js";
import { quickEntryFix } from "./core/quick_entry_fix.js";
import { browserIdentity } from "./core/browser_identity.js";

// Install the browser-title guard immediately at bundle evaluation time.
// This closes the gap before DOM ready where Frappe may write its default title.
browserIdentity.mount();

// Silence two harmless frappe-charts noise sources (one is an uncaught error)
// as early as possible, before any chart renders. See the module for details.
consoleHygiene.install();

// Patches QuickEntryForm.prototype once, before any dialog can be opened, so
// editing a Desktop Icon from the apps screen stops failing with
// `"doctype" is a required key`. See the module for the full trace.
quickEntryFix.install();

/* ============================================
   FEATURE SWITCHES — "Amir Theme Settings"
   ============================================
   Server-side single doctype, delivered on `frappe.boot.amt_settings` by
   amir_theme_v16/boot.py. Read synchronously (never fetched) because every
   feature gated below mounts during `$(document).ready` — a `frappe.call`
   could not resolve in time, and a prototype patch applied late is worse than
   not applied at all.

   The fallbacks matter: on a site that has the theme but has not migrated the
   settings doctype yet, `amt_settings` is simply absent and every feature must
   stay ON, exactly as it behaved before the switches existed. Nothing here is
   a permission — these are cosmetic UI flags only. */
const AMT_SETTING_DEFAULTS = {
	enable_hijri_dates: 1,
	enable_smart_actions: 1,
	enable_translation_mode: 1,
	enable_color_schemes: 1,
	language_switcher_position: "Navbar",
};

function amtSetting(key) {
	const configured = (window.frappe && frappe.boot && frappe.boot.amt_settings) || {};
	const value = configured[key];
	return value === undefined || value === null ? AMT_SETTING_DEFAULTS[key] : value;
}

function amtEnabled(key) {
	return Boolean(Number(amtSetting(key)));
}

// Re-apply the saved colour scheme as early as the bundle executes, before the
// rail/content paint, so there is no flash of the default palette. This runs
// even when the *picker* is switched off: the setting hides the affordance,
// it does not throw away a palette the user already chose.
colorScheme.applyEarly();

/*
 * Amir Theme v16 - Dual Sidebar + User Menu
 * Derived from "Saas Theme" by CommitStreet (MIT).
 *
 * Architecture:
 *   [Workspace Rail 56px] [Sidebar Panel ~220px] [Main Content]
 *
 * The rail shows workspace icons from frappe.boot.desktop_icons.
 * Clicking an icon switches the sidebar panel to that workspace.
 * Rail only shows when the sidebar panel is also visible.
 */

$(document).ready(function () {
	if (!frappe.boot.setup_complete) return;

	frappe.after_ajax(function () {
		amir_theme.sidebar.init();
		amir_theme.attachments.init();
	});

	// Re-init on sidebar_setup in case frappe.after_ajax fired too early
	$(document).on("sidebar_setup", function () {
		if (!amir_theme.sidebar.rail_built) {
			amir_theme.sidebar.init();
		}
		amir_theme.sidebar.setup_user_menu();
	});
});

frappe.provide("amir_theme.sidebar");
frappe.provide("amir_theme.attachments");

amir_theme.sidebar = {
	rail_built: false,

	init() {
		this.restore_rail_state();
		this.build_workspace_rail();
		this.setup_user_menu();
		if (!this._listeners_bound) {
			this.listen_for_changes();
			this._listeners_bound = true;
		}
		this.toggle_rail_visibility();
	},

	/* ============================================
	   WORKSPACE RAIL
	   ============================================ */

	build_workspace_rail() {
		if (this.rail_built) return;

		const workspaces = this.get_workspaces();
		if (!workspaces.length) return;

		let icons_html = "";
		let prev_group = null;
		workspaces.forEach((ws) => {
			// Flag the first row of each band; the divider is drawn in CSS as a
			// border on that row, so no extra nodes enter the flex flow.
			const starts_group = prev_group !== null && ws._group !== prev_group;
			prev_group = ws._group;
			const icon_content = this.get_icon_for_workspace(ws);
			// `data-workspace` stays the untranslated name — it is the key passed to
			// frappe.app.sidebar.setup() and compared against sidebar_title. Only the
			// text the user reads gets translated.
			const key = frappe.utils.escape_html(ws.label);
			// KEY stays the untranslated workspace name (used for switching);
			// only the human-readable label is re-titled + translated.
			const label_base = this.RAIL_LABEL_OVERRIDES[ws.label] || ws.label;
			const display = frappe.utils.escape_html(__(label_base));
			icons_html += `
				<div class="amt-rail-item${starts_group ? " amt-rail-group-start" : ""}"
					data-workspace="${key}"
					data-label="${display}"
					data-group="${frappe.utils.escape_html(ws._group || "")}">
					<div class="amt-rail-icon">
						${icon_content}
					</div>
					<span class="amt-rail-label">${display}</span>
					<span class="amt-rail-tooltip">${display}</span>
				</div>`;
		});

		const search_svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`;
		const chevrons_svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 17 5-5-5-5"/><path d="m13 17 5-5-5-5"/></svg>`;
		const globe_svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;

		this.$rail = $(`
			<div class="amt-workspace-rail">
				<div class="amt-rail-search">
					<div class="amt-rail-search-btn" title="${__("Search workspaces")}">
						${search_svg}
					</div>
					<div class="amt-rail-search-box">
						${search_svg}
						<input type="text" placeholder="${__("Search")}" spellcheck="false">
						<span class="amt-rail-search-clear" title="${__("Clear")}">&times;</span>
					</div>
				</div>
				<div class="amt-rail-top">
					${icons_html}
				</div>
				<div class="amt-rail-empty">${__("No workspaces found")}</div>
				<div class="amt-rail-bottom">
					${
						amtSetting("language_switcher_position") === "Sidebar Rail"
							? `<div class="amt-rail-lang" title="${__("Switch language")}">
						${globe_svg}
						<span class="amt-rail-lang-code"></span>
					</div>`
							: ""
					}
					<div class="amt-rail-toggle" title="${__("Expand / collapse")}">
						${chevrons_svg}
					</div>
				</div>
				<div class="amt-rail-resizer"></div>
			</div>
		`);

		$(".body-sidebar-container").before(this.$rail);

		// Click handler
		this.$rail.find(".amt-rail-item").on("click", function () {
			const ws_name = $(this).data("workspace");
			amir_theme.sidebar.switch_workspace(ws_name);
		});

		// Tooltips — move to body and position with JS
		this.$rail.find(".amt-rail-tooltip").each(function () {
			$(this).appendTo("body");
		});

		this.$rail.find(".amt-rail-item").on("mouseenter", function () {
			// Labels are visible in expanded mode — no tooltip needed
			if (document.body.classList.contains("amt-rail-expanded")) return;

			const label = $(this).data("label");
			const $tip = $("body > .amt-rail-tooltip").filter(function () {
				return $(this).text().trim() === label;
			});
			if (!$tip.length) return;

			const rect = this.getBoundingClientRect();
			// In RTL the rail sits on the right, so the tooltip must flip to the left edge.
			const is_rtl = document.documentElement.getAttribute("dir") === "rtl";
			$tip.css({
				top: rect.top + rect.height / 2 - $tip.outerHeight() / 2,
				left: is_rtl ? rect.left - $tip.outerWidth() - 10 : rect.right + 10,
			}).addClass("visible");
		}).on("mouseleave", function () {
			$("body > .amt-rail-tooltip").removeClass("visible");
		});

		this.setup_rail_search();
		this.setup_rail_toggle();
		this.setup_rail_resizer();
		this.setup_language_toggle();
		if (amtEnabled("enable_color_schemes")) colorScheme.attach(this.$rail);
		if (amtEnabled("enable_translation_mode")) translationToggle.attach(this.$rail);

		this.rail_built = true;
		this.update_rail_active();
	},

	/* ============================================
	   RAIL EXPAND / COLLAPSE + SEARCH
	   ============================================ */

	restore_rail_state() {
		let expanded = false;
		try {
			expanded = localStorage.getItem("amt_rail_expanded") === "1";
		} catch (e) {
			// localStorage unavailable — stay collapsed
		}
		$("body").toggleClass("amt-rail-expanded", expanded);
	},

	set_rail_expanded(expanded) {
		$("body").toggleClass("amt-rail-expanded", !!expanded);
		try {
			localStorage.setItem("amt_rail_expanded", expanded ? "1" : "0");
		} catch (e) {
			// non-persistent, still works for the session
		}
		$("body > .amt-rail-tooltip").removeClass("visible");
		if (!expanded && this.$rail) {
			// Collapsing hides the search box — drop any active filter with it
			this.$rail.find(".amt-rail-search-box input").val("");
			this.filter_rail("");
		}
	},

	/* ============================================
	   LANGUAGE TOGGLE (AR / EN)
	   ============================================ */

	current_lang() {
		// boot.lang is authoritative; fall back to the served <html lang>.
		return (
			frappe.boot?.lang ||
			document.documentElement.getAttribute("lang") ||
			"en"
		).toLowerCase().startsWith("ar")
			? "ar"
			: "en";
	},

	/** Wire one language-switch control, wherever it lives. Shared by the rail
	 * and the navbar placements so the switching logic exists exactly once. */
	bind_language_control($btn, $code) {
		if (!$btn || !$btn.length) return;

		const render = () => {
			const next = this.current_lang() === "ar" ? "EN" : "ع";
			if ($code && $code.length) $code.text(next);
			$btn.attr(
				"title",
				this.current_lang() === "ar"
					? __("Switch to English")
					: __("Switch to Arabic")
			);
		};
		render();

		$btn.on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			if (this._lang_switching) return; // double-click would fire two reloads
			this._lang_switching = true;
			$btn.addClass("amt-busy");

			const target = this.current_lang() === "ar" ? "en" : "ar";

			frappe.call({
				method: "amir_theme_v16.api.language.set_language",
				args: { lang: target },
				callback: () => {
					// A full reload is required, not just a re-render: the language
					// determines dir=rtl/ltr and which CSS bundle (ltr vs rtl) the
					// server injects. Both are decided server-side at page render.
					window.location.reload();
				},
				error: () => {
					this._lang_switching = false;
					$btn.removeClass("amt-busy");
					frappe.show_alert({
						message: __("Could not switch language"),
						indicator: "red",
					});
				},
			});
		});
	},

	setup_language_toggle() {
		// Only present when the setting puts the switcher on the rail; the
		// markup is omitted entirely otherwise (see build_rail).
		const $btn = this.$rail.find(".amt-rail-lang");
		if (!$btn.length) return;
		this.bind_language_control($btn, $btn.find(".amt-rail-lang-code"));
	},

	/* ============================================
	   LANGUAGE TOGGLE — NAVBAR PLACEMENT
	   ============================================
	   v16's desk has no Bootstrap `.navbar`; the top bar is `.page-head`, and
	   Frappe builds ONE PER PAGE, swapping which is visible on navigation. So
	   this cannot be a single one-time injection into a global header — the
	   button is injected into every page head that doesn't have it yet, on
	   ready and again after each page-change. Injection is idempotent (guarded
	   by the `.amt-nav-lang` class), so repeats are free.

	   `.standard-items-section` is the right-hand cluster that already holds
	   the page's own action buttons, which is why the switcher lands beside
	   them and inherits the header's alignment in both LTR and RTL. */
	mount_navbar_language_toggle() {
		if (amtSetting("language_switcher_position") !== "Navbar") return;

		const me = this;
		const globe_svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`;

		const inject = () => {
			$(".page-head-content .standard-items-section").each(function () {
				const $section = $(this);
				if ($section.find(".amt-nav-lang").length) return;

				const $btn = $(
					`<button type="button" class="btn-reset amt-nav-lang" aria-label="${__(
						"Switch language"
					)}">${globe_svg}<span class="amt-nav-lang-code"></span></button>`
				);

				$section.prepend($btn);
				me.bind_language_control($btn, $btn.find(".amt-nav-lang-code"));
			});
		};

		inject();
		// Page heads are created lazily as routes are first visited.
		$(document).on("page-change", () => setTimeout(inject, 120));
	},

	setup_rail_toggle() {
		const me = this;
		this.$rail.find(".amt-rail-toggle").on("click", () => {
			me.set_rail_expanded(!$("body").hasClass("amt-rail-expanded"));
		});
	},

	setup_rail_search() {
		const me = this;
		const $input = this.$rail.find(".amt-rail-search-box input");

		// Collapsed mode: the search icon expands the rail and focuses the input
		this.$rail.find(".amt-rail-search-btn").on("click", () => {
			me.set_rail_expanded(true);
			setTimeout(() => $input.trigger("focus"), 220);
		});

		$input.on("input", () => me.filter_rail($input.val()));

		$input.on("keydown", (e) => {
			if (e.key === "Escape") {
				$input.val("");
				me.filter_rail("");
				$input.trigger("blur");
			} else if (e.key === "Enter") {
				const $first = me.$rail.find(".amt-rail-item:not(.amt-rail-hidden)").first();
				if ($first.length) $first.trigger("click");
			}
		});

		this.$rail.find(".amt-rail-search-clear").on("click", () => {
			$input.val("");
			me.filter_rail("");
			$input.trigger("focus");
		});
	},

	filter_rail(query) {
		if (!this.$rail) return;
		const q = (query || "").toLowerCase().trim();
		let visible = 0;

		this.$rail.find(".amt-rail-item").each(function () {
			// Match the English key *and* the translated label, so searching works
			// whichever language the user is thinking in.
			const key = String($(this).data("workspace") || "").toLowerCase();
			const label = String($(this).data("label") || "").toLowerCase();
			const match = !q || key.includes(q) || label.includes(q);
			$(this).toggleClass("amt-rail-hidden", !match);
			if (match) visible++;
		});

		this.$rail.toggleClass("amt-filtering", !!q);
		this.$rail.find(".amt-rail-empty").toggleClass("visible", !!q && visible === 0);
	},

	setup_rail_resizer() {
		const me = this;
		const rail = this.$rail[0];
		const MIN = 60;
		const MAX = 184;

		this.$rail.find(".amt-rail-resizer").on("mousedown", function (e) {
			e.preventDefault();
			const start_x = e.clientX;
			const start_w = rail.getBoundingClientRect().width;
			$("body").addClass("amt-rail-resizing");

			const on_move = (ev) => {
				const w = Math.min(MAX, Math.max(MIN, start_w + (ev.clientX - start_x)));
				rail.style.width = w + "px";
				rail.style.minWidth = w + "px";
			};

			const on_up = () => {
				$(document).off("mousemove", on_move).off("mouseup", on_up);
				$("body").removeClass("amt-rail-resizing");
				const w = rail.getBoundingClientRect().width;
				rail.style.width = "";
				rail.style.minWidth = "";
				// Snap to the nearest state
				me.set_rail_expanded(w > (MIN + MAX) / 2);
			};

			$(document).on("mousemove", on_move).on("mouseup", on_up);
		});
	},

	/* Rail display-label overrides (SIDEBAR ONLY).
	   Re-titles a workspace *as shown in the rail* without touching the Workspace
	   record, its page, or the global translation of the original word. The value
	   is a translation base string, so both languages resolve it:
	     Invoicing        -> __("Accounts")            = "الحسابات"
	     Organization     -> __("Company Master Data") = "بيانات المؤسسة (الشركة)"
	   The rail KEY (data-workspace) still carries the real workspace name, so
	   switch_workspace() / update_rail_active() keep working unchanged. */
	RAIL_LABEL_OVERRIDES: {
		Invoicing: "Accounts",
		Organization: "Company Master Data",
	},

	/* Rail order (SIDEBAR ONLY).
	   The erpnext band is arranged as an operator's working day rather than the
	   framework's insertion order: core ledger first, then the trade cycle
	   (sell → buy → stock → make), delivery, treasury, reporting, and finally the
	   advanced/config surfaces. Labels absent here keep their original relative
	   order after the listed ones (robust to newly installed workspaces). Bands
	   still apply first (see GROUP_ORDER), so this only ranks within a band. */
	RAIL_ORDER: [
		"Invoicing",         // الحسابات
		"Selling",           // المبيعات
		"Buying",            // المشتريات
		"Stock",             // المخزون
		"Manufacturing",     // التصنيع
		"Projects",          // المشاريع
		"Assets",            // الأصول
		"Quality",           // الجودة
		"Payments",          // المدفوعات
		"Taxes",             // الضرائب
		"Banking",           // الخدمات المصرفية
		"Budget",            // الميزانية التقديرية
		"Financial Reports", // التقارير المالية
		"Subcontracting",    // التعاقد من الباطن
		"Share Management",  // إدارة الأسهم
		"Subscription",      // الاشتراك
		"Accounts Setup",    // إعداد الحسابات
		"Organization",      // بيانات المؤسسة (الشركة)
		"ERPNext Settings",  // إعدادات ERPNext
	],

	/* Rail grouping.
	   Every workspace carries an owning `app`. Ungrouped, the rail renders one
	   flat alphabetical run where "Build" and "Data" sit between "Buying" and
	   "Selling" — daily business modules buried among framework internals.
	   We sort into three bands and draw a hairline between them.
	   Order is by how often an ERP operator actually needs them. */
	GROUP_ORDER: ["erpnext", "custom", "frappe"],

	group_of(icon, sidebar_items) {
		const app = icon.app || sidebar_items[icon.label.toLowerCase()]?.app;
		if (app === "frappe") return "frappe";
		if (app === "erpnext") return "erpnext";
		// Anything else is a locally installed app — keep those together and
		// above the framework band, since they are usually purpose-built.
		return "custom";
	},

	get_workspaces() {
		const icons = frappe.boot.desktop_icons || [];
		const sidebar_items = frappe.boot.workspace_sidebar_item || {};

		const visible = icons.filter((icon) => {
			return (
				icon.hidden !== 1 &&
				icon.link_type === "Workspace Sidebar" &&
				sidebar_items[icon.label.toLowerCase()]
			);
		});

		// Stable sort: band first, then our curated business order within the
		// band, then the order Frappe already gave us for anything not listed —
		// so nothing is lost and unlisted workspaces keep their relative order.
		const rank_of = (label) => {
			const r = this.RAIL_ORDER.indexOf(label);
			return r === -1 ? this.RAIL_ORDER.length : r;
		};
		return visible
			.map((icon, i) => ({
				icon,
				i,
				g: this.group_of(icon, sidebar_items),
				r: rank_of(icon.label),
			}))
			.sort((a, b) => {
				const d =
					this.GROUP_ORDER.indexOf(a.g) - this.GROUP_ORDER.indexOf(b.g);
				if (d !== 0) return d;
				if (a.r !== b.r) return a.r - b.r;
				return a.i - b.i;
			})
			.map((x) => Object.assign({}, x.icon, { _group: x.g }));
	},

	get_icon_for_workspace(ws) {
		const sidebar_data = frappe.boot.workspace_sidebar_item[ws.label.toLowerCase()];
		if (sidebar_data && sidebar_data.header_icon) {
			return frappe.utils.icon(sidebar_data.header_icon, "md", "", "", "", true);
		}

		const letter = ws.label.charAt(0).toUpperCase();
		return `<span class="amt-rail-initials">${letter}</span>`;
	},

	switch_workspace(workspace_name) {
		if (!workspace_name) return;

		// A rail item is a *Workspace Sidebar* (a grouping), NOT necessarily a
		// Workspace page. Only some sidebars (Selling, Buying, Invoicing…) begin
		// with a `link_type=Workspace` "Home" item whose page shares the sidebar
		// name — for those, routing to Workspaces/<name> happens to land right.
		// Others (Payments, Taxes, Banking…) have NO Workspace page at all: their
		// first item is a Dashboard or a DocType. Blindly routing to
		// Workspaces/<name> there hits a page that doesn't exist and crashes core
		// workspace.js (`Cannot read properties of undefined (reading 'name')`),
		// leaving the main area blank.
		//
		// Fix: open the sidebar's FIRST navigable item, preferring the module
		// landing page (Home workspace) → Dashboard → any other link. This is the
		// smart "fall back to لوحة المعلومات when there's no الرئيسية" behaviour.
		const sidebar = (frappe.boot.workspace_sidebar_item || {})[
			workspace_name.toLowerCase()
		];
		const target = sidebar && this.pick_landing_item(sidebar.items);

		if (!target) {
			// Nothing navigable resolved (mis-configured / empty sidebar). Just
			// swap the sidebar panel and stay put — never route into the crash.
			try {
				frappe.app.sidebar.setup(workspace_name);
			} catch (e) {
				console.warn("[amir_theme] cannot open sidebar", workspace_name, e);
			}
			return;
		}

		this.route_to_sidebar_item(target, workspace_name);
	},

	/* Choose the item a rail click should land on. Sidebars are authored so the
	   FIRST navigable item is the intended landing: a module Home (Workspace) for
	   Selling/Buying/Invoicing, a Dashboard (لوحة المعلومات) for Payments, a plain
	   DocType for Taxes. So we simply take the first item in document order —
	   Section Breaks and destination-less items skipped.

	   One guard: never return a Workspace item whose page does not actually exist
	   (a deleted/renamed workspace, or a cross-module link). Routing to a missing
	   Workspace page is the exact bug that blanked the screen; if the first item
	   is such a link we skip past it to the next real destination instead. */
	pick_landing_item(items) {
		const navigable = (items || []).filter(
			(it) =>
				it &&
				it.type === "Link" &&
				(it.link_to || (it.link_type === "URL" && it.url))
		);
		const workspace_exists = (name) =>
			!!(frappe.workspaces || {})[frappe.router.slug(name)];
		return (
			navigable.find(
				(it) => it.link_type !== "Workspace" || workspace_exists(it.link_to)
			) ||
			navigable[0] ||
			null
		);
	},

	/* Navigate to a resolved sidebar item, mirroring core sidebar_item.get_path,
	   and pin the sidebar panel so the correct one opens regardless of which
	   sidebar the route resolver would otherwise infer. */
	route_to_sidebar_item(item, sidebar_name) {
		// Pin the intended sidebar AFTER the route resolves, via a one-shot router
		// listener — NOT via frappe.route_options. A `sidebar` key placed in
		// route_options leaks into the List view, which consumes route_options as
		// filters (list_view.js parse_filters_from_route_options) and then warns
		// "Unable to find sidebar in any table related to <doctype>" (meta.js).
		// Frappe's own set_workspace_sidebar runs first on the change event and
		// usually already picks the right one (our landing items are sidebar-unique),
		// so this correction is typically a no-op; it only re-runs setup when the
		// resolver landed on a different sidebar than the one the user clicked.
		const pin_sidebar = () => {
			frappe.router.once("change", () => {
				try {
					const sb = frappe.app.sidebar;
					if (
						sb &&
						sb.sidebar_title !== sidebar_name &&
						frappe.boot.workspace_sidebar_item[sidebar_name.toLowerCase()]
					) {
						sb.setup(sidebar_name);
					}
				} catch (e) {
					/* noop */
				}
			});
		};

		// URLs leave the desk — open without touching the router.
		if (item.link_type === "URL") {
			if (item.url) window.open(item.url, item.url.startsWith("http") ? "_blank" : "_self");
			return;
		}

		// Workspace pages route through the Workspaces view directly.
		if (item.link_type === "Workspace") {
			pin_sidebar();
			frappe.set_route("Workspaces", item.link_to);
			return;
		}

		// Everything else (Dashboard / DocType / Report / Page) reuses core's own
		// route generator so filters, report types and route_options stay correct.
		const args = { type: item.link_type, name: item.link_to, tab: item.tab };
		if (item.link_type === "Report" && item.report) {
			args.is_query_report =
				item.report.report_type === "Query Report" ||
				item.report.report_type === "Script Report";
			args.report_ref_doctype = item.report.ref_doctype;
		}
		if (item.link_type === "DocType") {
			if (item.filters) {
				args.doc_view = "List";
				args.route_options = JSON.parse(
					frappe.utils.get_filter_as_json(JSON.parse(item.filters))
				);
			} else if (item.route_options) {
				args.doc_view = "List";
				args.route_options = JSON.parse(item.route_options);
			}
		}
		if (item.link_type === "Page" && item.route_options) {
			args.route_options = JSON.parse(item.route_options);
		}

		let path;
		try {
			path = frappe.utils.generate_route(args);
		} catch (e) {
			console.warn("[amir_theme] could not build route for", item, e);
		}
		if (!path) {
			// Last-resort fallback: at least surface the right sidebar panel.
			try {
				frappe.app.sidebar.setup(sidebar_name);
			} catch (e) {
				/* noop */
			}
			return;
		}

		// generate_route may set frappe.route_options (legitimate list filters);
		// we no longer touch route_options — pin the sidebar via the router event.
		pin_sidebar();
		frappe.set_route(path);
	},

	update_rail_active() {
		const current = (frappe.app.sidebar.sidebar_title || "").toLowerCase();

		$(".amt-rail-item").removeClass("active");
		$(".amt-rail-item").each(function () {
			const ws = $(this).data("workspace");
			if (ws && ws.toLowerCase() === current) {
				$(this).addClass("active");
			}
		});
	},

	toggle_rail_visibility() {
		if (!this.$rail) return;

		const sidebar_visible = $(".body-sidebar-container").is(":visible");
		const page = frappe.container?.page?.page;
		const hide = page?.hide_sidebar;

		if (sidebar_visible && !hide) {
			this.$rail.show();
			$("body").addClass("amt-dual-sidebar");
		} else {
			this.$rail.hide();
			$("body").removeClass("amt-dual-sidebar");
		}
	},

	ensure_sidebar_content() {
		// If sidebar panel is visible but has no items, force a re-setup
		const $top = $(".body-sidebar .body-sidebar-top");
		if (!$top.length) return;

		const has_items = $top.find(".standard-sidebar-item").length > 0;
		if (has_items) return;

		// Try to find the right workspace for the current route
		const route = frappe.get_route();
		if (!route || !route.length) return;

		const entity = route.length >= 2 ? route[1] : route[0];
		if (!entity || !frappe.app.sidebar) return;

		// Check if entity maps to a workspace
		const sidebars = frappe.app.sidebar.get_workspace_sidebars
			? frappe.app.sidebar.get_workspace_sidebars(entity)
			: [];

		if (sidebars.length) {
			frappe.app.sidebar.setup(sidebars[0]);
		} else if (frappe.app.sidebar.sidebar_title) {
			// Re-setup current sidebar to force re-render
			frappe.app.sidebar.setup(frappe.app.sidebar.sidebar_title);
		}
	},

	listen_for_changes() {
		const me = this;

		$(document).on("sidebar_setup", () => {
			setTimeout(() => {
				me.update_rail_active();
				me.toggle_rail_visibility();
			}, 50);
		});

		$(document).on("page-change", () => {
			setTimeout(() => {
				me.update_rail_active();
				me.toggle_rail_visibility();
				me.ensure_sidebar_content();
			}, 100);
		});

		$(document).on("form-refresh", () => {
			setTimeout(() => {
				me.toggle_rail_visibility();
				me.ensure_sidebar_content();
			}, 200);
		});
	},

	/* ============================================
	   USER MENU
	   ============================================ */

	setup_user_menu() {
		const $sidebar = $(".body-sidebar");
		const $user_btn = $sidebar.find(
			".dropdown-navbar-user .sidebar-user-button"
		);

		if (!$user_btn.length) return;

		$user_btn.removeAttr("onclick");
		$user_btn.off("click");

		$user_btn.on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.toggle_user_menu();
		});

		if (!this._user_menu_doc_bound) {
			$(document).on("click.amt_user_menu", (e) => {
				if (
					!$(e.target).closest(".amt-user-menu").length &&
					!$(e.target).closest(".dropdown-navbar-user").length
				) {
					this.close_user_menu();
				}
			});
			this._user_menu_doc_bound = true;
		}
	},

	toggle_user_menu() {
		if ($(".amt-user-menu").length) {
			$(".amt-user-menu").remove();
			return;
		}
		this.show_user_menu();
	},

	close_user_menu() {
		$(".amt-user-menu").remove();
	},

	show_user_menu() {
		const user_fullname = frappe.session.user_fullname;
		const user_email = frappe.session.user_email;
		const user_avatar = frappe.avatar(frappe.session.user, "avatar-large");
		const version = frappe.boot.versions?.frappe
			? `v${frappe.boot.versions.frappe}`
			: "";

		const menu_items = [
			// Open the current user's User document (/app/user/<email>), NOT the
			// social "user-profile" page — that page 500s in this install
			// (share-modal null + desk_page.getpage failure). encodeURIComponent
			// turns the @ into %40 so the route resolves cleanly.
			{
				label: __("My Settings"),
				icon: "setting",
				href: `/app/user/${encodeURIComponent(frappe.session.user)}`,
			},
			{ label: __("Integrations"), icon: "folder", href: "/app/installed-applications" },
			{ label: __("History"), icon: "clock", href: "/app/activity-log" },
			{ divider: true },
			{ label: __("Logout"), icon: "logout", action: "logout" },
		];

		let items_html = "";
		menu_items.forEach((item) => {
			if (item.divider) {
				items_html += '<div class="amt-user-menu-divider"></div>';
			} else if (item.highlight) {
				items_html += `
					<a class="amt-user-menu-item highlight"
						${item.href ? `href="${item.href}"` : ""}
						data-action="${item.action || ""}">
						<span class="amt-menu-dot"></span>
						<span>${item.label}</span>
					</a>`;
			} else {
				items_html += `
					<a class="amt-user-menu-item"
						${item.href ? `href="${item.href}"` : ""}
						data-action="${item.action || ""}">
						${item.icon ? `<span class="amt-menu-icon">${frappe.utils.icon(item.icon, "sm")}</span>` : ""}
						${item.star ? '<span class="amt-menu-star">&#9734;</span>' : ""}
						<span>${item.label}</span>
					</a>`;
			}
		});

		const $menu = $(`
			<div class="amt-user-menu">
				<div class="amt-user-menu-header">
					<div class="amt-user-menu-avatar">${user_avatar}</div>
					<div class="amt-user-menu-info">
						<div class="amt-user-menu-name">${user_fullname}</div>
						<div class="amt-user-menu-email">${user_email}</div>
					</div>
				</div>
				<div class="amt-user-menu-divider"></div>
				<div class="amt-user-menu-items">${items_html}</div>
				${version ? `<div class="amt-user-menu-footer">${version} &middot; ${__("Terms & Conditions")}</div>` : ""}
			</div>
		`);

		$(".body-sidebar").append($menu);

		$menu.find(".amt-user-menu-item").on("click", function (e) {
			const action = $(this).data("action");
			if (action) {
				e.preventDefault();
				amir_theme.sidebar.handle_menu_action(action);
				amir_theme.sidebar.close_user_menu();
			}
		});
	},

	handle_menu_action(action) {
		switch (action) {
			case "logout":
				frappe.app.logout();
				break;
		}
	},
};

/* ============================================
   ATTACHMENT ENHANCEMENTS
   ============================================ */

amir_theme.attachments = {
	ext_map: {
		pdf:  { label: "PDF",  cls: "amt-pdf" },
		doc:  { label: "DOC",  cls: "amt-doc" },
		docx: { label: "DOC",  cls: "amt-doc" },
		xls:  { label: "XLS",  cls: "amt-xls" },
		xlsx: { label: "XLS",  cls: "amt-xls" },
		csv:  { label: "CSV",  cls: "amt-xls" },
		png:  { label: "PNG",  cls: "amt-img" },
		jpg:  { label: "JPG",  cls: "amt-img" },
		jpeg: { label: "JPG",  cls: "amt-img" },
		gif:  { label: "GIF",  cls: "amt-img" },
		svg:  { label: "SVG",  cls: "amt-img" },
		webp: { label: "IMG",  cls: "amt-img" },
		zip:  { label: "ZIP",  cls: "amt-zip" },
		gz:   { label: "GZ",   cls: "amt-zip" },
		rar:  { label: "RAR",  cls: "amt-zip" },
		"7z": { label: "7Z",   cls: "amt-zip" },
		js:   { label: "JS",   cls: "amt-code" },
		py:   { label: "PY",   cls: "amt-code" },
		json: { label: "JSON", cls: "amt-code" },
		html: { label: "HTML", cls: "amt-code" },
		css:  { label: "CSS",  cls: "amt-code" },
		txt:  { label: "TXT",  cls: "amt-file" },
		ppt:  { label: "PPT",  cls: "amt-doc" },
		pptx: { label: "PPT",  cls: "amt-doc" },
	},

	init() {
		this.listen();
	},

	get_file_info(filename) {
		if (!filename) return { label: "FILE", cls: "amt-file" };
		const ext = filename.split(".").pop().toLowerCase();
		return this.ext_map[ext] || { label: ext.substring(0, 4).toUpperCase(), cls: "amt-file" };
	},

	enhance_all() {
		const me = this;
		$(".form-sidebar .attachment-row:not(.amt-enhanced)").each(function () {
			me.enhance_row($(this));
		});
	},

	enhance_row($row) {
		const $pill = $row.find(".data-pill");
		if (!$pill.length) return;

		const $label_link = $pill.find(".attachment-file-label");
		if (!$label_link.length) return;

		$row.addClass("amt-enhanced");

		const file_url = $label_link.attr("href") || "";
		const filename = $label_link.attr("title") || $label_link.text().trim();
		const file_info = this.get_file_info(filename);

		const $lock_icon = $pill.find(".attachment-icon");
		const lock_use = $lock_icon.find("use");
		const lock_href_attr = lock_use.length ? lock_use.attr("href") : "";
		const is_private = lock_href_attr === "#es-line-lock";
		const lock_href = $lock_icon.attr("href") || "";

		const $remove = $pill.find(".remove-btn").clone(true);
		const escaped_name = frappe.utils.escape_html(filename);
		const escaped_url = frappe.utils.escape_html(file_url);

		// Replace entire pill content with clean structure
		$pill.empty().addClass("amt-attach-card").append(`
			<div class="amt-file-icon ${file_info.cls}">${file_info.label}</div>
			<div class="amt-attach-details">
				<a class="amt-attach-name" href="${escaped_url}" target="_blank" title="${escaped_name}">${escaped_name}</a>
				<span class="amt-attach-lock">
					<a href="${frappe.utils.escape_html(lock_href)}" style="color:inherit;text-decoration:none">${is_private ? __("Private") : __("Public")}</a>
				</span>
			</div>
		`);
		if ($remove.length) {
			$pill.append($remove);
		}
	},

	listen() {
		const me = this;
		const debounced = frappe.utils.debounce(() => me.enhance_all(), 150);

		// Attachment rows only ever render inside the form's side section, so the
		// observer is scoped to that one small subtree.
		//
		// It used to observe <body> with childList+subtree, which means the
		// callback ran for EVERY DOM mutation anywhere in the desk — every row a
		// report's datatable paints, every grid row a form builds, every list
		// refresh. The debounce capped the work done per burst but not the
		// per-mutation callback cost, and on a large report that is a continuous
		// storm. Scoping it removes that cost entirely without changing what gets
		// enhanced.
		//
		// `.layout-side-section` is the stable parent: Frappe rebuilds
		// `.form-sidebar` inside it on every sidebar refresh (form_sidebar.js
		// appends to `this.page.sidebar.empty()`), so watching the section
		// survives those rebuilds. The section itself is replaced when a
		// different form page is opened, so it is tracked by identity and
		// rebound — the same pattern core/desk_host.js uses for the desk.
		let observer = null;
		let watched = null;

		const rebind = () => {
			const root =
				document.querySelector(".layout-side-section") ||
				document.querySelector(".form-sidebar");

			if (!root || !root.isConnected) {
				if (observer) observer.disconnect();
				observer = null;
				watched = null;
				return;
			}

			if (watched !== root) {
				if (observer) observer.disconnect();
				watched = root;
				observer = new MutationObserver(debounced);
				observer.observe(root, { childList: true, subtree: true });
			}
			debounced();
		};

		// The sidebar is built asynchronously after each of these events, so
		// rebind on a short delay rather than in the same tick.
		$(document).on("form-refresh", () => setTimeout(rebind, 300));
		$(document).on("page-change", () => setTimeout(rebind, 500));
		rebind();
	},
};


// Desk launcher glyph enhancement — see core/desk_launcher.js for why this
// exists and why it cannot be done in CSS alone.
$(document).ready(function () {
	// Subscribes to jQuery's global ajax events only — no polling, no observer,
	// and nothing in the DOM until a request is actually slow.
	browserIdentity.mount();
	progressBar.mount();
	deskLauncher.mount();
	quickActions.mount();
	deskStatusBar.mount();
	// Patches ControlDate.prototype once; must run before any date field is
	// built, so it is mounted here rather than behind after_ajax. Skipping the
	// mount is the whole disable path: the prototype is then never touched, so
	// date fields behave exactly as stock Frappe renders them.
	if (amtEnabled("enable_hijri_dates")) hijriDate.mount();
	// Patches QueryReport.prototype once to auto-fit report columns to content.
	reportAutofit.mount();
	// Adds "＋ new" to creatable-doctype sidebar links + topic icons on card titles.
	workspaceEnhance.mount();
	// Save & Final Submit / Revert to Draft / Cancel & Delete on submittable
	// doctypes with no active Workflow — see core/smart_submit_actions.js.
	if (amtEnabled("enable_smart_actions")) smartSubmitActions.mount();
	// Language switcher in the page header (default placement).
	amir_theme.sidebar.mount_navbar_language_toggle();
});
// The desk landing (route "") decorates its app tiles asynchronously, and
// Frappe rebuilds `.desktop-container` from scratch on every SPA return to it
// (`on_page_show` -> `update()` -> `make()` -> `$(page.body).empty()`). The
// decoration therefore has to be re-applied to a NEW element each time.
//
// This used to be handled with a hard `window.location.reload()` on SPA
// re-entry, because the observer in core/desk_host.js stayed bound to the old,
// detached container and the tiles came back undecorated. That reload cost a
// full framework boot — every bundle re-downloaded, re-parsed and re-run — on
// each return to the desk, which is far and away the most expensive thing the
// theme did.
//
// desk_host now tracks the host BY IDENTITY and rebinds when Frappe replaces
// it, so refreshDeskHost() alone restores a fully decorated desk. See the
// header comment in core/desk_host.js for the mechanism.
$(document).on("page-change", function () {
	refreshDeskHost();
});
