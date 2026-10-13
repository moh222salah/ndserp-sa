/*
 * NDS ERP Saudi — shared engine for the redesigned Workspace dashboards (Assets, HR).
 *
 * It reproduces the structure of the Accounts / Sales / Purchases / Warehouse
 * dashboards — KPI cards, two chart panels, a latest-records table and the
 * sections below — from a small declarative config, so each dashboard module
 * only describes WHAT to show (labels, queries) and not HOW to draw it.
 *
 * Strictly presentation-only:
 *   - data is read through the standard `frappe.client.get_list` API (so every
 *     role / user permission applies) and nothing is ever written;
 *   - the Workspace record, its content, shortcuts, link cards and routes are
 *     never modified. The native shortcut / link widgets are MOVED (not copied)
 *     into the new layout, exactly like the warehouse dashboard does, so their
 *     hrefs, click handlers and permissions are the stock ones;
 *   - no HRMS / ERPNext (core) file, DocType or Workspace is touched.
 */
import { newBlocks } from "./new_blocks.js";

const COMMON_TXT = {
	ar: {
		loading: "جارٍ تحميل البيانات...",
		unavailable: "تعذّر تحميل البيانات بسبب الصلاحيات أو الاتصال.",
		source: "من البيانات المسجلة",
		quickAccess: "الوصول السريع",
		quickAccessNote: "اختصارات مأخوذة من الصفحة الأصلية.",
		navigation: "أقسام الصفحة",
		navigationNote: "روابط مباشرة مأخوذة من أقسام الصفحة الأصلية.",
		noNavigationLinks: "لا توجد روابط متاحة في القسم الأصلي لهذا القسم.",
	},
	en: {
		loading: "Loading data...",
		unavailable: "Data could not be loaded due to permissions or connectivity.",
		source: "From recorded data",
		quickAccess: "Quick Access",
		quickAccessNote: "Shortcuts sourced from the original workspace.",
		navigation: "Workspace Sections",
		navigationNote: "Direct links sourced from the original workspace sections.",
		noNavigationLinks: "No links are available in the original section.",
	},
};

// Accent cycle for the section cards (same palette as the other dashboards).
const NAV_TONES = ["navy", "blue", "gold", "green", "red"];

function esc(value) {
	return String(value === undefined || value === null ? "" : value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;");
}

function el(tag, cls, value) {
	const out = document.createElement(tag);
	if (cls) out.className = cls;
	if (value !== undefined && value !== null) out.textContent = String(value);
	return out;
}

function normName(value) {
	let text = String(value || "").trim();
	try {
		text = decodeURIComponent(text);
	} catch (_) {
		// Not percent-encoded: keep the raw segment.
	}
	return text.toLowerCase().replace(/[_\s]+/g, "-");
}

function rpc(method, args) {
	return new Promise((resolve, reject) => {
		if (!window.frappe || typeof frappe.call !== "function") return reject(new Error("Frappe API unavailable"));
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response ? response.message : null),
			error: (error) => reject(error || new Error("Request failed")),
		});
	});
}

function getList(doctype, fields, filters, options) {
	return rpc("frappe.client.get_list", Object.assign({
		doctype,
		fields,
		filters: filters || [],
		limit_page_length: 500,
	}, options || {}));
}

async function aggregate(doctype, operation, field, alias, filters) {
	const expression = {};
	expression[operation] = field;
	expression.as = alias;
	const rows = await getList(doctype, [expression], filters, { limit_page_length: 1 });
	if (!Array.isArray(rows) || !rows.length) return 0;
	const value = Number(rows[0][alias]);
	return Number.isFinite(value) ? value : 0;
}

function defaultCompany() {
	try {
		const company = frappe.defaults && frappe.defaults.get_user_default("Company");
		if (company) return company;
	} catch (_) {
		// Fall through to the site default.
	}
	return (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.company) || "";
}

