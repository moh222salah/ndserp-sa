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
			period: "الفترة الحالية",
			netProfit: "صافي الربح (الشهر)",
			revenue: "الإيرادات",
			expenses: "المصروفات",
			receivables: "ذمم مدينة مستحقة",
			margin: "{value}% هامش",
			overdueCount: "{count} فاتورة متأخرة",
			monthlyChange: "مقارنة بالشهر السابق",
			expensesByCategory: "المصروفات حسب الحساب",
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
			loading: "جارٍ تحميل البيانات…",
			loadingCategories: "جارٍ تحميل حسابات المصروفات…",
			loadingChart: "جارٍ تحميل البيانات المالية…",
			loadingInvoices: "جارٍ تحميل الفواتير…",
			noExpenses: "لا توجد حسابات مصروفات بها حركة في الفترة الحالية.",
			noFinancialData: "لا توجد حركة مالية في الفترة المعروضة.",
			noInvoices: "لا توجد فواتير غير مسددة لعرضها.",
			dataError: "تعذر تحميل البيانات. تحقق من الصلاحيات والاتصال.",
			companyMissing: "لم يتم تعيين شركة افتراضية للمستخدم.",
			newActivity: "نشاط جديد في الفترة الحالية",
			noActivity: "لا توجد حركة في الفترتين",
			noCompare: "لا توجد بيانات مقارنة كافية",
			sar: "ر.س",
		},
		en: {
			title: "Accounts Dashboard",
			breadcrumbModule: "Accounts",
			breadcrumbOverview: "Overview",
			period: "Current period",
			netProfit: "Net Profit (Month)",
			revenue: "Revenue",
			expenses: "Expenses",
			receivables: "Accounts Receivable",
			margin: "{value}% margin",
			overdueCount: "{count} overdue invoices",
			monthlyChange: "Compared with previous month",
			expensesByCategory: "Expenses by Account",
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
			loading: "Loading live data…",
			loadingCategories: "Loading expense accounts…",
			loadingChart: "Loading financial activity…",
			loadingInvoices: "Loading invoices…",
			noExpenses: "No expense-account activity in this period.",
			noFinancialData: "No financial activity in the displayed period.",
			noInvoices: "No unpaid invoices to display.",
			dataError: "Unable to load data. Check permissions and connectivity.",
			companyMissing: "No default company is assigned to this user.",
			newActivity: "New activity in the current period",
			noActivity: "No activity in either period",
			noCompare: "Not enough comparison data",
			sar: "SAR",
		},
	};

	let installStarted = false;
	let preservedEditor = null;
	let editorPlaceholder = null;
	let observer = null;
	let observedBody = null;
	let scheduledTimers = [];
	let directionSnapshot = new Map();
	let directionObserver = null;

	function setScopedDirection(node, direction) {
		if (!node) return;
		if (!directionSnapshot.has(node)) directionSnapshot.set(node, { dir: node.hasAttribute("dir") ? node.getAttribute("dir") : null });
		if (node.getAttribute("dir") !== direction) node.setAttribute("dir", direction);
	}
	function syncWorkspaceDirection(page, language) {
		const direction = language === "ar" ? "rtl" : "ltr";
		document.body?.classList.toggle("nds-accounts-rtl", direction === "rtl");
		document.body?.classList.toggle("nds-accounts-ltr", direction === "ltr");
		const header = page?.querySelector(".page-head");
		const navbar = document.querySelector(".navbar");
		const navbarContent = navbar?.querySelector(".container, .container-fluid");
		const targets = [
			document.documentElement,
			document.body,
			page,
			header,
			header?.querySelector(".page-head-content"),
			header?.querySelector(".title-area"),
			header?.querySelector(".title-text"),
			header?.querySelector(".page-actions"),
			header?.querySelector(".page-head-actions"),
			header?.querySelector(".navbar-breadcrumbs"),
			...(header ? Array.from(header.querySelectorAll(".navbar-breadcrumbs li")) : []),
			page?.querySelector(".layout-main-section"),
			navbar,
			navbarContent,
			navbar?.querySelector(".navbar-collapse"),
			navbar?.querySelector(".navbar-nav"),
		];
		targets.forEach((node) => setScopedDirection(node, direction));
		const board = document.getElementById(DASHBOARD_ID);
		if (board) { board.setAttribute("dir", direction); board.setAttribute("lang", language); board.dataset.language = language; }
	}
	function restoreWorkspaceDirection() {
		directionSnapshot.forEach((snapshot, node) => {
			if (snapshot.dir === null) node.removeAttribute("dir");
			else node.setAttribute("dir", snapshot.dir);
		});
		directionSnapshot.clear();
		document.body?.classList.remove("nds-accounts-rtl", "nds-accounts-ltr");
	}

	function getLanguage() {
		const root = document.documentElement;
		const boot = window.frappe && frappe.boot || {};
		const candidates = [
			boot.lang,
			root && root.lang,
			boot.user && boot.user.language,
			boot.user && boot.user.language_code,
			boot.user_language,
			boot.user_language_code,
		];
		const candidate = candidates.find((value) => {
			const language = String(value || "").trim().toLowerCase();
			return language.startsWith("ar") || language.startsWith("en");
		});
		if (candidate) return String(candidate).trim().toLowerCase().startsWith("en") ? "en" : "ar";
		return String(root && root.getAttribute("dir") || "").toLowerCase() === "ltr" ? "en" : "ar";
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
			if (routeName && !expected.has(routeName)) return false;
			const pageTitle = normalize(document.querySelector(".workspace-title")?.textContent);
			const sidebarTitle = normalize(frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_title);
			const scoped = Boolean(document.body && document.body.classList.contains("amt-accounts-workspace"));

			// The theme's route-scoped class is maintained by the existing Workspace
			// enhancer. Use it as a fallback during route/title settling, not as a
			// replacement for Frappe's canonical route check.
			return expected.has(routeName)
				|| expected.has(pageTitle)
				|| expected.has(sidebarTitle)
				|| scoped;
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
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small><span class="nds-accounts-kpi-indicator positive" data-kpi-trend></span></div>' +
					'<div class="nds-accounts-kpi-foot"><span class="nds-accounts-kpi-foot-caption"></span></div>' +
				'</article>' +
				'<article class="nds-accounts-kpi-card" data-kpi="expenses">' +
					'<div class="nds-accounts-kpi-top"><span class="nds-accounts-kpi-label"></span><span class="nds-accounts-kpi-icon" aria-hidden="true">↗</span></div>' +
					'<div class="nds-accounts-kpi-value"><span data-kpi-value></span><small class="nds-accounts-currency"></small><span class="nds-accounts-kpi-indicator caution" data-kpi-trend></span></div>' +
					'<div class="nds-accounts-kpi-foot"><span class="nds-accounts-kpi-foot-caption"></span></div>' +
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
					'<div class="nds-accounts-expenses-axis" aria-hidden="true"><span>100%</span><span>50%</span><span>0%</span></div>' +
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
					'<span class="nds-accounts-invoice-count">—</span>' +
				'</div>' +
				'<div class="nds-accounts-table-wrap"><table class="nds-accounts-invoice-table">' +
					'<thead><tr><th data-th="id"></th><th data-th="customer"></th><th data-th="due"></th><th data-th="amount"></th><th data-th="status"></th></tr></thead>' +
					'<tbody data-invoice-rows></tbody>' +
				'</table></div>' +
			'</section>';

		board.querySelector("[data-accounts-title]").textContent = t.title;
		board.querySelector("[data-accounts-module]").textContent = t.breadcrumbModule;
		board.querySelector("[data-accounts-overview]").textContent = t.breadcrumbOverview;

		const kpis = [["profit",t.netProfit],["revenue",t.revenue],["expenses",t.expenses],["receivables",t.receivables]];
		kpis.forEach(([key,label]) => {
			const card=board.querySelector('[data-kpi="'+key+'"]'); if(!card)return;
			card.querySelector(".nds-accounts-kpi-label").textContent=label;
			card.querySelector("[data-kpi-value]").textContent="—";
			card.querySelector(".nds-accounts-currency").textContent=t.sar;
			const trend=card.querySelector("[data-kpi-trend]"); if(trend)trend.textContent=t.loading;
			const caption=card.querySelector(".nds-accounts-kpi-foot-caption"); if(caption)caption.textContent=t.monthlyChange;
		});
		board.querySelector("[data-expenses-heading]").textContent=t.expensesByCategory;
		board.querySelector("[data-expenses-caption]").textContent=t.categoryCaption;
		board.querySelector("[data-revenue-heading]").textContent=t.revenueVsExpenses;
		board.querySelector("[data-revenue-caption]").textContent=t.lastSixMonths;
		board.querySelector("[data-revenue-legend]").textContent=t.revenueLegend;
		board.querySelector("[data-expenses-legend]").textContent=t.expensesLegend;
		board.querySelector("[data-invoices-heading]").textContent=t.unpaidInvoices;
		board.querySelector("[data-invoices-caption]").textContent=t.highestCurrently;
		board.querySelector('[data-th="id"]').textContent=t.invoiceNumber;
		board.querySelector('[data-th="customer"]').textContent=t.entity;
		board.querySelector('[data-th="due"]').textContent=t.dueDate;
		board.querySelector('[data-th="amount"]').textContent=t.amount;
		board.querySelector('[data-th="status"]').textContent=t.status;
		board.querySelector(".nds-accounts-invoice-count").textContent="—";
		renderExpenses(board,t,null,language);
		renderMonths(board,t,language,null);
		renderInvoices(board,t,null,null,"SAR");
		return board;
	}

	function rpc(method,args){return new Promise((resolve,reject)=>{if(!window.frappe||typeof frappe.call!=="function")return reject(new Error("Frappe unavailable"));frappe.call({method,args,callback:r=>resolve(r?r.message:null),error:e=>reject(e||new Error("Request failed"))});});}
	function list(dt,fields,filters,extra){return rpc("frappe.client.get_list",Object.assign({doctype:dt,fields,filters:filters||[],limit_page_length:5000},extra||{})).then(r=>Array.isArray(r)?r:[]);}
	async function aggregate(dt,fields,filters,extra){const rows=await list(dt,fields,filters,Object.assign({limit_page_length:1},extra||{}));return rows[0]||{};}
	function chunks(items,size){const out=[];for(let i=0;i<items.length;i+=size)out.push(items.slice(i,i+size));return out;}
	function iso(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");}
	function today(){try{if(frappe.datetime?.get_today)return frappe.datetime.get_today();}catch(_){}return iso(new Date());}
	function monthStart(v,o){const p=String(v).slice(0,7).split("-").map(Number);return iso(new Date(p[0],p[1]-1+(o||0),1,12));}
	function monthKey(v){return String(v||"").slice(0,7);}
	function localeFor(lang){return lang==="ar"?"ar-SA":"en-US";}
	function num(v,lang,d){const n=Number(v||0);return Number.isFinite(n)?new Intl.NumberFormat(localeFor(lang),{maximumFractionDigits:d===undefined?0:d,minimumFractionDigits:0}).format(n):"—";}
	function money(v,c,lang){return num(v,lang,2)+" "+String(c||"SAR").toUpperCase();}
	function periodLabel(v,lang){try{return new Intl.DateTimeFormat(localeFor(lang),{month:"long",year:"numeric",calendar:"gregory"}).format(new Date(monthKey(v)+"-01T12:00:00"));}catch(_){return monthKey(v);}}
	function sumMonth(rows,key,kind,cutoff){return (rows||[]).reduce((s,r)=>{if(monthKey(r.posting_date)!==key||(cutoff&&Number(String(r.posting_date).slice(8,10))>cutoff))return s;const d=Number(r.debit_total||0),c=Number(r.credit_total||0);return s+(kind==="income"?c-d:d-c);},0);}
	function deltaText(a,b,lang,t){if(Math.abs(b)<1e-6)return{text:Math.abs(a)<1e-6?t.noActivity:t.newActivity,state:Math.abs(a)<1e-6?"neutral":"positive"};const d=(a-b)/Math.abs(b)*100;return{text:(d>0?"↑ ":d<0?"↓ ":"")+num(Math.abs(d),lang,1)+"% "+t.monthlyChange,state:d>0?"positive":d<0?"alert":"neutral"};}
	function setMetric(board,key,value,caption,state){const c=board.querySelector('[data-kpi="'+key+'"]');if(!c)return;const v=c.querySelector("[data-kpi-value]");if(v)v.textContent=value===null||value===undefined?"—":String(value);const tr=c.querySelector("[data-kpi-trend]");if(tr){tr.textContent=caption||"";["positive","caution","alert","neutral"].forEach(n=>tr.classList.remove(n));if(state)tr.classList.add(state);}}
	function unavailable(board,key,message){setMetric(board,key,"—",message,"neutral");}
	function ledgerFilters(company,names,start,end){return [["GL Entry","company","=",company],["GL Entry","posting_date",">=",start],["GL Entry","posting_date","<=",end],["GL Entry","is_cancelled","=",0],["GL Entry","account","in",names]];}
	async function byDate(company,names,start,end){if(!names.length)return[];return(await Promise.all(chunks(names,180).map(g=>list("GL Entry",["posting_date",{SUM:"debit",as:"debit_total"},{SUM:"credit",as:"credit_total"}],ledgerFilters(company,g,start,end),{group_by:"posting_date",order_by:"posting_date asc",limit_page_length:5000})))).flat();}
	async function byAccount(company,names,start,end){if(!names.length)return[];return(await Promise.all(chunks(names,180).map(g=>list("GL Entry",["account",{SUM:"debit",as:"debit_total"},{SUM:"credit",as:"credit_total"}],ledgerFilters(company,g,start,end),{group_by:"account",order_by:"debit_total desc",limit_page_length:5000})))).flat();}
	async function receivable(company,names,end){if(!names.length)return 0;const rows=await Promise.all(chunks(names,180).map(g=>aggregate("GL Entry",[{SUM:"debit",as:"debit_total"},{SUM:"credit",as:"credit_total"}],[["GL Entry","company","=",company],["GL Entry","posting_date","<=",end],["GL Entry","is_cancelled","=",0],["GL Entry","account","in",g]])));return rows.reduce((s,r)=>s+Number(r.debit_total||0)-Number(r.credit_total||0),0);}
	function renderExpenses(board,t,items,lang){const host=board.querySelector("[data-expense-list]");if(!host)return;host.replaceChildren();if(items===null){host.appendChild(make("div","nds-accounts-chart-empty",t.loadingCategories));return;}if(items===false){host.appendChild(make("div","nds-accounts-chart-empty",t.dataError));return;}if(!items.length){host.appendChild(make("div","nds-accounts-chart-empty",t.noExpenses));return;}items.forEach((x,i)=>{const row=make("div","nds-accounts-expense-row tone-"+["payroll","cogs","operational"][i%3]),head=make("div","nds-accounts-expense-head");head.append(make("span","nds-accounts-expense-label",x.label),make("span","nds-accounts-expense-pct",num(x.pct,lang,1)+"%"));const track=make("div","nds-accounts-expense-track"),fill=make("span","nds-accounts-expense-fill");fill.style.width=Math.max(0,Math.min(100,Number(x.pct||0)))+"%";fill.title=x.label+" — "+money(x.total,board.dataset.currency,lang);fill.setAttribute("aria-hidden","true");track.appendChild(fill);row.append(head,track);host.appendChild(row);});}
	function renderMonths(board,t,lang,months){const plot=board.querySelector("[data-month-chart]");if(!plot)return;plot.replaceChildren();if(months===null){plot.appendChild(make("div","nds-accounts-chart-empty",t.loadingChart));return;}if(months===false||!months.some(m=>m.revenue||m.expenses)){plot.appendChild(make("div","nds-accounts-chart-empty",months===false?t.dataError:t.noFinancialData));return;}const grid=make("div","nds-accounts-chart-columns"),max=Math.max(1,...months.map(m=>Math.max(m.revenue,m.expenses)));months.forEach(m=>{const col=make("div","nds-accounts-month-column"),bars=make("div","nds-accounts-month-bars"),r=make("span","nds-accounts-bar revenue"),e=make("span","nds-accounts-bar expenses");r.style.height=(m.revenue>0?Math.max(3,m.revenue/max*100):0)+"%";e.style.height=(m.expenses>0?Math.max(3,m.expenses/max*100):0)+"%";r.title=t.revenueLegend+" — "+m.label+": "+money(m.revenue,board.dataset.currency,lang);e.title=t.expensesLegend+" — "+m.label+": "+money(m.expenses,board.dataset.currency,lang);r.setAttribute("aria-label",r.title);e.setAttribute("aria-label",e.title);bars.append(r,e);col.append(bars,make("span","nds-accounts-month-label",m.label));grid.appendChild(col);});plot.appendChild(grid);}
	function renderInvoices(board,t,rows,now,currency){const body=board.querySelector("[data-invoice-rows]");if(!body)return;body.replaceChildren();if(rows===null||rows===false){const row=make("tr"),cell=make("td","nds-accounts-table-empty",rows===null?t.loadingInvoices:t.dataError);cell.colSpan=5;row.appendChild(cell);body.appendChild(row);return;}board.querySelector(".nds-accounts-invoice-count").textContent=num(rows.length,board.dataset.language);if(!rows.length){const row=make("tr"),cell=make("td","nds-accounts-table-empty",t.noInvoices);cell.colSpan=5;row.appendChild(cell);body.appendChild(row);return;}rows.forEach(inv=>{const row=make("tr"),id=make("td","invoice-id",inv.name||"—"),cust=make("td","invoice-customer",inv.customer||"—"),due=make("td","invoice-date",inv.due_date||"—");id.setAttribute("dir","ltr");due.setAttribute("dir","ltr");const amt=make("td","invoice-amount"),out=Number(inv.outstanding_amount||0);amt.append(make("span","invoice-amount-value",num(out,board.dataset.language,2)),make("small","invoice-currency",inv.currency||currency));const late=Boolean(inv.due_date&&inv.due_date<now)||String(inv.status||"")==="Overdue",status=make("td","invoice-status");status.appendChild(make("span","nds-accounts-status "+(late?"overdue":"collecting"),late?t.overdue:t.collecting));row.append(id,cust,due,amt,status);body.appendChild(row);});}
	async function loadDashboard(board){const lang=board.dataset.language==="en"?"en":"ar",t=LANGUAGES[lang],now=today(),curKey=monthKey(now),start=monthStart(now,-5),curStart=monthStart(now,0),prevKey=monthKey(monthStart(now,-1)),day=Number(String(now).slice(8,10));const company=(window.frappe&&frappe.defaults&&frappe.defaults.get_user_default?frappe.defaults.get_user_default("Company"):null)||(frappe.boot&&frappe.boot.sysdefaults&&frappe.boot.sysdefaults.company)||"",currency=String((frappe.boot&&frappe.boot.sysdefaults&&frappe.boot.sysdefaults.currency)||"SAR").toUpperCase();board.dataset.currency=currency;board.querySelectorAll(".nds-accounts-currency").forEach(n=>n.textContent=currency);const p=board.querySelector(".nds-accounts-dashboard-period");if(p){p.setAttribute("aria-label",periodLabel(now,lang));const pl=p.querySelector("span:last-child");if(pl)pl.textContent=periodLabel(now,lang);}if(!company){["profit","revenue","expenses","receivables"].forEach(k=>unavailable(board,k,t.companyMissing));renderExpenses(board,t,false,lang);renderMonths(board,t,lang,false);renderInvoices(board,t,false,now,currency);return;}
		const req=await Promise.allSettled([
			list("Account",["name","account_name","root_type","account_type","is_group","disabled"],[["Account","company","=",company],["Account","is_group","=",0],["Account","disabled","=",0]],{order_by:"lft asc",limit_page_length:5000}),
			aggregate("Sales Invoice",[{COUNT:"*",as:"invoice_count"}],[["Sales Invoice","company","=",company],["Sales Invoice","docstatus","=",1],["Sales Invoice","is_return","=",0],["Sales Invoice","outstanding_amount",">",0],["Sales Invoice","due_date","<",now]]),
			list("Sales Invoice",["name","customer","due_date","outstanding_amount","currency","status"],[["Sales Invoice","company","=",company],["Sales Invoice","docstatus","=",1],["Sales Invoice","is_return","=",0],["Sales Invoice","outstanding_amount",">",0]],{order_by:"outstanding_amount desc",limit_page_length:5})
		]);if(!board.isConnected)return;const ok=req[0].status==="fulfilled",accounts=ok?req[0].value:[],map=new Map(accounts.map(a=>[a.name,a])),inc=accounts.filter(a=>a.root_type==="Income").map(a=>a.name),exp=accounts.filter(a=>a.root_type==="Expense").map(a=>a.name),rec=accounts.filter(a=>a.account_type==="Receivable").map(a=>a.name);let fin=null;if(ok)fin=await Promise.allSettled([byDate(company,inc,start,now),byDate(company,exp,start,now),byAccount(company,exp,curStart,now),receivable(company,rec,now)]);if(!board.isConnected)return;
		if(ok&&fin&&fin[0].status==="fulfilled"&&fin[1].status==="fulfilled"){const ir=fin[0].value,er=fin[1].value,revenue=sumMonth(ir,curKey,"income"),expenses=sumMonth(er,curKey,"expense"),profit=revenue-expenses,pr=sumMonth(ir,prevKey,"income",day),pe=sumMonth(er,prevKey,"expense",day),margin=revenue?profit/revenue*100:0,rt=deltaText(revenue,pr,lang,t),et=deltaText(expenses,pe,lang,t);setMetric(board,"revenue",num(revenue,lang),rt.text,rt.state);setMetric(board,"expenses",num(expenses,lang),et.text,et.state);setMetric(board,"profit",num(profit,lang),t.margin.replace("{value}",num(margin,lang,1)),profit>=0?"positive":"alert");const months=[];for(let o=0;o>=-5;o--){const d=monthStart(now,o),k=monthKey(d);let label=k;try{label=new Intl.DateTimeFormat(localeFor(lang),{month:"short",calendar:"gregory"}).format(new Date(d+"T12:00:00"));}catch(_){}months.push({key:k,label,revenue:sumMonth(ir,k,"income"),expenses:sumMonth(er,k,"expense")});}renderMonths(board,t,lang,months);if(fin[2].status==="fulfilled"){const amounts=fin[2].value.map(r=>({label:(map.get(r.account)||{}).account_name||r.account,total:Number(r.debit_total||0)-Number(r.credit_total||0)})).filter(x=>x.label&&x.total>0).sort((a,b)=>b.total-a.total),total=amounts.reduce((s,x)=>s+x.total,0);renderExpenses(board,t,amounts.slice(0,6).map(x=>Object.assign(x,{pct:total?x.total/total*100:0})),lang);}else renderExpenses(board,t,false,lang);if(fin[3].status==="fulfilled"){const overdue=Number(req[1].status==="fulfilled"?req[1].value.invoice_count||0:0);setMetric(board,"receivables",num(fin[3].value,lang),t.overdueCount.replace("{count}",num(overdue,lang)),overdue?"alert":"neutral");}else unavailable(board,"receivables",t.dataError);}else{["profit","revenue","expenses","receivables"].forEach(k=>unavailable(board,k,t.dataError));renderExpenses(board,t,false,lang);renderMonths(board,t,lang,false);}if(req[1].status!=="fulfilled"){const tr=board.querySelector('[data-kpi="receivables"] [data-kpi-trend]');if(tr)tr.textContent=t.dataError;}renderInvoices(board,t,req[2].status==="fulfilled"?req[2].value:false,now,currency);}


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

		// Frappe v16 creates the Workspaces wrapper as #page-Workspaces. Resolve
		// from the editor as a fallback in case a theme or Frappe re-render changes
		// the wrapper id while keeping the native Workspace editor intact.
		const knownPage = document.getElementById("page-Workspaces")
			|| document.querySelector('.page-container[data-page-route="Workspaces"]');
		const existingEditor = knownPage?.querySelector("#editorjs") || document.querySelector("#editorjs");
		const page = knownPage || existingEditor?.closest(".page-container");
		const host = existingEditor?.closest(".layout-main-section")
			|| page?.querySelector(".layout-main-section");
		if (!host) return;

		// Keep styling deterministic; do not depend on the sidebar enhancer's
		// separate MutationObserver winning the same-render timing race.
		document.body.classList.add("amt-accounts-workspace");

		const language = getLanguage();
		syncWorkspaceDirection(page, language);
		const current = document.getElementById(DASHBOARD_ID);
		if (current && current.isConnected && current.parentElement === host && current.dataset.language === language) {
			document.body.classList.add(READY_CLASS);
			syncWorkspaceDirection(page, language);
			detachWorkspaceEditor(page);
			return;
		}
		const next = buildDashboard(language);
		if (current && current.parentElement) current.replaceWith(next);
		else host.insertBefore(next, host.firstChild);
		document.body.classList.add(READY_CLASS);
		syncWorkspaceDirection(page, language);
		void loadDashboard(next);
		detachWorkspaceEditor(page);
	}

	function cleanup() {
		const board = document.getElementById(DASHBOARD_ID);
		if (board) board.remove();
		restoreWorkspaceEditor();
		restoreWorkspaceDirection();
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
			if (!directionObserver && document.documentElement) {
				directionObserver = new MutationObserver(() => { if (isAccountsWorkspace()) scheduleSync(); });
				directionObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["dir", "lang"] });
			}
			if (document.body && observedBody !== document.body) {
				if (observer) observer.disconnect();
				observedBody = document.body;
				observer = new MutationObserver(() => {
					if (isAccountsWorkspace()) {
						if (!document.getElementById(DASHBOARD_ID)) scheduleSync();
						else {
							const page = document.querySelector("#page-Workspaces");
							syncWorkspaceDirection(page, getLanguage());
							detachWorkspaceEditor(page);
						}
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
