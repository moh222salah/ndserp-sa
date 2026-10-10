/*
 * NDS ERP Saudi — Accounts Dashboard.
 * UI-only implementation of the user-provided dashboard specification.
 * It does not read, write, or modify ERP records or existing Workspace logic.
 */
const accountsDashboard = (() => {
	"use strict";

	const DASHBOARD_ID = "nds-accounts-dashboard";
	const READY_CLASS = "nds-accounts-dashboard-ready";
	const WORKSPACE_NAME = "حسابات NDS ERP";
	const LANGUAGES = {
		ar: {
			title: "لوحة الحسابات",
			breadcrumbModule: "الحسابات",
			breadcrumbOverview: "نظرة عامة",
			period: "أكتوبر 2026",
			netProfit: "صافي الربح (الشهر)",
			revenue: "الإيرادات",
			expenses: "المصروفات",
			receivables: "ذمم مدينة مستحقة",
			margin: "هامش 30.1%",
			overdueCount: "18 فاتورة متأخرة",
			monthlyChange: "مقارنة بالشهر السابق",
			expensesByCategory: "المصروفات حسب البند",
			categoryCaption: "النسبة من إجمالي الشهر",
			payroll: "رواتب وأجور",
			cogs: "تكلفة البضاعة المباعة",
			operational: "مصاريف تشغيلية أخرى",
			revenueVsExpenses: "الإيرادات مقابل المصروفات",
			lastSixMonths: "آخر 6 أشهر، بالريال السعودي",
			revenueLegend: "الإيرادات",
			expensesLegend: "المصروفات",
			unpaidInvoices: "فواتير غير مسددة",
			highestCurrently: "الأعلى قيمة حالياً",
			invoiceNumber: "رقم الفاتورة",
			entity: "الجهة",
			dueDate: "تاريخ الاستحقاق",
			amount: "المبلغ",
			status: "الحالة",
			overdue: "متأخرة",
			collecting: "قيد التحصيل",
			sar: "ر.س",
			loading: "عرض تصميمي — القيم وفق مواصفات الطلب وليست محمّلة من قاعدة بيانات ERP.",
		},
		en: {
			title: "Accounts Dashboard",
			breadcrumbModule: "Accounts",
			breadcrumbOverview: "Overview",
			period: "October 2026",
			netProfit: "Net Profit (Month)",
			revenue: "Revenue",
			expenses: "Expenses",
			receivables: "Accounts Receivable",
			margin: "30.1% margin",
			overdueCount: "18 overdue invoices",
			monthlyChange: "Compared with previous month",
			expensesByCategory: "Expenses by Category",
			categoryCaption: "Share of monthly total",
			payroll: "Payroll & Wages",
			cogs: "Cost of Goods Sold",
			operational: "Other Operating Expenses",
			revenueVsExpenses: "Revenue vs. Expenses",
			lastSixMonths: "Last 6 months, in Saudi riyals",
			revenueLegend: "Revenue",
			expensesLegend: "Expenses",
			unpaidInvoices: "Unpaid Invoices",
			highestCurrently: "Highest outstanding balances",
			invoiceNumber: "Invoice Number",
			entity: "Entity",
			dueDate: "Due Date",
			amount: "Amount",
			status: "Status",
			overdue: "Overdue",
			collecting: "In Collection",
			sar: "SAR",
			loading: "Design preview — these values are supplied by the brief, not loaded from ERP records.",
		},
	};

	// These are the explicit display values supplied in the design brief.
	const KPI_DATA = [
		{ key: "profit", value: "386,400", trend: "margin", icon: "↗", state: "positive" },
		{ key: "revenue", value: "1,284,600", trend: "12.4% ↑", icon: "↗", state: "positive" },
		{ key: "expenses", value: "898,200", trend: "4.6% ↑", icon: "↗", state: "caution" },
		{ key: "receivables", value: "214,500", trend: "overdue", icon: "◷", state: "alert" },
	];

	const EXPENSES_DATA = [
		{ key: "payroll", pct: 44, tone: "payroll" },
		{ key: "cogs", pct: 33, tone: "cogs" },
		{ key: "operational", pct: 23, tone: "operational" },
	];

	const MONTHS = [
		{ ar: "أكتوبر", en: "Oct", revenue: 92, expenses: 69 },
		{ ar: "سبتمبر", en: "Sep", revenue: 78, expenses: 57 },
		{ ar: "أغسطس", en: "Aug", revenue: 85, expenses: 64 },
		{ ar: "يوليو", en: "Jul", revenue: 66, expenses: 51 },
		{ ar: "يونيو", en: "Jun", revenue: 73, expenses: 54 },
		{ ar: "مايو", en: "May", revenue: 59, expenses: 43 },
	];

	const INVOICES = [
		{ id: "SI-2026-0339", customer: "شركة درة الخليج", due: "2026-10-15", amount: "41,200", state: "overdue" },
		{ id: "SI-2026-0321", customer: "مؤسسة الرواد", due: "2026-10-18", amount: "28,900", state: "overdue" },
		{ id: "SI-2026-0330", customer: "شركة الأفق التجارية", due: "2026-10-28", amount: "17,650", state: "collecting" },
		{ id: "SI-2026-0335", customer: "مطاعم الواحة", due: "2026-10-30", amount: "9,300", state: "collecting" },
		{ id: "SI-2026-0337", customer: "عبدالله الحربي", due: "2026-11-02", amount: "4,120", state: "collecting" },
	];

	let installStarted = false;
	let preservedEditor = null;
	let editorPlaceholder = null;
	let observer = null;
	let observedBody = null;
	let scheduledTimers = [];

	function getLanguage() {
		const candidates = [
			window.frappe && frappe.boot && frappe.boot.lang,
			window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.language,
			document.documentElement.lang,
		];
		const candidate = candidates.find((value) => typeof value === "string" && value.trim());
		return String(candidate || "ar").toLowerCase().startsWith("en") ? "en" : "ar";
	}

	function normalize(value) {
		return String(value || "").trim().toLowerCase().replace(/[_\s]+/g, "-");
	}

	function isAccountsWorkspace() {
		try {
			const route = window.frappe && typeof frappe.get_route === "function" ? frappe.get_route() : [];
			if (!Array.isArray(route) || normalize(route[0]) !== "workspaces") return false;

			const expected = new Set([normalize(WORKSPACE_NAME)]);
			try {
				if (frappe.router && typeof frappe.router.slug === "function") {
					expected.add(normalize(frappe.router.slug(WORKSPACE_NAME)));
				}
			} catch (_) {
				// The canonical Workspace name remains the fallback.
			}

			const routeName = normalize(route[1]);
			const pageTitle = normalize(document.querySelector(".workspace-title")?.textContent);
			const sidebarTitle = normalize(frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_title);
			return expected.has(routeName) || expected.has(pageTitle) || expected.has(sidebarTitle);
		} catch (_) {
			return false;
		}
	}

	function make(tag, className, text) {
		const node = document.createElement(tag);
		if (className) node.className = className;
		if (text !== undefined && text !== null) node.textContent = String(text);
		return node;
	}

	function buildDashboard(language) {
		const t = LANGUAGES[language];
		const board = make("section", "nds-accounts-dashboard");
		board.id = DASHBOARD_ID;
		board.dataset.language = language;
		board.setAttribute("dir", language === "ar" ? "rtl" : "ltr");
		board.setAttribute("lang", language);
		board.setAttribute("aria-label", t.title);
		board.innerHTML =
			'<header class="nds-accounts-dashboard-header">' +
				'<div class="nds-accounts-dashboard-heading">' +
					'<h1 data-accounts-title></h1>' +
					'<div class="nds-accounts-dashboard-breadcrumb">' +
						'<span>Nexterp v16</span><span aria-hidden="true">/</span>' +
						'<span data-accounts-module></span><span aria-hidden="true">/</span>' +
						'<span data-accounts-overview></span>' +
					'</div>' +
				'</div>' +
				'<div class="nds-accounts-dashboard-period" aria-label="' + t.period + '">' +
					'<span class="nds-accounts-period-icon" aria-hidden="true">◷</span>' +
					'<span>' + t.period + '</span>' +
				'</div>' +
			'</header>' +
			'<section class="nds-accounts-kpi-grid" aria-label="' + t.title + '">' +
				'<article class="nds-accounts-kpi-card" data-kpi="profit">' +
					'<div class="nds-accounts-kpi-top"><span class="nds-accounts-kpi-label"></span><span class="nds-accounts-kpi-icon" aria-hidden="true">↗</span></div>' +
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small></div>' +
					'<div class="nds-accounts-kpi-foot positive"><span data-kpi-trend></span></div>' +
				'</article>' +
				'<article class="nds-accounts-kpi-card" data-kpi="revenue">' +
					'<div class="nds-accounts-kpi-top"><span class="nds-accounts-kpi-label"></span><span class="nds-accounts-kpi-icon" aria-hidden="true">↗</span></div>' +
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small></div>' +
					'<div class="nds-accounts-kpi-foot positive"><span data-kpi-trend></span><span class="nds-accounts-kpi-foot-caption"></span></div>' +
				'</article>' +
				'<article class="nds-accounts-kpi-card" data-kpi="expenses">' +
					'<div class="nds-accounts-kpi-top"><span class="nds-accounts-kpi-label"></span><span class="nds-accounts-kpi-icon" aria-hidden="true">↗</span></div>' +
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small></div>' +
					'<div class="nds-accounts-kpi-foot caution"><span data-kpi-trend></span><span class="nds-accounts-kpi-foot-caption"></span></div>' +
				'</article>' +
				'<article class="nds-accounts-kpi-card" data-kpi="receivables">' +
					'<div class="nds-accounts-kpi-top"><span class="nds-accounts-kpi-label"></span><span class="nds-accounts-kpi-icon" aria-hidden="true">◷</span></div>' +
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small></div>' +
					'<div class="nds-accounts-kpi-foot alert"><span data-kpi-trend></span></div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-accounts-analysis-grid" aria-label="' + t.revenueVsExpenses + '">' +
				'<article class="nds-accounts-panel nds-accounts-expenses-chart">' +
					'<div class="nds-accounts-panel-heading"><div><h2 data-expenses-heading></h2><p data-expenses-caption></p></div><span class="nds-accounts-panel-mark" aria-hidden="true">%</span></div>' +
					'<div class="nds-accounts-expense-list" data-expense-list></div>' +
					'<div class="nds-accounts-expenses-axis" aria-hidden="true"><span>44%</span><span>33%</span><span>23%</span></div>' +
				'</article>' +
				'<article class="nds-accounts-panel nds-accounts-revenue-chart">' +
					'<div class="nds-accounts-panel-heading"><div><h2 data-revenue-heading></h2><p data-revenue-caption></p></div><span class="nds-accounts-panel-mark" aria-hidden="true">▥</span></div>' +
					'<div class="nds-accounts-chart-legend">' +
						'<span><i class="revenue-key"></i><span data-revenue-legend></span></span>' +
						'<span><i class="expenses-key"></i><span data-expenses-legend></span></span>' +
					'</div>' +
					'<div class="nds-accounts-chart-plot" data-month-chart role="img" aria-label="' + t.revenueVsExpenses + '"></div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-accounts-panel nds-accounts-invoices" aria-labelledby="nds-accounts-invoices-title">' +
				'<div class="nds-accounts-panel-heading nds-accounts-invoices-heading">' +
					'<div><h2 id="nds-accounts-invoices-title" data-invoices-heading></h2><p data-invoices-caption></p></div>' +
					'<span class="nds-accounts-invoice-count">05</span>' +
				'</div>' +
				'<div class="nds-accounts-table-wrap"><table class="nds-accounts-invoice-table">' +
					'<thead><tr><th data-th="id"></th><th data-th="customer"></th><th data-th="due"></th><th data-th="amount"></th><th data-th="status"></th></tr></thead>' +
					'<tbody data-invoice-rows></tbody>' +
				'</table></div>' +
			'</section>' +
			'<p class="nds-accounts-dashboard-note" data-dashboard-note></p>';

		board.querySelector("[data-accounts-title]").textContent = t.title;
		board.querySelector("[data-accounts-module]").textContent = t.breadcrumbModule;
		board.querySelector("[data-accounts-overview]").textContent = t.breadcrumbOverview;

		KPI_DATA.forEach((item) => {
			const card = board.querySelector('[data-kpi="' + item.key + '"]');
			card.querySelector(".nds-accounts-kpi-label").textContent = t[item.key === "profit" ? "netProfit" : item.key];
			card.querySelector("[data-kpi-value]").textContent = item.value;
			card.querySelector(".nds-accounts-currency").textContent = t.sar;
			const trend = card.querySelector("[data-kpi-trend]");
			if (item.trend === "margin") trend.textContent = t.margin;
			else if (item.trend === "overdue") trend.textContent = t.overdueCount;
			else trend.textContent = item.trend;
			const caption = card.querySelector(".nds-accounts-kpi-foot-caption");
			if (caption) caption.textContent = t.monthlyChange;
		});

		board.querySelector("[data-expenses-heading]").textContent = t.expensesByCategory;
		board.querySelector("[data-expenses-caption]").textContent = t.categoryCaption;
		board.querySelector("[data-revenue-heading]").textContent = t.revenueVsExpenses;
		board.querySelector("[data-revenue-caption]").textContent = t.lastSixMonths;
		board.querySelector("[data-revenue-legend]").textContent = t.revenueLegend;
		board.querySelector("[data-expenses-legend]").textContent = t.expensesLegend;
		board.querySelector("[data-invoices-heading]").textContent = t.unpaidInvoices;
		board.querySelector("[data-invoices-caption]").textContent = t.highestCurrently;
		board.querySelector('[data-th="id"]').textContent = t.invoiceNumber;
		board.querySelector('[data-th="customer"]').textContent = t.entity;
		board.querySelector('[data-th="due"]').textContent = t.dueDate;
		board.querySelector('[data-th="amount"]').textContent = t.amount;
		board.querySelector('[data-th="status"]').textContent = t.status;
		board.querySelector("[data-dashboard-note]").textContent = t.loading;

		renderExpenses(board, t);
		renderMonths(board, t, language);
		renderInvoices(board, t);

		return board;
	}

	function renderExpenses(board, t) {
		const list = board.querySelector("[data-expense-list]");
		EXPENSES_DATA.forEach((item) => {
			const row = make("div", "nds-accounts-expense-row tone-" + item.tone);
			const head = make("div", "nds-accounts-expense-head");
			head.append(
				make("span", "nds-accounts-expense-label", t[item.key]),
				make("span", "nds-accounts-expense-pct", item.pct + "%")
			);
			const track = make("div", "nds-accounts-expense-track");
			const fill = make("span", "nds-accounts-expense-fill");
			fill.style.width = item.pct + "%";
			fill.setAttribute("aria-hidden", "true");
			track.appendChild(fill);
			row.append(head, track);
			list.appendChild(row);
		});
	}

	function renderMonths(board, t, language) {
		const plot = board.querySelector("[data-month-chart]");
		const grid = make("div", "nds-accounts-chart-columns");
		MONTHS.forEach((month) => {
			const column = make("div", "nds-accounts-month-column");
			const bars = make("div", "nds-accounts-month-bars");
			const revenue = make("span", "nds-accounts-bar revenue");
			const expense = make("span", "nds-accounts-bar expenses");
			revenue.style.height = month.revenue + "%";
			expense.style.height = month.expenses + "%";
			revenue.title = t.revenueLegend + " — " + (language === "ar" ? month.ar : month.en);
			expense.title = t.expensesLegend + " — " + (language === "ar" ? month.ar : month.en);
			revenue.setAttribute("aria-hidden", "true");
			expense.setAttribute("aria-hidden", "true");
			bars.append(revenue, expense);
			column.append(bars, make("span", "nds-accounts-month-label", language === "ar" ? month.ar : month.en));
			grid.appendChild(column);
		});
		plot.appendChild(grid);
	}

	function renderInvoices(board, t) {
		const body = board.querySelector("[data-invoice-rows]");
		INVOICES.forEach((invoice) => {
			const row = make("tr");
			const id = make("td", "invoice-id", invoice.id);
			id.setAttribute("dir", "ltr");
			const customer = make("td", "invoice-customer", invoice.customer);
			const due = make("td", "invoice-date", invoice.due);
			due.setAttribute("dir", "ltr");
			const amount = make("td", "invoice-amount");
			const value = make("span", "invoice-amount-value", invoice.amount);
			const currency = make("small", "invoice-currency", t.sar);
			amount.append(value, currency);
			const status = make("td", "invoice-status");
			const badge = make("span", "nds-accounts-status " + (invoice.state === "overdue" ? "overdue" : "collecting"), invoice.state === "overdue" ? t.overdue : t.collecting);
			status.appendChild(badge);
			row.append(id, customer, due, amount, status);
			body.appendChild(row);
		});
	}

	function detachWorkspaceEditor(page) {
		const editor = page && page.querySelector("#editorjs");
		if (!editor || !editor.parentNode || editor === preservedEditor) return;
		if (preservedEditor && editorPlaceholder && editorPlaceholder.parentNode) {
			// Keep the first Workspace editor as the restoration point. The theme
			// may recreate another editor while this replacement is active.
			editor.remove();
			return;
		}
		// If Frappe replaced the page entirely, the old placeholder is detached;
		// retain the newly rendered editor instead of restoring stale page DOM.
		preservedEditor = null;
		editorPlaceholder = null;
		const placeholder = document.createComment("NDS Accounts Dashboard preserves the original Workspace editor");
		editor.parentNode.insertBefore(placeholder, editor);
		editor.remove();
		preservedEditor = editor;
		editorPlaceholder = placeholder;
	}

	function restoreWorkspaceEditor() {
		if (preservedEditor && editorPlaceholder && editorPlaceholder.parentNode) {
			editorPlaceholder.replaceWith(preservedEditor);
		}
		preservedEditor = null;
		editorPlaceholder = null;
	}

	function mountIfReady() {
		if (!isAccountsWorkspace()) {
			cleanup();
			return;
		}
		const page = document.querySelector("#page-Workspaces");
		const host = page && page.querySelector(".layout-main-section");
		if (!host) return;

		const language = getLanguage();
		const current = document.getElementById(DASHBOARD_ID);
		if (current && current.isConnected && current.parentElement === host && current.dataset.language === language) {
			document.body.classList.add(READY_CLASS);
			detachWorkspaceEditor(page);
			return;
		}
		const next = buildDashboard(language);
		if (current && current.parentElement) current.replaceWith(next);
		else host.insertBefore(next, host.firstChild);
		document.body.classList.add(READY_CLASS);
		detachWorkspaceEditor(page);
	}

	function cleanup() {
		const board = document.getElementById(DASHBOARD_ID);
		if (board) board.remove();
		restoreWorkspaceEditor();
		if (document.body) document.body.classList.remove(READY_CLASS);
	}

	function scheduleSync() {
		scheduledTimers.forEach(window.clearTimeout);
		scheduledTimers = [0, 120, 350, 800, 1400].map((delay) => window.setTimeout(mountIfReady, delay));
	}

	function install() {
		if (installStarted) return;
		installStarted = true;
		const boot = () => {
			scheduleSync();
			if (window.frappe && frappe.router && typeof frappe.router.on === "function") {
				frappe.router.on("change", scheduleSync);
			}
			$(document).on("page-change", scheduleSync);
			window.addEventListener("popstate", scheduleSync);
			if (document.body && observedBody !== document.body) {
				if (observer) observer.disconnect();
				observedBody = document.body;
				observer = new MutationObserver(() => {
					if (isAccountsWorkspace()) {
						if (!document.getElementById(DASHBOARD_ID)) scheduleSync();
						else detachWorkspaceEditor(document.querySelector("#page-Workspaces"));
					} else if (document.getElementById(DASHBOARD_ID)) {
						cleanup();
					}
				});
				observer.observe(document.body, { childList: true, subtree: true });
			}
		};
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", boot, { once: true });
		} else {
			boot();
		}
	}

	return { mount: install };
})();

export { accountsDashboard };