function today() {
	try {
		if (frappe.datetime && frappe.datetime.get_today) return frappe.datetime.get_today();
	} catch (_) {
		// Use the browser clock.
	}
	const d = new Date();
	return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

function monthStart(iso, offset) {
	const p = String(iso).split("-").map(Number);
	const d = new Date(p[0], p[1] - 1 + offset, 1, 12, 0, 0);
	return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

function monthKey(value) {
	return String(value || "").slice(0, 7);
}

function fmt(value, decimals) {
	const n = Number(value);
	return Number.isFinite(n)
		? new Intl.NumberFormat("en-US", { minimumFractionDigits: 0, maximumFractionDigits: decimals === undefined ? 0 : decimals }).format(n)
		: "—";
}

function createWorkspaceDashboard(cfg) {
	"use strict";
	const key = cfg.key;
	const P = "nds-" + key;
	const ID = P + "-dashboard";
	const READY = P + "-dashboard-ready";
	const SCOPE = P + "-workspace";
	const CONSUMED = P + "-consumed";
	const VERSION = "1";

	let installed = false;
	let domObserver = null;
	let langObserver = null;
	let observedBody = null;
	let timers = [];
	let renderTimer = null;
	let loadToken = 0;

	// ---------- language ----------------------------------------------------
	function lang() {
		const root = document.documentElement;
		const documentLanguage = String((root && root.getAttribute("lang")) || "").toLowerCase();
		const bootLanguage = String((window.frappe && frappe.boot && frappe.boot.lang) || "").toLowerCase();
		const active = [bootLanguage, documentLanguage].find((value) => value.startsWith("ar") || value.startsWith("en"));
		if (active) return active.startsWith("ar") ? "ar" : "en";
		return String((root && root.getAttribute("dir")) || "").toLowerCase() === "rtl" ? "ar" : "en";
	}

	function t() {
		const language = lang();
		return Object.assign({}, COMMON_TXT[language], cfg.texts[language]);
	}

	function monthLabel(keyValue) {
		try {
			return new Intl.DateTimeFormat(lang() === "ar" ? "ar-SA" : "en-US", { month: "short", calendar: "gregory" })
				.format(new Date(keyValue + "-01T12:00:00"));
		} catch (_) {
			return keyValue;
		}
	}

	function money(value) {
		const currency = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "SAR";
		return fmt(value) + " " + (currency === "SAR" ? (lang() === "ar" ? "ر.س" : "SAR") : currency);
	}

	// ---------- route scope -------------------------------------------------
	/*
	 * Frappe v16 opens a Workspace either as /desk/workspaces/<name> (route
	 * ["Workspaces", name]) or directly as /desk/<slug> (route [slug]). Both are
	 * recognised, but only THIS dashboard's own Workspace names: the stock
	 * Assets / HR workspaces and every other page are never matched.
	 */
	function expectedNames() {
		const expected = new Set();
		cfg.targets.forEach((name) => {
			expected.add(normName(name));
			try {
				if (frappe.router && typeof frappe.router.slug === "function") expected.add(normName(frappe.router.slug(name)));
			} catch (_) {
				// The canonical name stays valid.
			}
		});
		return expected;
	}

	function isTarget() {
		try {
			const route = typeof frappe.get_route === "function" ? frappe.get_route() : [];
			if (!Array.isArray(route) || !route.length) return false;
			const expected = expectedNames();
			const first = normName(route[0]);
			if (first === "workspaces") {
				const second = normName(route[1]);
				// A concrete name in the URL wins over any stale sidebar / heading state.
				if (second) return expected.has(second);
				const sidebar = frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_title;
				const heading = document.querySelector("#page-Workspaces .workspace-title, .workspace-title");
				return [sidebar, heading && heading.textContent].some((value) => expected.has(normName(value)));
			}
			return expected.has(first);
		} catch (_) {
			return false;
		}
	}

	// ---------- direction ---------------------------------------------------
	function setDirection(board) {
		const language = lang();
		const direction = language === "ar" ? "rtl" : "ltr";
		const root = document.documentElement;
		const page = document.querySelector("#page-Workspaces");
		const pageHeader = page && page.querySelector(".page-head");
		const targets = [
			root,
			document.body,
			document.querySelector("body .navbar"),
			document.querySelector("body .navbar .container-fluid"),
			document.querySelector("body .navbar .navbar-collapse"),
			document.querySelector("body .navbar .navbar-nav"),
			page,
			pageHeader,
			pageHeader && pageHeader.querySelector(".page-head-content"),
			pageHeader && pageHeader.querySelector(".title-area"),
			pageHeader && pageHeader.querySelector(".title-text"),
			pageHeader && pageHeader.querySelector(".navbar-breadcrumbs"),
			page && page.querySelector(".layout-main-section"),
			page && page.querySelector("#editorjs"),
			page && page.querySelector("#editorjs .codex-editor__redactor"),
			board,
		];
		targets.filter(Boolean).forEach((node) => {
			if (node.nodeType !== 1) return;
			if (node.getAttribute("dir") !== direction) node.setAttribute("dir", direction);
			node.setAttribute("data-nds-ui-direction", direction);
		});
		if (pageHeader) {
			pageHeader.querySelectorAll(".navbar-breadcrumbs li").forEach((node) => {
				if (node.getAttribute("dir") !== direction) node.setAttribute("dir", direction);
			});
		}
		if (root && root.getAttribute("lang") !== language) root.setAttribute("lang", language);
		if (board) board.setAttribute("lang", language);
	}

	// ---------- markup ------------------------------------------------------
	function panelHeading(c, spec, id) {
		return '<div class="' + P + '-panel-heading"><div><h2 id="' + P + "-" + id + '-title">' + esc(c[spec.title]) + "</h2><p>" +
			esc(c[spec.note]) + '</p></div><span class="' + P + '-panel-mark' + (spec.markTone ? " is-" + spec.markTone : "") +
			'" aria-hidden="true">' + esc(spec.mark) + "</span></div>";
	}

	function build() {
		const c = t();
		const board = el("section", ID);
		board.id = ID;
		board.setAttribute("aria-label", c.title);
		board.setAttribute("data-" + key + "-dashboard-version", VERSION);
		board.setAttribute("data-nds-dashboard-kit", "v1");
		setDirection(board);

		const kpis = cfg.kpis.map((kpi) =>
			'<article class="' + P + '-kpi-card" data-kpi="' + esc(kpi.id) + '" data-tone="' + esc(kpi.tone || "navy") + '">' +
			'<div class="' + P + '-kpi-top"><span class="' + P + '-kpi-label">' + esc(c[kpi.label]) + '</span><span class="' + P +
			'-kpi-icon" aria-hidden="true">' + esc(kpi.icon) + "</span></div>" +
			'<div class="' + P + '-kpi-value" data-kpi-value>—</div>' +
			'<div class="' + P + '-kpi-caption" data-kpi-caption>' + esc(c.loading) + "</div></article>").join("");

		const charts = cfg.charts.map((chart) => {
			const legend = chart.kind === "columns"
				? '<div class="' + P + '-columns-legend">' + chart.series.map((s) =>
					"<span><i class=\"" + esc(s.tone) + "\"></i>" + esc(c[s.label]) + "</span>").join("") + "</div>"
				: "";
			return '<article class="' + P + "-panel " + P + "-" + chart.kind + '-chart" data-chart-panel="' + esc(chart.id) + '" aria-labelledby="' + P + "-" + esc(chart.id) + '-title">' +
				panelHeading(c, chart, chart.id) + legend +
				'<div class="' + P + "-" + chart.kind + '-body" data-chart="' + esc(chart.id) + '"><div class="' + P + '-loading">' + esc(c.loading) + "</div></div></article>";
		}).join("");

		const tableSpec = cfg.table;
		const head = tableSpec.columns.map((col) => "<th>" + esc(c[col.label]) + "</th>").join("");
		const table = '<section class="' + P + "-panel " + P + '-table-panel" aria-labelledby="' + P + '-table-title">' +
			panelHeading(c, tableSpec, "table") +
			'<div class="' + P + '-table-wrap"><table class="' + P + '-table"><thead><tr>' + head + "</tr></thead>" +
			'<tbody data-table-rows><tr><td colspan="' + tableSpec.columns.length + '" class="' + P + '-table-empty">' + esc(c.loading) + "</td></tr></tbody></table></div></section>";

		const quick = '<section class="' + P + '-quick" data-quick hidden aria-label="' + esc(c.quickAccess) + '">' +
			'<div class="' + P + '-navigation-heading"><div><h2 data-quick-title>' + esc(c.quickAccess) + "</h2><p data-quick-note>" + esc(c.quickAccessNote) + "</p></div></div>" +
			'<div class="' + P + '-quick-grid" data-quick-grid></div></section>';

		const nav = '<section class="' + P + '-navigation" data-navigation aria-label="' + esc(c.navigation) + '">' +
			'<div class="' + P + '-navigation-heading"><div><h2 data-nav-title>' + esc(c.navigation) + "</h2><p data-nav-note>" + esc(c.navigationNote) + "</p></div></div>" +
			'<div class="' + P + '-navigation-grid" data-nav-grid></div></section>';

		board.innerHTML =
			'<section class="' + P + '-kpi-grid" aria-label="' + esc(c.title) + '">' + kpis + "</section>" +
			'<section class="' + P + '-analysis-grid" aria-label="' + esc(c.title) + '">' + charts + "</section>" +
			table + quick + nav;
		return board;
	}

	// ---------- renderers ---------------------------------------------------
	function setKpi(board, id, result, failed) {
		const card = board.querySelector('[data-kpi="' + id + '"]');
		if (!card) return;
		const c = t();
		const valueNode = card.querySelector("[data-kpi-value]");
		const caption = card.querySelector("[data-kpi-caption]");
		const ok = !failed && result && result.display !== undefined && result.display !== null;
		if (valueNode) valueNode.textContent = ok ? String(result.display) : "—";
		if (caption) caption.textContent = ok ? (result.caption || c.source) : c.unavailable;
		card.classList.toggle("is-unavailable", !ok);
	}

	function chartBox(board, id) {
		return board.querySelector('[data-chart="' + id + '"]');
	}

	function formatValue(spec, value) {
		return spec.format === "money" ? money(value) : fmt(value, spec.format === "decimal" ? 2 : 0);
	}

	function renderColumns(board, spec, payload) {
		const box = chartBox(board, spec.id);
		if (!box) return;
		const c = t();
		box.replaceChildren();
		if (payload === null) return void box.appendChild(el("div", P + "-chart-empty", c.unavailable));
		const months = [];
		const index = new Map();
		const end = today();
		for (let i = -5; i <= 0; i += 1) {
			const k = monthKey(monthStart(end, i));
			const row = { key: k, label: monthLabel(k), values: {} };
			spec.series.forEach((s) => { row.values[s.id] = 0; });
			months.push(row);
			index.set(k, row);
		}
		spec.series.forEach((s) => {
			(payload[s.id] || []).forEach((r) => {
				const bucket = index.get(monthKey(r.date));
				if (bucket) bucket.values[s.id] += Math.abs(Number(r.value) || 0);
			});
		});
		const max = Math.max(0, ...months.flatMap((m) => spec.series.map((s) => m.values[s.id])));
		if (!max) return void box.appendChild(el("div", P + "-chart-empty", c[spec.empty]));
		const columns = el("div", P + "-columns");
		months.forEach((m) => {
			const col = el("div", P + "-month-column");
			const bars = el("div", P + "-month-bars");
			spec.series.forEach((s) => {
				const track = el("div", P + "-bar-track " + s.tone);
				const bar = el("span", P + "-bar");
				const value = m.values[s.id];
				bar.style.height = (value > 0 ? Math.max(4, (value / max) * 106) : 0).toFixed(1) + "px";
				bar.title = m.label + " — " + c[s.label] + ": " + formatValue(spec, value);
				bar.setAttribute("aria-label", bar.title);
				track.appendChild(bar);
				bars.appendChild(track);
			});
			col.append(bars, el("span", P + "-month-label", m.label));
			columns.appendChild(col);
		});
		box.appendChild(columns);
	}

	function renderBars(board, spec, rows) {
		const box = chartBox(board, spec.id);
		if (!box) return;
		const c = t();
		box.replaceChildren();
		if (rows === null) return void box.appendChild(el("div", P + "-chart-empty", c.unavailable));
		const data = rows.filter((r) => Number(r.value) > 0);
		const max = Math.max(0, ...data.map((r) => Number(r.value)));
		if (!data.length || max <= 0) return void box.appendChild(el("div", P + "-chart-empty", c[spec.empty]));
		const list = el("div", P + "-bars-list");
		data.slice(0, 8).forEach((r) => {
			const value = Number(r.value);
			const row = el("div", P + "-bars-row");
			const head = el("div", P + "-bars-head");
			const name = el("span", P + "-bars-name", r.label || "—");
			if (r.title) name.title = r.title;
			head.append(name, el("strong", P + "-bars-value", formatValue(spec, value)));
			const track = el("div", P + "-bars-track");
			const fill = el("span", P + "-bars-fill");
			fill.style.width = Math.max(2, (value / max) * 100).toFixed(1) + "%";
			track.appendChild(fill);
			row.append(head, track);
			list.appendChild(row);
		});
		box.appendChild(list);
	}

	function appendLink(cell, doctype, name, label, sub) {
		if (!name) {
			cell.textContent = "—";
			return;
		}
		const anchor = el("a", "", label || name);
		anchor.href = "#";
		anchor.addEventListener("click", (event) => {
			event.preventDefault();
			if (window.frappe && frappe.set_route) frappe.set_route("Form", doctype, name);
		});
		cell.appendChild(anchor);
		if (sub) cell.appendChild(el("small", P + "-item-code", sub));
	}

	function renderTable(board, rows) {
		const body = board.querySelector("[data-table-rows]");
		if (!body) return;
		const c = t();
		const spec = cfg.table;
		body.replaceChildren();
		if (rows === null || !rows.length) {
			const row = el("tr");
			const cell = el("td", P + "-table-empty", rows === null ? c.unavailable : c[spec.empty]);
			cell.colSpan = spec.columns.length;
			row.appendChild(cell);
			body.appendChild(row);
			return;
		}
		rows.forEach((r) => {
			const tr = el("tr");
			spec.columns.forEach((col) => {
				const td = el("td");
				const value = r[col.id];
				if (col.kind === "link") {
					appendLink(td, col.doctype, r[col.nameField], r[col.labelField || col.nameField], col.subField ? r[col.subField] : "");
				} else if (col.kind === "money") {
					td.className = "is-numeric";
					td.textContent = value === null || value === undefined ? "—" : money(value);
				} else if (col.kind === "num") {
					td.className = "is-numeric";
					td.textContent = value === null || value === undefined ? "—" : fmt(value, col.decimals || 0);
				} else if (col.kind === "date") {
					td.className = "is-numeric";
					td.textContent = value || "—";
				} else if (col.kind === "status") {
					const entry = (col.map && col.map[value]) || null;
					const pill = el("span", P + "-pill is-" + (entry ? entry.tone : "muted"), entry ? c[entry.label] : (value || "—"));
					td.appendChild(pill);
				} else {
					td.textContent = value || "—";
				}
				tr.appendChild(td);
			});
			body.appendChild(tr);
		});
	}

	// ---------- sections below the dashboard -------------------------------
	function widgetKey(widget) {
		const holder = widget.querySelector("[shortcut_name], [card_name]") || widget.closest(".ce-block")?.querySelector("[shortcut_name], [card_name]");
		const named = holder && (holder.getAttribute("shortcut_name") || holder.getAttribute("card_name"));
		const title = widget.querySelector(".widget-head .widget-title, .widget-title");
		return normName(named || (title && title.textContent) || widget.textContent);
	}

	// `block` must be captured BEFORE the widget is moved out of the editor.
	function markConsumed(block) {
		if (block && !block.querySelector(".widget")) block.classList.add(CONSUMED);
	}

	function renderNavigation(board) {
		const c = t();
		const quick = board.querySelector("[data-quick]");
		const quickGrid = board.querySelector("[data-quick-grid]");
		const navGrid = board.querySelector("[data-nav-grid]");
		const setText = (selector, text) => {
			const node = board.querySelector(selector);
			if (node && node.textContent !== text) node.textContent = text;
		};
		setText("[data-nav-title]", c.navigation);
		setText("[data-nav-note]", c.navigationNote);
		setText("[data-quick-title]", c.quickAccess);
		setText("[data-quick-note]", c.quickAccessNote);

		// While the Workspace is being edited the stock editor must stay intact, so the
		// native widgets are only folded into the new layout in view mode.
		const editing = document.querySelector("#page-Workspaces .layout-main-section.edit-mode");
		const source = editing ? null : document.querySelector("#page-Workspaces #editorjs");
		if (source && quickGrid && navGrid) {
			// Shortcuts → quick access strip. The complete native widget is moved, so its
			// href, handlers and permissions stay the stock ones.
			Array.from(source.querySelectorAll(".widget.shortcut-widget-box")).forEach((widget) => {
				if (board.contains(widget) || newBlocks.isNativeNew(widget)) return;
				const id = widgetKey(widget);
				quickGrid.querySelectorAll('[data-nds-quick-key="' + CSS.escape(id) + '"]').forEach((old) => old.remove());
				const sourceBlock = widget.closest(".ce-block");
				widget.setAttribute("data-nds-quick-key", id);
				widget.setAttribute("data-nds-" + key + "-quick-source", "1");
				quickGrid.appendChild(widget);
				markConsumed(sourceBlock);
			});

			// Link cards → one section card per native card, in the original order.
			Array.from(source.querySelectorAll(".widget.links-widget-box")).forEach((widget) => {
				if (board.contains(widget) || newBlocks.isNativeNew(widget)) return;
				const links = Array.from(widget.querySelectorAll(".widget-body > a.link-item"));
				if (!links.length) return;
				const titleNode = widget.querySelector(".widget-head .widget-title");
				const title = ((titleNode && titleNode.textContent) || "").trim();
				const id = normName(title) || "section-" + navGrid.children.length;
				// A re-rendered Workspace brings fresh widgets: replace the stale card.
				navGrid.querySelectorAll('[data-nds-nav-key="' + CSS.escape(id) + '"]').forEach((old) => old.remove());

				const sourceBlock = widget.closest(".ce-block");
				const card = el("article", P + "-nav-card");
				card.setAttribute("data-nds-nav-key", id);
				const heading = el("div", P + "-nav-card-heading");
				heading.append(el("h3", "", title), el("span", "", cfg.navIcon ? cfg.navIcon(title) : "▤"));
				heading.lastChild.setAttribute("aria-hidden", "true");
				const holder = el("div", P + "-nav-links");
				links.forEach((link) => link.classList.add(P + "-nav-link"));
				widget.setAttribute("data-nds-" + key + "-nav-source", "1");
				holder.appendChild(widget);
				card.append(heading, holder);
				navGrid.appendChild(card);
				markConsumed(sourceBlock);
			});
			Array.from(navGrid.children).forEach((card, index) => {
				card.setAttribute("data-tone", NAV_TONES[index % NAV_TONES.length]);
			});
		}
		if (quick && quickGrid) quick.hidden = !quickGrid.children.length;
		const nav = board.querySelector("[data-navigation]");
		if (nav && navGrid) {
			let empty = navGrid.querySelector("[data-nav-empty]");
			if (!navGrid.querySelector("." + P + "-nav-card")) {
				if (!empty) {
					empty = el("p", P + "-nav-empty", c.noNavigationLinks);
					empty.setAttribute("data-nav-empty", "1");
					navGrid.appendChild(empty);
				} else if (empty.textContent !== c.noNavigationLinks) {
					empty.textContent = c.noNavigationLinks;
				}
			} else if (empty) {
				empty.remove();
			}
		}
	}

	// ---------- data --------------------------------------------------------
	function settle(promise, apply) {
		Promise.resolve(promise).then(
			(value) => apply(value, false),
			() => apply(null, true)
		);
	}

	function loadData(board) {
		const token = ++loadToken;
		const live = () => token === loadToken && board.isConnected;
		const ctx = {
			company: defaultCompany(),
			today: today(),
			t,
			lang,
			fmt,
			money,
			monthStart,
			monthLabel,
			getList,
			aggregate,
		};
		let sources;
		try {
			sources = cfg.sources(ctx) || {};
		} catch (_) {
			sources = {};
		}
		cfg.kpis.forEach((kpi) => {
			const source = sources.kpis && sources.kpis[kpi.id];
			settle(source, (value, failed) => { if (live()) setKpi(board, kpi.id, value, failed || !source); });
		});
		cfg.charts.forEach((chart) => {
			const source = sources.charts && sources.charts[chart.id];
			settle(source, (value) => {
				if (!live()) return;
				const payload = source ? value : null;
				if (chart.kind === "columns") renderColumns(board, chart, payload);
				else renderBars(board, chart, Array.isArray(payload) ? payload : null);
			});
		});
		settle(sources.table, (value) => { if (live()) renderTable(board, Array.isArray(value) ? value : null); });
	}

	// ---------- lifecycle ---------------------------------------------------
	function cleanup() {
		loadToken += 1;
		const current = document.getElementById(ID);
		if (current) current.remove();
		const root = document.documentElement;
		if (root) root.classList.remove(READY);
	}

	function syncScope(active) {
		const root = document.documentElement;
		if (root) root.classList.toggle(SCOPE, Boolean(active));
	}

	function mountIfReady() {
		const active = isTarget();
		syncScope(active);
		if (!active) {
			cleanup();
			return;
		}
		if (!document.body) return;
		const host = document.querySelector("#page-Workspaces .layout-main-section");
		if (!host) return;
		const current = document.getElementById(ID);
		if (current && current.isConnected && current.parentElement === host) {
			setDirection(current);
			renderNavigation(current);
			document.documentElement.classList.add(READY);
			return;
		}
		if (current) current.remove();
		const board = build();
		host.insertBefore(board, host.firstChild);
		document.documentElement.classList.add(READY);
		renderNavigation(board);
		loadData(board);
	}

	function schedule() {
		timers.forEach((timer) => window.clearTimeout(timer));
		timers = [0, 120, 350, 800, 1400].map((delay) => window.setTimeout(mountIfReady, delay));
	}

	// Coalesces bursts of DOM mutations (Frappe paints the Workspace in several passes).
	function scheduleRender() {
		if (renderTimer) return;
		renderTimer = window.setTimeout(() => {
			renderTimer = null;
			const board = document.getElementById(ID);
			if (!isTarget()) {
				if (board) cleanup();
				syncScope(false);
				return;
			}
			if (!board) {
				schedule();
				return;
			}
			setDirection(board);
			renderNavigation(board);
		}, 90);
	}

	function mount() {
		if (installed) return;
		installed = true;
		const boot = () => {
			schedule();
			try {
				if (window.frappe && frappe.router && frappe.router.on) frappe.router.on("change", schedule);
			} catch (_) {
				// The page-change event below still covers navigation.
			}
			window.addEventListener("popstate", schedule);
			if (window.$) window.$(document).on("page-change", schedule);
			if (!langObserver && document.documentElement) {
				langObserver = new MutationObserver(() => {
					const board = document.getElementById(ID);
					if (board && isTarget()) setDirection(board);
					schedule();
				});
				langObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["dir", "lang"] });
			}
			if (document.body && observedBody !== document.body) {
				if (domObserver) domObserver.disconnect();
				observedBody = document.body;
				domObserver = new MutationObserver(scheduleRender);
				domObserver.observe(document.body, { childList: true, subtree: true });
			}
		};
		if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
		else boot();
	}

	return { mount };
}

export { createWorkspaceDashboard };
