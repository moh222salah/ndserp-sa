/*
 * NDS ERP Saudi — live Sales Dashboard.
 * Presentation-only: reads permission-filtered ERPNext records and adds a dashboard
 * surface to the Sales Workspace without changing Workspace records or sales logic.
 */
const salesDashboard = (() => {
	"use strict";

	const DASHBOARD_ID = "nds-sales-dashboard";
	const DASHBOARD_CLASS = "nds-sales-dashboard";
	const SALES_WORKSPACE_NAME = "المبيعات NDS ERP";
	const READY_CLASS = "nds-sales-dashboard-ready";
	let settleTimers = [];
	let observer = null;
	let observedBody = null;
	let installStarted = false;

	function routeName(value) {
		return String(value || "").trim().toLowerCase().replace(/[_\s]+/g, "-");
	}

	function isSalesWorkspace() {
		try {
			const route = window.frappe && typeof frappe.get_route === "function" ? frappe.get_route() : [];
			if (!Array.isArray(route) || route[0] !== "Workspaces") return false;
			const target = routeName(SALES_WORKSPACE_NAME);
			let slug = SALES_WORKSPACE_NAME;
			try {
				if (frappe.router && typeof frappe.router.slug === "function") {
					slug = frappe.router.slug(SALES_WORKSPACE_NAME);
				}
			} catch (_) {
				// Use the canonical Workspace name when slugging is unavailable.
			}
			const expected = new Set([target, routeName(slug)]);
			const key = frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_title;
			const routeMatches = expected.has(routeName(route[1]));
			const keyMatches = expected.has(routeName(key));
			return routeMatches || keyMatches;
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

	function rpc(method, args) {
		return new Promise((resolve, reject) => {
			if (!window.frappe || typeof frappe.call !== "function") {
				reject(new Error("Frappe API is not ready"));
				return;
			}
			frappe.call({
				method,
				args,
				callback: (response) => resolve(response ? response.message : null),
				error: (error) => reject(error || new Error("Request failed")),
			});
		});
	}

	function getList(doctype, fields, filters, extra) {
		return rpc("frappe.client.get_list", Object.assign({
			doctype,
			fields,
			filters,
			limit_page_length: 500,
		}, extra || {}));
	}

	function todayISO() {
		try {
			if (frappe.datetime && typeof frappe.datetime.get_today === "function") {
				return frappe.datetime.get_today();
			}
		} catch (_) {
			// Local browser date is the safe fallback.
		}
		const now = new Date();
		return isoDate(now);
	}

	function isoDate(date) {
		return [
			date.getFullYear(),
			String(date.getMonth() + 1).padStart(2, "0"),
			String(date.getDate()).padStart(2, "0"),
		].join("-");
	}

	function monthStart(dateString, offset) {
		const parts = String(dateString).split("-").map(Number);
		const date = new Date(parts[0], parts[1] - 1 + offset, 1, 12, 0, 0);
		return isoDate(date);
	}

	function monthKey(dateString) {
		return String(dateString || "").slice(0, 7);
	}

	function monthLabel(key) {
		try {
			const date = new Date(key + "-01T12:00:00");
			return new Intl.DateTimeFormat("ar-EG", {
				month: "long",
				calendar: "gregory",
			}).format(date);
		} catch (_) {
			return key;
		}
	}

	function number(value, decimals) {
		const numeric = Number(value);
		if (!Number.isFinite(numeric)) return "—";
		return new Intl.NumberFormat("en-US", {
			minimumFractionDigits: 0,
			maximumFractionDigits: decimals === undefined ? 0 : decimals,
		}).format(numeric);
	}

	function currencyCode() {
		try {
			return (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "SAR";
		} catch (_) {
			return "SAR";
		}
	}

	function money(value) {
		const code = currencyCode();
		const suffix = code === "SAR" ? "ر.س" : code;
		return number(value, 0) + " " + suffix;
	}

	function percentChange(current, previous) {
		if (!(previous > 0)) return null;
		return ((current - previous) / previous) * 100;
	}

	function trendText(current, previous, kind) {
		const delta = current - previous;
		if (previous === 0 && current === 0) return { text: "لا توجد حركة في الفترة المقارنة", state: "neutral" };
		if (previous === 0 && current > 0) return { text: "نشاط جديد هذا الشهر", state: "positive" };
		if (kind === "count") {
			if (delta > 0) return { text: "↑ " + number(delta) + " فاتورة جديدة عن الشهر السابق", state: "positive" };
			if (delta < 0) return { text: "↓ " + number(Math.abs(delta)) + " فاتورة عن الشهر السابق", state: "negative" };
			return { text: "لا تغيير عن الشهر السابق", state: "neutral" };
		}
		const change = percentChange(current, previous);
		if (change === null) return { text: "لا توجد بيانات مقارنة", state: "neutral" };
		const arrow = change > 0 ? "↑ " : change < 0 ? "↓ " : "";
		const state = change > 0 ? "positive" : change < 0 ? "negative" : "neutral";
		return { text: arrow + number(Math.abs(change), 1) + "% عن الشهر السابق", state };
	}

	function setText(root, selector, text) {
		const node = root.querySelector(selector);
		if (node) node.textContent = text;
	}

	function setTrend(root, selector, trend) {
		const node = root.querySelector(selector);
		if (!node) return;
		node.className = "nds-sales-kpi-trend " + (trend.state || "neutral");
		node.textContent = trend.text || "";
	}

	function buildDashboard() {
		const board = make("section", DASHBOARD_CLASS);
		board.id = DASHBOARD_ID;
		board.setAttribute("dir", "rtl");
		board.setAttribute("aria-label", "لوحة المبيعات");
		board.innerHTML =
			'<header class="nds-sales-dashboard-header">' +
				'<div class="nds-sales-dashboard-heading">' +
					'<h1>لوحة المبيعات</h1>' +
					'<div class="nds-sales-dashboard-breadcrumb"><span>المبيعات</span><span aria-hidden="true">/</span><span>نظرة عامة</span></div>' +
				'</div>' +
				'<div class="nds-sales-dashboard-period">' +
					'<span class="nds-sales-dashboard-period-icon" aria-hidden="true">◷</span>' +
					'<span data-sales-period>الفترة الحالية</span>' +
				'</div>' +
			'</header>' +
			'<section class="nds-sales-kpi-grid" aria-label="مؤشرات المبيعات">' +
				'<article class="nds-sales-kpi-card" data-kpi="sales">' +
					'<div class="nds-sales-kpi-label">إجمالي المبيعات (الشهر)</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>جارٍ تحميل البيانات…</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="invoices">' +
					'<div class="nds-sales-kpi-label">عدد الفواتير</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>جارٍ تحميل البيانات…</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="average">' +
					'<div class="nds-sales-kpi-label">متوسط قيمة الفاتورة</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>جارٍ تحميل البيانات…</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="opportunities">' +
					'<div class="nds-sales-kpi-label">فرص مفتوحة (CRM)</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>جارٍ تحميل البيانات…</div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-sales-charts-grid" aria-label="تحليلات المبيعات">' +
				'<article class="nds-sales-panel nds-sales-revenue-chart" aria-labelledby="nds-sales-revenue-title">' +
					'<div class="nds-sales-panel-heading"><div><h2 id="nds-sales-revenue-title">المبيعات — آخر 6 أشهر</h2><p>إجمالي قيمة فواتير البيع المعتمدة</p></div></div>' +
					'<div class="nds-sales-revenue-chart-body" data-revenue-chart><div class="nds-sales-loading">جارٍ تحميل بيانات الرسم البياني…</div></div>' +
				'</article>' +
				'<article class="nds-sales-panel nds-sales-channels-chart" aria-labelledby="nds-sales-channels-title">' +
					'<div class="nds-sales-panel-heading"><div><h2 id="nds-sales-channels-title">المبيعات حسب القناة</h2><p data-channel-caption>النسبة من إجمالي المبيعات للفترة</p></div></div>' +
					'<div class="nds-sales-channel-list" data-channel-chart><div class="nds-sales-loading">جارٍ تحميل بيانات التوزيع…</div></div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-sales-panel nds-sales-invoices" aria-labelledby="nds-sales-invoices-title">' +
				'<div class="nds-sales-panel-heading nds-sales-invoices-heading">' +
					'<div><h2 id="nds-sales-invoices-title">أحدث فواتير المبيعات</h2><p>آخر 5 فواتير بيع معتمدة</p></div>' +
					'<button type="button" class="nds-sales-view-all" data-sales-view-all>عرض جميع الفواتير <span aria-hidden="true">←</span></button>' +
				'</div>' +
				'<div class="nds-sales-table-wrap">' +
					'<table class="nds-sales-invoice-table"><thead><tr><th>رقم الفاتورة</th><th>العميل</th><th>التاريخ</th><th>المبلغ</th><th>الحالة</th></tr></thead>' +
					'<tbody data-invoice-rows><tr><td colspan="5" class="nds-sales-table-empty">جارٍ تحميل أحدث الفواتير…</td></tr></tbody></table>' +
				'</div>' +
			'</section>';

		const viewAll = board.querySelector("[data-sales-view-all]");
		viewAll.addEventListener("click", () => {
			if (window.frappe && typeof frappe.set_route === "function") {
				frappe.set_route("List", "Sales Invoice");
			}
		});
		return board;
	}

	function currentMonthBuckets(dateString, dailyRows) {
		const items = [];
		for (let offset = -5; offset <= 0; offset += 1) {
			const start = monthStart(dateString, offset);
			items.push({
				key: monthKey(start),
				label: monthLabel(monthKey(start)),
				total: 0,
				count: 0,
			});
		}
		const byKey = new Map(items.map((item) => [item.key, item]));
		(dailyRows || []).forEach((row) => {
			const item = byKey.get(monthKey(row.posting_date));
			if (!item) return;
			item.total += Number(row.sales_total || 0);
			item.count += Number(row.invoice_count || 0);
		});
		return items;
	}

	async function loadDailySales(startDate, endDate) {
		const filters = [
			["Sales Invoice", "docstatus", "=", 1],
			["Sales Invoice", "is_return", "=", 0],
			["Sales Invoice", "posting_date", ">=", startDate],
			["Sales Invoice", "posting_date", "<=", endDate],
		];
		return getList("Sales Invoice", [
			"posting_date",
			{ SUM: "base_grand_total", as: "sales_total" },
			{ COUNT: "*", as: "invoice_count" },
		], filters, {
			group_by: "posting_date",
			order_by: "posting_date asc",
			limit_page_length: 1000,
		});
	}

	function renderRevenueChart(board, buckets) {
		const container = board.querySelector("[data-revenue-chart]");
		if (!container) return;
		container.replaceChildren();
		const maximum = Math.max(0, ...buckets.map((item) => item.total));
		if (!buckets.length || maximum <= 0) {
			container.appendChild(make("div", "nds-sales-chart-empty", "لا توجد مبيعات مسجلة خلال الفترة المعروضة."));
			return;
		}
		const columns = make("div", "nds-sales-revenue-columns");
		buckets.slice().reverse().forEach((item) => {
			const column = make("div", "nds-sales-revenue-column");
			const barArea = make("div", "nds-sales-revenue-bar-area");
			const bar = make("div", "nds-sales-revenue-bar");
			const height = Math.max(item.total > 0 ? 5 : 0, (item.total / maximum) * 112);
			bar.style.height = height.toFixed(1) + "px";
			bar.title = item.label + " — " + money(item.total);
			bar.setAttribute("aria-label", item.label + " " + money(item.total));
			barArea.appendChild(bar);
			const value = make("span", "nds-sales-revenue-value", item.total > 0 ? number(item.total) : "0");
			const label = make("span", "nds-sales-revenue-month", item.label);
			column.appendChild(value);
			column.appendChild(barArea);
			column.appendChild(label);
			columns.appendChild(column);
		});
		container.appendChild(columns);
	}

	function channelFieldName() {
		try {
			const meta = frappe.get_meta("Sales Invoice");
			const fields = new Set((meta.fields || []).map((field) => field.fieldname));
			return ["sales_channel", "channel", "branch", "is_pos", "territory"].find((name) => fields.has(name)) || null;
		} catch (_) {
			return "is_pos";
		}
	}

	async function loadChannelRows(startDate, endDate) {
		const filters = [
			["Sales Invoice", "docstatus", "=", 1],
			["Sales Invoice", "is_return", "=", 0],
			["Sales Invoice", "posting_date", ">=", startDate],
			["Sales Invoice", "posting_date", "<=", endDate],
		];
		const candidates = [];
		const primary = channelFieldName();
		if (primary) candidates.push(primary);
		["sales_channel", "channel", "branch", "is_pos", "territory"].forEach((field) => {
			if (!candidates.includes(field)) candidates.push(field);
		});
		for (const field of candidates) {
			try {
				const rows = await getList("Sales Invoice", [
					field,
					{ SUM: "base_grand_total", as: "sales_total" },
				], filters, {
					group_by: field,
					order_by: "sales_total desc",
					limit_page_length: 40,
				});
				const valid = (rows || []).filter((row) => row[field] !== undefined && row[field] !== null && String(row[field]).trim() !== "");
				if (valid.length) return { field, rows: valid };
			} catch (_) {
				// Try the next available standard/custom sales dimension without blocking the dashboard.
			}
		}
		return { field: null, rows: [] };
	}

	function channelLabel(field, value) {
		if (field === "is_pos") {
			return Number(value) ? "نقاط البيع (POS)" : "فواتير خارج نقاط البيع";
		}
		return String(value || "غير محدد");
	}

	function renderChannels(board, result) {
		const container = board.querySelector("[data-channel-chart]");
		if (!container) return;
		container.replaceChildren();
		const rows = (result && result.rows) || [];
		const sorted = rows.map((row) => ({
			label: channelLabel(result.field, row[result.field]),
			total: Number(row.sales_total || 0),
		})).sort((a, b) => b.total - a.total);
		const total = sorted.reduce((sum, item) => sum + item.total, 0);
		if (!sorted.length || total <= 0) {
			container.appendChild(make("div", "nds-sales-chart-empty", "لا توجد بيانات كافية لتوزيع المبيعات حسب القناة."));
			return;
		}
		setText(board, "[data-channel-caption]", result.field === "is_pos"
			? "نقاط البيع مقارنة بالفواتير خارجها"
			: "النسبة من إجمالي المبيعات خلال آخر 6 أشهر");
		sorted.slice(0, 4).forEach((item, index) => {
			const pct = (item.total / total) * 100;
			const row = make("div", "nds-sales-channel-row");
			const head = make("div", "nds-sales-channel-head");
			const labelGroup = make("div", "nds-sales-channel-label-group");
			const dot = make("span", "nds-sales-channel-dot tone-" + (index + 1));
			const label = make("span", "nds-sales-channel-label", item.label);
			labelGroup.append(dot, label);
			const pctLabel = make("span", "nds-sales-channel-percent", number(pct, 0) + "%");
			head.append(labelGroup, pctLabel);
			const track = make("div", "nds-sales-channel-track");
			const fill = make("div", "nds-sales-channel-fill tone-" + (index + 1));
			fill.style.width = pct.toFixed(1) + "%";
			fill.title = item.label + " — " + money(item.total);
			track.appendChild(fill);
			row.append(head, track);
			container.appendChild(row);
		});
	}

	function statusLabel(status) {
		const labels = {
			Paid: "مسددة",
			Unpaid: "غير مسددة",
			Overdue: "متأخرة",
			"Partly Paid": "مدفوعة جزئيًا",
			Draft: "مسودة",
			Submitted: "معتمدة",
			Cancelled: "ملغاة",
			Return: "مرتجع",
			"Credit Note Issued": "إشعار دائن",
		};
		return labels[status] || status || "—";
	}

	function renderInvoices(board, invoices) {
		const body = board.querySelector("[data-invoice-rows]");
		if (!body) return;
		body.replaceChildren();
		if (!invoices || !invoices.length) {
			const row = make("tr");
			const cell = make("td", "nds-sales-table-empty", "لا توجد فواتير بيع معتمدة لعرضها.");
			cell.colSpan = 5;
			row.appendChild(cell);
			body.appendChild(row);
			return;
		}
		invoices.forEach((invoice) => {
			const row = make("tr");
			const numberCell = make("td");
			const link = make("a", "nds-sales-invoice-link", invoice.name || "—");
			link.href = "#";
			link.addEventListener("click", (event) => {
				event.preventDefault();
				if (window.frappe && typeof frappe.set_route === "function") {
					frappe.set_route("Form", "Sales Invoice", invoice.name);
				}
			});
			numberCell.appendChild(link);
			const customer = make("td", "nds-sales-invoice-customer", invoice.customer_name || invoice.customer || "—");
			const date = make("td", "nds-sales-invoice-date", String(invoice.posting_date || "—"));
			const amount = make("td", "nds-sales-invoice-amount", money(invoice.base_grand_total || 0));
			const statusText = statusLabel(invoice.status);
			const statusCell = make("td");
			const badge = make("span", "nds-sales-status", statusText);
			const statusValue = String(invoice.status || "").toLowerCase();
			if (statusValue === "paid") badge.classList.add("is-paid");
			else if (statusValue === "overdue") badge.classList.add("is-overdue");
			else if (statusValue === "unpaid" || statusValue === "partly paid") badge.classList.add("is-pending");
			statusCell.appendChild(badge);
			row.append(numberCell, customer, date, amount, statusCell);
			body.appendChild(row);
		});
	}

	function updatePeriod(board, today) {
		const key = monthKey(today);
		setText(board, "[data-sales-period]", "الفترة: " + monthLabel(key) + " " + key.slice(0, 4));
	}

	async function loadDashboardData(board) {
		const today = todayISO();
		const start = monthStart(today, -5);
		updatePeriod(board, today);

		const dailyPromise = loadDailySales(start, today);
		const opportunitiesPromise = getList("Opportunity", [
			{ COUNT: "*", as: "opportunity_count" },
			{ SUM: "opportunity_amount", as: "expected_total" },
		], [["Opportunity", "status", "=", "Open"]], { limit_page_length: 1 })
			.catch(() => null);
		const channelsPromise = loadChannelRows(start, today).catch(() => ({ field: null, rows: [] }));
		const invoicesPromise = getList("Sales Invoice", [
			"name", "customer", "customer_name", "posting_date", "base_grand_total", "status", "currency",
		], [
			["Sales Invoice", "docstatus", "=", 1],
			["Sales Invoice", "is_return", "=", 0],
		], {
			order_by: "posting_date desc, creation desc",
			limit_page_length: 5,
		}).catch(() => null);

		try {
			const daily = await dailyPromise;
			const buckets = currentMonthBuckets(today, daily || []);
			renderRevenueChart(board, buckets);
			const currentKey = monthKey(today);
			const previousKey = monthKey(monthStart(today, -1));
			const current = buckets.find((item) => item.key === currentKey) || { total: 0, count: 0 };
			const previous = buckets.find((item) => item.key === previousKey) || { total: 0, count: 0 };
			const average = current.count ? current.total / current.count : 0;
			const previousAverage = previous.count ? previous.total / previous.count : 0;

			const salesCard = board.querySelector('[data-kpi="sales"]');
			const invoicesCard = board.querySelector('[data-kpi="invoices"]');
			const averageCard = board.querySelector('[data-kpi="average"]');
			setText(salesCard, "[data-kpi-value]", money(current.total));
			setTrend(salesCard, "[data-kpi-trend]", trendText(current.total, previous.total, "amount"));
			setText(invoicesCard, "[data-kpi-value]", number(current.count));
			setTrend(invoicesCard, "[data-kpi-trend]", trendText(current.count, previous.count, "count"));
			setText(averageCard, "[data-kpi-value]", money(average));
			setTrend(averageCard, "[data-kpi-trend]", trendText(average, previousAverage, "amount"));
		} catch (_) {
			const salesCard = board.querySelector('[data-kpi="sales"]');
			const invoicesCard = board.querySelector('[data-kpi="invoices"]');
			const averageCard = board.querySelector('[data-kpi="average"]');
			[salesCard, invoicesCard, averageCard].forEach((card) => {
				setText(card, "[data-kpi-value]", "غير متاح");
				setTrend(card, "[data-kpi-trend]", { text: "تعذر تحميل بيانات الفواتير", state: "neutral" });
			});
			const revenue = board.querySelector("[data-revenue-chart]");
			if (revenue) revenue.replaceChildren(make("div", "nds-sales-chart-empty", "تعذر تحميل بيانات المبيعات. تحقق من صلاحية قراءة الفواتير."));
		}

		const opportunities = await opportunitiesPromise;
		const oppCard = board.querySelector('[data-kpi="opportunities"]');
		if (opportunities && opportunities.length) {
			const opp = opportunities[0];
			setText(oppCard, "[data-kpi-value]", number(opp.opportunity_count || 0));
			setTrend(oppCard, "[data-kpi-trend]", {
				text: "القيمة المتوقعة: " + money(opp.expected_total || 0),
				state: "neutral",
			});
		} else {
			setText(oppCard, "[data-kpi-value]", "غير متاح");
			setTrend(oppCard, "[data-kpi-trend]", { text: "تعذر تحميل بيانات فرص CRM", state: "neutral" });
		}

		const channels = await channelsPromise;
		renderChannels(board, channels);

		const invoices = await invoicesPromise;
		if (invoices === null) {
			const body = board.querySelector("[data-invoice-rows]");
			if (body) {
				body.replaceChildren();
				const row = make("tr");
				const cell = make("td", "nds-sales-table-empty", "تعذر تحميل أحدث الفواتير بسبب الصلاحيات أو الاتصال.");
				cell.colSpan = 5;
				row.appendChild(cell);
				body.appendChild(row);
			}
		} else {
			renderInvoices(board, invoices || []);
		}
	}

	function mountIfReady() {
		if (!isSalesWorkspace()) {
			cleanup();
			return;
		}
		if (!document.body) return;
		document.body.classList.add("nds-sales-workspace-redesign");
		const host = document.querySelector("#page-Workspaces .layout-main-section");
		if (!host) return;
		const current = document.getElementById(DASHBOARD_ID);
		if (current && current.isConnected && current.parentElement === host) {
			document.body.classList.add(READY_CLASS);
			return;
		}
		if (current) current.remove();
		const board = buildDashboard();
		host.insertBefore(board, host.firstChild);
		document.body.classList.add(READY_CLASS);
		loadDashboardData(board);
	}

	function cleanup() {
		const current = document.getElementById(DASHBOARD_ID);
		if (current) current.remove();
		if (document.body) {
			document.body.classList.remove(READY_CLASS);
			document.body.classList.remove("nds-sales-workspace-redesign");
		}
	}

	function scheduleSync() {
		settleTimers.forEach(window.clearTimeout);
		settleTimers = [0, 120, 350, 800, 1400].map((delay) => window.setTimeout(mountIfReady, delay));
	}

	function install() {
		if (installStarted) return;
		installStarted = true;
		const boot = () => {
			scheduleSync();
			if (window.frappe && frappe.router && typeof frappe.router.on === "function") {
				frappe.router.on("change", scheduleSync);
			}
			window.addEventListener("popstate", scheduleSync);
			if (document.body && observedBody !== document.body) {
				if (observer) observer.disconnect();
				observedBody = document.body;
				observer = new MutationObserver(() => {
					if (isSalesWorkspace() && !document.getElementById(DASHBOARD_ID)) scheduleSync();
					else if (!isSalesWorkspace() && document.getElementById(DASHBOARD_ID)) cleanup();
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

export { salesDashboard };