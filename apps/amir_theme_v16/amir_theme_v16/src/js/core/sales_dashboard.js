/*
 * NDS ERP Saudi — live Sales Dashboard.
 * Presentation-only: reads permission-filtered ERPNext records and adds a dashboard
 * surface to the Sales Workspace without changing Workspace records or sales logic.
 */
const salesDashboard = (() => {
	"use strict";

	const DASHBOARD_ID = "nds-sales-dashboard";
	const DASHBOARD_CLASS = "nds-sales-dashboard";
	const SALES_SECTIONS_ID = "nds-sales-workspace-sections";
	const SALES_WORKSPACE_NAME = "المبيعات NDS ERP";
	const READY_CLASS = "nds-sales-dashboard-ready";
	let settleTimers = [];
	let observer = null;
	let directionObserver = null;
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

	function currentLanguage() {
		const bootLanguage = window.frappe && frappe.boot && frappe.boot.lang;
		return String(
			bootLanguage
			|| (document.documentElement && document.documentElement.getAttribute("lang"))
			|| "en"
		).toLowerCase();
	}

	function isEnglish() {
		return !currentLanguage().startsWith("ar");
	}

	function copy(arabic, english) {
		return isEnglish() ? english : arabic;
	}

	function currentDirection() {
		// Use the active ERP language consistently for direction across every sales component.
		return isEnglish() ? "ltr" : "rtl";
	}

	function syncDashboardDirection(board) {
		if (!board) return;
		const direction = currentDirection();
		const language = currentLanguage();
		board.setAttribute("dir", direction);
		board.setAttribute("data-sales-direction", direction);
		if (language) board.setAttribute("lang", language);
		board.querySelectorAll(".nds-sales-kpi-grid, .nds-sales-charts-grid, .nds-sales-invoices, .nds-sales-invoice-table, .nds-sales-invoice-table th, .nds-sales-invoice-table td").forEach((node) => {
			node.setAttribute("dir", direction);
		});
		const sections = document.getElementById(SALES_SECTIONS_ID);
		if (sections) {
			sections.setAttribute("dir", direction);
			sections.setAttribute("data-sales-direction", direction);
			if (language) sections.setAttribute("lang", language);
			sections.querySelectorAll(".nds-sales-section-card, .nds-sales-section-card-head, .nds-sales-section-card-title, .nds-sales-section-links, .nds-sales-section-link, .nds-sales-sections-header, .nds-sales-sections-title, .nds-sales-sections-description").forEach((node) => {
				node.setAttribute("dir", direction);
			});
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
			return new Intl.DateTimeFormat(isEnglish() ? "en-US" : "ar-EG", {
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
		const suffix = code === "SAR" ? (isEnglish() ? "SAR" : "ر.س") : code;
		return number(value, 0) + " " + suffix;
	}

	function percentChange(current, previous) {
		if (!(previous > 0)) return null;
		return ((current - previous) / previous) * 100;
	}

	function trendText(current, previous, kind) {
		const delta = current - previous;
		if (previous === 0 && current === 0) return { text: copy("لا توجد حركة في الفترة المقارنة", "No activity in comparison period"), state: "neutral" };
		if (previous === 0 && current > 0) return { text: copy("نشاط جديد هذا الشهر", "New activity this month"), state: "positive" };
		if (kind === "count") {
			if (delta > 0) return { text: "↑ " + number(delta) + copy(" فاتورة جديدة عن الشهر السابق", " new invoices vs. previous month"), state: "positive" };
			if (delta < 0) return { text: "↓ " + number(Math.abs(delta)) + copy(" فاتورة عن الشهر السابق", " invoices vs. previous month"), state: "negative" };
			return { text: copy("لا تغيير عن الشهر السابق", "No change vs. previous month"), state: "neutral" };
		}
		const change = percentChange(current, previous);
		if (change === null) return { text: copy("لا توجد بيانات مقارنة", "No comparison data"), state: "neutral" };
		const arrow = change > 0 ? "↑ " : change < 0 ? "↓ " : "";
		const state = change > 0 ? "positive" : change < 0 ? "negative" : "neutral";
		return { text: arrow + number(Math.abs(change), 1) + copy("% عن الشهر السابق", "% vs. previous month"), state };
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


	// Render the existing Workspace's native groups from Frappe's loaded page
	// model instead of depending on the CSS classes generated by Editor.js.
	// This is a display-only view: it never writes Workspace records or ERP data.
	const SALES_SECTION_DEFINITIONS = [
		{ key: "home", ar: "الرئيسية", en: "Home", icon: "home", matches: /الرئيسية|^home$|main/ },
		{ key: "items-pricing", ar: "الأصناف والتسعير", en: "Items & Pricing", icon: "stock", matches: /اصناف.*تسعير|items?.*pricing|items\s*&\s*pricing|pricing.*items/ },
		{ key: "customer", ar: "العميل", en: "Customers", icon: "users", matches: /العميل|العملاء|customer/ },
		{ key: "settings", ar: "الإعدادات", en: "Settings", icon: "settings", matches: /اعداد|settings|setup/ },
		{ key: "reports", ar: "التقارير", en: "Reports", icon: "sheet", matches: /تقارير|reports/ },
	];

	function normalizeSectionLabel(value) {
		return String(value || "")
			.toLowerCase()
			.replace(/[أإآ]/g, "ا")
			.replace(/[يى]/g, "ي")
			.replace(/[\u064b-\u065f]/g, "")
			.replace(/[_&/-]+/g, " ")
			.replace(/\s+/g, " ")
			.trim();
	}

	function sectionDefinition(label) {
		const normalized = normalizeSectionLabel(label);
		return SALES_SECTION_DEFINITIONS.find((definition) => definition.matches.test(normalized)) || null;
	}

	function getSalesWorkspaceRecord() {
		try {
			const map = window.frappe && frappe.workspace_map;
			if (!map) return null;
			if (map[SALES_WORKSPACE_NAME]) return map[SALES_WORKSPACE_NAME];
			return Object.values(map).find((page) => routeName(page && page.name) === routeName(SALES_WORKSPACE_NAME)) || null;
		} catch (_) {
			return null;
		}
	}

	function getSalesSectionGroups() {
		const page = getSalesWorkspaceRecord();
		if (!page) return null;
		let links = page.links;
		if (typeof links === "string") {
			try { links = JSON.parse(links); } catch (_) { links = []; }
		}
		if (!Array.isArray(links)) links = [];
		const groups = SALES_SECTION_DEFINITIONS.map((definition) => ({ definition, links: [] }));
		let activeGroup = null;
		links.forEach((item) => {
			if (!item) return;
			if (String(item.type || "").toLowerCase() === "card break") {
				const definition = sectionDefinition(item.label);
				activeGroup = definition ? groups.find((group) => group.definition.key === definition.key) : null;
				return;
			}
			if (!activeGroup || String(item.type || "").toLowerCase() !== "link") return;
			if (Number(item.hidden || 0) === 1 || !item.link_to || !item.link_type) return;
			if (item.only_for && Array.isArray(frappe.user_roles)) {
				const allowed = String(item.only_for).split(",").map((role) => role.trim()).filter(Boolean);
				if (allowed.length && !allowed.some((role) => frappe.user_roles.includes(role))) return;
			}
			activeGroup.links.push(item);
		});
		const reports = groups.find((group) => group.definition.key === "reports");
		if (!reports) return groups;
		const reportLinks = reports.links;
		const splitPoint1 = Math.ceil(reportLinks.length / 3);
		const splitPoint2 = Math.ceil((reportLinks.length - splitPoint1) / 2) + splitPoint1;
		const reportGroups = [
			{ definition: { ...reports.definition, key: "reports-1" }, links: reportLinks.slice(0, splitPoint1) },
			{ definition: { ...reports.definition, key: "reports-2" }, links: reportLinks.slice(splitPoint1, splitPoint2) },
			{ definition: { ...reports.definition, key: "reports-3" }, links: reportLinks.slice(splitPoint2) },
		];
		return groups.filter((group) => group.definition.key !== "reports").concat(reportGroups);
	}

	function salesLinkRoute(item) {
		try {
			if (!item || !item.link_to || !item.link_type || !frappe.utils || typeof frappe.utils.generate_route !== "function") {
				return null;
			}
			if (item.link_type === "URL") return item.url || null;
			const args = { type: item.link_type, name: item.link_to, tab: item.tab };
			if (item.link_type === "Report") {
				args.is_query_report = !!Number(item.is_query_report || 0);
				args.report_ref_doctype = item.report_ref_doctype || "";
			}
			if (item.link_type === "DocType") {
				if (item.filters) {
					args.doc_view = "List";
					args.route_options = JSON.parse(frappe.utils.get_filter_as_json(JSON.parse(item.filters)));
				} else if (item.route_options) {
					args.doc_view = "List";
					args.route_options = typeof item.route_options === "string" ? JSON.parse(item.route_options) : item.route_options;
				}
			}
			if (item.link_type === "Page" && item.route_options) {
				args.route_options = typeof item.route_options === "string" ? JSON.parse(item.route_options) : item.route_options;
			}
			return frappe.utils.generate_route(args) || null;
		} catch (_) {
			return null;
		}
	}

	function salesSectionLinkLabel(item, direction) {
		const arabic = String(item.label || item.link_to || "");
		if (direction === "rtl") return __(arabic);
		const translations = {
			"العملاء": "Customers", "العميل": "Customers", "مندوب المبيعات": "Sales Person",
			"شريك المبيعات": "Sales Partner", "عرض سعر": "Quotation", "امر البيع": "Sales Order",
			"اذن التسليم": "Delivery Note", "قائمة الالتقاط": "Pick List", "فاتورة البيع": "Sales Invoice",
			"سند الدفع": "Payment Entry", "طلب الدفع": "Payment Request", "امر اجمالي": "Blanket Order",
			"المطالبة": "Dunning", "الصنف": "Item", "مجموعة الاصناف": "Item Group", "مجموعة الأصناف": "Item Group",
			"قاعدة التسعير": "Item Price", "قائمة التسعير": "Price List", "حزمة المنتجات": "Product Bundle",
			"قاعدة التسعير المتقدمة": "Pricing Rule", "المخطط الترويجي": "Promotional Scheme",
			"قاعدة الشحن": "Shipping Rule", "كود الخصم": "Coupon Code",
			"قالب ضرائب المبيعات": "Sales Taxes and Charges Template", "الشروط والاحكام": "Terms and Conditions",
			"طرق الدفع": "Modes of Payment", "الحملة": "Campaign", "مجموعات العملاء": "Customer Groups",
			"عناوين الاتصال": "Contacts", "العناوين": "Addresses", "المنطقه التابع لها": "Territory",
			"فرع": "Branch", "تحليل المبيعات": "Sales Analytics", "تحليل اوامر البيع": "Sales Order Analysis",
			"اتجاهات اوامر البيع": "Sales Order Trends", "تحليل فواتير البيع": "Sales Invoice Trends",
			"اتجاهات عروض الاسعار": "Quotation Trends", "اتجاهات اذن التسليم": "Delivery Note Trends",
			"عروض الاسعار المفقودة": "Lost Quotations", "سجل المبيعات": "Sales Register",
			"سجل حركة المبيعات وفقا لصنف": "Item-wise Sales Register", "سجل مبيعات الاصناف": "Item-wise Sales History",
			"ملخص مدفوعات المبيعات": "Sales Payment Summary", "ربحيه البيع": "Gross Profit",
			"الاصناف غير النشطة": "Inactive Sales Items", "الذمم المدينة": "Accounts Receivable",
			"ملخص الذمم المدينة": "Accounts Receivable Summary", "ملخص دفتر العميل": "Customer Ledger Summary",
			"رصيد ائتمان العميل": "Customer Credit Balance", "اصناف مسلمة للفوترة": "Delivered Items To Be Billed",
			"حالة شروط دفع اوامر البيع": "Payment Terms Status for Sales Order", "اوامر البيع المعلقة": "Pending SO Items For Purchase Request",
			"عموله مناديب البيع": "Sales Person Commission Summary", "تفاصيل عموله مندوب البيع": "Sales Person-wise Transaction Summary",
			"هدف مندوب البيع": "Sales Person Target Variance", "عمولة شركاء المبيعات": "Sales Partners Commission",
			"ملخص عمولة شريك المبيعات": "Sales Partner Commission Summary", "معاملات شريك المبيعات": "Sales Partner Transaction Summary",
			"هدف شريك المبيعات": "Sales Partner Target Variance", "هدف المنطقة": "Territory Target Variance",
			"اكتساب العملاء والولاء": "Customer Acquisition and Loyalty", "العملاء غير النشطين": "Inactive Customers",
			"عملاء بدون معاملات بيع": "Customers Without Sales Transactions", "اسعار الاصناف حسب العميل": "Customer-wise Item Price",
			"عناوين واتصالات العملاء": "Address And Contacts", "المخزون المتاح لحزم المنتجات": "Available Stock for Packing Items",
			"تفاصيل تكامل زاتكا": "ZATCA Integration Details", "ملخص تكامل زاتكا": "ZATCA Integration Summary",
		};
		const translated = translations[arabic];
		if (translated) return translated;
		const fallback = String(item.link_to || arabic);
		return /[\u0600-\u06FF]/.test(fallback) ? __(arabic) : fallback;
	}

	function renderSalesSections(host, board) {
		if (!host || !board) return false;
		const groups = getSalesSectionGroups();
		if (!groups) return false;
		const direction = currentDirection();
		const language = currentLanguage();
		const signature = direction + "|" + groups.map((group) =>
			group.definition.key + ":" + group.links.map((item) => item.label + ">" + item.link_to).join(",")
		).join("|");
		const existing = document.getElementById(SALES_SECTIONS_ID);
		if (existing && existing.parentElement === host && existing.dataset.salesSignature === signature) {
			existing.setAttribute("dir", direction);
			existing.setAttribute("data-sales-direction", direction);
			if (language) existing.setAttribute("lang", language);
			return true;
		}
		if (existing) existing.remove();

		const sections = make("section", "nds-sales-workspace-sections");
		sections.id = SALES_SECTIONS_ID;
		sections.setAttribute("dir", direction);
		sections.setAttribute("data-sales-direction", direction);
		sections.setAttribute("aria-label", direction === "rtl" ? "أقسام المبيعات" : "Sales sections");
		if (language) sections.setAttribute("lang", language);
		sections.dataset.salesSignature = signature;

		const header = make("header", "nds-sales-sections-header");
		header.setAttribute("dir", direction);
		const heading = make("h2", "nds-sales-sections-title", copy("أقسام المبيعات", "Sales sections"));
		heading.setAttribute("dir", direction);
		const helper = make("p", "nds-sales-sections-description",
			copy("الوصول المباشر إلى أقسام ووظائف المبيعات", "Quick access to sales tools and reports"));
		helper.setAttribute("dir", direction);
		header.append(heading, helper);
		sections.appendChild(header);

		const grid = make("div", "nds-sales-section-grid");
		groups.forEach((group) => {
			const definition = group.definition;
			const card = make("article", "nds-sales-section-card");
			card.setAttribute("dir", direction);
			card.setAttribute("data-sales-section", definition.key);

			const cardHeader = make("div", "nds-sales-section-card-head");
			cardHeader.setAttribute("dir", direction);
			const icon = make("span", "nds-sales-section-icon");
			icon.setAttribute("aria-hidden", "true");
			try {
				if (frappe.utils && typeof frappe.utils.icon === "function") {
					icon.innerHTML = frappe.utils.icon(definition.icon, "md");
				}
			} catch (_) {
				// Decorative icons are optional; navigation must remain available.
			}
			const title = make("h3", "nds-sales-section-card-title", direction === "rtl" ? definition.ar : definition.en);
			title.setAttribute("dir", direction);
			cardHeader.append(icon, title);
			card.appendChild(cardHeader);

			const list = make("nav", "nds-sales-section-links");
			list.setAttribute("dir", direction);
			list.setAttribute("aria-label", direction === "rtl" ? definition.ar : definition.en);
			group.links.forEach((item) => {
				const link = make("a", "nds-sales-section-link", salesSectionLinkLabel(item, direction));
				link.href = "#";
				link.setAttribute("dir", direction);
				link.setAttribute("data-sales-link-type", item.link_type);
				link.setAttribute("data-sales-link-target", item.link_to);
				link.addEventListener("click", (event) => {
					event.preventDefault();
					if (item.link_type === "URL" && item.url) {
						window.open(item.url, item.url.startsWith("http") ? "_blank" : "_self");
						return;
					}
					const route = salesLinkRoute(item);
					if (route && window.frappe && typeof frappe.set_route === "function") {
						frappe.set_route(route);
					} else if (window.frappe && typeof frappe.show_alert === "function") {
						frappe.show_alert({ message: direction === "rtl" ? "تعذر فتح هذا الرابط." : "This link could not be opened.", indicator: "orange" });
					}
				});
				list.appendChild(link);
			});
			if (!group.links.length) {
				list.appendChild(make("p", "nds-sales-section-empty",
					direction === "rtl" ? "لا توجد روابط متاحة لهذا القسم." : "No links are available in this section."));
			}
			card.appendChild(list);
			grid.appendChild(card);
		});
		sections.appendChild(grid);
		host.insertBefore(sections, board.nextSibling);
		return true;
	}

	function buildDashboard() {
		const board = make("section", DASHBOARD_CLASS);
		board.id = DASHBOARD_ID;
		syncDashboardDirection(board);
		board.setAttribute("aria-label", copy("مؤشرات وتحليلات المبيعات", "Sales metrics and analytics"));
		board.innerHTML =
			'<section class="nds-sales-kpi-grid" aria-label="' + copy("مؤشرات المبيعات", "Sales metrics") + '">' +
				'<article class="nds-sales-kpi-card" data-kpi="sales">' +
					'<div class="nds-sales-kpi-label">' + copy("إجمالي المبيعات (الشهر)", "Monthly Sales") + '</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>' + copy("جارٍ تحميل البيانات…", "Loading live data…") + '</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="invoices">' +
					'<div class="nds-sales-kpi-label">' + copy("عدد الفواتير", "Invoice Count") + '</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>' + copy("جارٍ تحميل البيانات…", "Loading live data…") + '</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="average">' +
					'<div class="nds-sales-kpi-label">' + copy("متوسط قيمة الفاتورة", "Average Invoice Value") + '</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>' + copy("جارٍ تحميل البيانات…", "Loading live data…") + '</div>' +
				'</article>' +
				'<article class="nds-sales-kpi-card" data-kpi="opportunities">' +
					'<div class="nds-sales-kpi-label">' + copy("فرص مفتوحة (CRM)", "Open Opportunities (CRM)") + '</div>' +
					'<div class="nds-sales-kpi-value" data-kpi-value>—</div>' +
					'<div class="nds-sales-kpi-trend neutral" data-kpi-trend>' + copy("جارٍ تحميل البيانات…", "Loading live data…") + '</div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-sales-charts-grid" aria-label="' + copy("تحليلات المبيعات", "Sales analytics") + '">' +
				'<article class="nds-sales-panel nds-sales-revenue-chart" aria-labelledby="nds-sales-revenue-title">' +
					'<div class="nds-sales-panel-heading"><div><h2 id="nds-sales-revenue-title">' + copy("المبيعات — آخر 6 أشهر", "Sales — Last 6 Months") + '</h2><p>' + copy("بالريال السعودي", "Saudi Riyal (SAR)") + '</p></div></div>' +
					'<div class="nds-sales-revenue-chart-body" data-revenue-chart><div class="nds-sales-loading">' + copy("جارٍ تحميل بيانات الرسم البياني…", "Loading chart data…") + '</div></div>' +
				'</article>' +
				'<article class="nds-sales-panel nds-sales-channels-chart" aria-labelledby="nds-sales-channels-title">' +
					'<div class="nds-sales-panel-heading"><div><h2 id="nds-sales-channels-title">' + copy("المبيعات حسب القناة", "Sales by Channel") + '</h2><p data-channel-caption>' + copy("النسبة من إجمالي المبيعات للفترة", "Share of sales for the period") + '</p></div></div>' +
					'<div class="nds-sales-channel-list" data-channel-chart><div class="nds-sales-loading">' + copy("جارٍ تحميل بيانات التوزيع…", "Loading channel distribution…") + '</div></div>' +
				'</article>' +
			'</section>' +
			'<section class="nds-sales-panel nds-sales-invoices" aria-labelledby="nds-sales-invoices-title">' +
				'<div class="nds-sales-panel-heading nds-sales-invoices-heading">' +
					'<div><h2 id="nds-sales-invoices-title">' + copy("أحدث فواتير المبيعات", "Latest Sales Invoices") + '</h2><p>' + copy("آخر 5 عمليات", "Latest 5 transactions") + '</p></div>' +
				'</div>' +
				'<div class="nds-sales-table-wrap">' +
					'<table class="nds-sales-invoice-table"><thead><tr><th>' + copy("رقم الفاتورة", "Invoice") + '</th><th>' + copy("العميل", "Customer") + '</th><th>' + copy("التاريخ", "Date") + '</th><th>' + copy("المبلغ", "Amount") + '</th><th>' + copy("الحالة", "Status") + '</th></tr></thead>' +
					'<tbody data-invoice-rows><tr><td colspan="5" class="nds-sales-table-empty">' + copy("جارٍ تحميل أحدث الفواتير…", "Loading latest invoices…") + '</td></tr></tbody></table>' +
				'</div>' +
			'</section>';
		board.querySelectorAll(".nds-sales-kpi-grid, .nds-sales-charts-grid, .nds-sales-invoices, .nds-sales-invoice-table, .nds-sales-invoice-table th, .nds-sales-invoice-table td").forEach((node) => {
			node.setAttribute("dir", currentDirection());
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
			container.appendChild(make("div", "nds-sales-chart-empty", copy("لا توجد مبيعات مسجلة خلال الفترة المعروضة.", "No sales recorded during the selected period.")));
			return;
		}
		const columns = make("div", "nds-sales-revenue-columns");
		buckets.forEach((item) => {
			const column = make("div", "nds-sales-revenue-column");
			const barArea = make("div", "nds-sales-revenue-bar-area");
			const bar = make("div", "nds-sales-revenue-bar");
			const height = Math.max(item.total > 0 ? 5 : 0, (item.total / maximum) * 112);
			bar.style.height = height.toFixed(1) + "px";
			bar.title = item.label + " — " + money(item.total);
			bar.setAttribute("aria-label", item.label + " " + money(item.total));
			barArea.appendChild(bar);
			const label = make("span", "nds-sales-revenue-month", item.label);
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
			return Number(value) ? copy("نقاط البيع (POS)", "Point of Sale (POS)") : copy("فواتير خارج نقاط البيع", "Non-POS Invoices");
		}
		return String(value || copy("غير محدد", "Unspecified"));
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
			container.appendChild(make("div", "nds-sales-chart-empty", copy("لا توجد بيانات كافية لتوزيع المبيعات حسب القناة.", "Not enough data to show sales by channel.")));
			return;
		}
		setText(board, "[data-channel-caption]", copy("النسبة من إجمالي الشهر", "Share of monthly sales"));
		sorted.slice(0, 3).forEach((item, index) => {
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
			Paid: ["مسددة", "Paid"],
			Unpaid: ["غير مسددة", "Unpaid"],
			Overdue: ["متأخرة", "Overdue"],
			"Partly Paid": ["مدفوعة جزئيًا", "Partly Paid"],
			Draft: ["مسودة", "Draft"],
			Submitted: ["معتمدة", "Submitted"],
			Cancelled: ["ملغاة", "Cancelled"],
			Return: ["مرتجع", "Return"],
			"Credit Note Issued": ["إشعار دائن", "Credit Note Issued"],
		};
		return (labels[status] ? copy(labels[status][0], labels[status][1]) : status) || "—";
	}

	function renderInvoices(board, invoices) {
		const body = board.querySelector("[data-invoice-rows]");
		if (!body) return;
		body.replaceChildren();
		if (!invoices || !invoices.length) {
			const row = make("tr");
			const cell = make("td", "nds-sales-table-empty", copy("لا توجد فواتير بيع معتمدة لعرضها.", "No submitted sales invoices to display."));
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

	async function loadDashboardData(board) {
		const today = todayISO();
		const start = monthStart(today, -5);

		const dailyPromise = loadDailySales(start, today);
		const opportunitiesPromise = getList("Opportunity", [
			{ COUNT: "*", as: "opportunity_count" },
			{ SUM: "opportunity_amount", as: "expected_total" },
		], [["Opportunity", "status", "=", "Open"]], { limit_page_length: 1 })
			.catch(() => null);
		const channelsPromise = loadChannelRows(monthStart(today, 0), today).catch(() => ({ field: null, rows: [] }));
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
			const previousComparableRows = (daily || []).filter((row) =>
				monthKey(row.posting_date) === previousKey
				&& Number(String(row.posting_date).slice(8, 10)) <= Number(String(today).slice(8, 10))
			);
			const previous = previousComparableRows.reduce((acc, row) => ({
				total: acc.total + Number(row.sales_total || 0),
				count: acc.count + Number(row.invoice_count || 0),
			}), { total: 0, count: 0 });
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
				setText(card, "[data-kpi-value]", copy("غير متاح", "Unavailable"));
				setTrend(card, "[data-kpi-trend]", { text: copy("تعذر تحميل بيانات الفواتير", "Could not load invoice data"), state: "neutral" });
			});
			const revenue = board.querySelector("[data-revenue-chart]");
			if (revenue) revenue.replaceChildren(make("div", "nds-sales-chart-empty", copy("تعذر تحميل بيانات المبيعات. تحقق من صلاحية قراءة الفواتير.", "Could not load sales data. Check invoice read permissions.")));
		}

		const opportunities = await opportunitiesPromise;
		const oppCard = board.querySelector('[data-kpi="opportunities"]');
		if (opportunities && opportunities.length) {
			const opp = opportunities[0];
			setText(oppCard, "[data-kpi-value]", number(opp.opportunity_count || 0));
			setTrend(oppCard, "[data-kpi-trend]", {
				text: copy("القيمة المتوقعة: ", "Expected value: ") + money(opp.expected_total || 0),
				state: "neutral",
			});
		} else {
			setText(oppCard, "[data-kpi-value]", copy("غير متاح", "Unavailable"));
			setTrend(oppCard, "[data-kpi-trend]", { text: copy("تعذر تحميل بيانات فرص CRM", "Could not load CRM opportunities"), state: "neutral" });
		}

		const channels = await channelsPromise;
		renderChannels(board, channels);

		const invoices = await invoicesPromise;
		if (invoices === null) {
			const body = board.querySelector("[data-invoice-rows]");
			if (body) {
				body.replaceChildren();
				const row = make("tr");
				const cell = make("td", "nds-sales-table-empty", copy("تعذر تحميل أحدث الفواتير بسبب الصلاحيات أو الاتصال.", "Could not load recent invoices. Check access permissions or connectivity."));
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
		let board = document.getElementById(DASHBOARD_ID);
		if (board && board.isConnected && board.parentElement === host) {
			syncDashboardDirection(board);
			renderSalesSections(host, board);
			document.body.classList.add(READY_CLASS);
			return;
		}
		if (board) board.remove();
		board = buildDashboard();
		host.insertBefore(board, host.firstChild);
		document.body.classList.add(READY_CLASS);
		loadDashboardData(board);
		renderSalesSections(host, board);
	}

	function cleanup() {
		const current = document.getElementById(DASHBOARD_ID);
		const sections = document.getElementById(SALES_SECTIONS_ID);
		if (current) current.remove();
		if (sections) sections.remove();
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
			if (!directionObserver && document.documentElement) {
				directionObserver = new MutationObserver(() => {
					const board = document.getElementById(DASHBOARD_ID);
					if (board && isSalesWorkspace()) syncDashboardDirection(board);
					scheduleSync();
				});
				directionObserver.observe(document.documentElement, {
					attributes: true,
					attributeFilter: ["dir", "lang"],
				});
			}
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