/*
 * NDS ERP Saudi — Assets Workspace dashboard ("الاصول NDS ERP").
 * UI-only: reads Asset records through the standard Frappe list API (user
 * permissions apply), never writes, and never edits the stock Assets
 * Workspace, DocTypes or any ERPNext core file. Drawing is done by the shared
 * engine in workspace_dashboard_kit.js.
 */
import { createWorkspaceDashboard } from "./workspace_dashboard_kit.js";

// Assets that are no longer live on the books.
const NOT_LIVE = ["Sold", "Scrapped", "Capitalized"];
const DISPOSED = ["Sold", "Scrapped"];
const NEEDS_ATTENTION = ["In Maintenance", "Out of Order"];

const STATUS = {
	"Draft": { label: "stDraft", tone: "muted" },
	"Submitted": { label: "stSubmitted", tone: "info" },
	"Partially Depreciated": { label: "stPartial", tone: "ok" },
	"Fully Depreciated": { label: "stFull", tone: "muted" },
	"Sold": { label: "stSold", tone: "muted" },
	"Scrapped": { label: "stScrapped", tone: "bad" },
	"In Maintenance": { label: "stMaintenance", tone: "warn" },
	"Out of Order": { label: "stOutOfOrder", tone: "bad" },
	"Issue": { label: "stIssue", tone: "info" },
	"Receipt": { label: "stReceipt", tone: "info" },
	"Capitalized": { label: "stCapitalized", tone: "muted" },
	"Work In Progress": { label: "stWip", tone: "warn" },
};

function navIcon(title) {
	const text = String(title || "").toLowerCase();
	if (/(تقرير|report)/.test(text)) return "▤";
	if (/(صيان|إصلاح|اصلاح|maint|repair)/.test(text)) return "◐";
	return "⌂";
}

const assetsDashboard = createWorkspaceDashboard({
	key: "assets",
	// Only the NDS Assets Workspace — never the stock "Assets" Workspace.
	targets: ["الاصول NDS ERP", "الأصول NDS ERP", "Assets NDS ERP", "NDS ERP Assets"],
	texts: {
		ar: {
			title: "لوحة الأصول",
			netValue: "صافي القيمة الدفترية",
			assetCount: "الأصول القائمة",
			depreciation: "الإهلاك المتراكم",
			attention: "أصول تحت الصيانة أو معطلة",
			ofCost: "من التكلفة الأصلية",
			flowTitle: "إضافات واستبعادات الأصول — آخر 6 أشهر",
			flowNote: "تكلفة الأصول المضافة والمستبعدة حسب الشهر",
			additions: "إضافات",
			disposals: "استبعادات",
			noFlow: "لا توجد إضافات أو استبعادات مسجلة خلال الفترة المحددة.",
			categoryTitle: "القيمة الدفترية حسب فئة الأصول",
			categoryNote: "صافي القيمة بعد الإهلاك لكل فئة",
			noCategory: "لا توجد قيمة أصول متاحة للعرض.",
			latestTitle: "أحدث الأصول المسجلة",
			latestNote: "آخر 8 أصول تم إنشاؤها",
			noLatest: "لا توجد أصول مسجلة لعرضها.",
			colAsset: "الأصل",
			colCategory: "الفئة",
			colLocation: "الموقع",
			colPurchased: "تاريخ الشراء",
			colCost: "التكلفة",
			colBook: "القيمة الدفترية",
			colStatus: "الحالة",
			stDraft: "مسودة",
			stSubmitted: "معتمد",
			stPartial: "مهلك جزئيًا",
			stFull: "مهلك بالكامل",
			stSold: "مباع",
			stScrapped: "مستبعد (خردة)",
			stMaintenance: "تحت الصيانة",
			stOutOfOrder: "معطل",
			stIssue: "مصروف",
			stReceipt: "مستلم",
			stCapitalized: "مرسمل",
			stWip: "قيد التنفيذ",
		},
		en: {
			title: "Assets Dashboard",
			netValue: "Net Book Value",
			assetCount: "Live Assets",
			depreciation: "Accumulated Depreciation",
			attention: "Assets In Maintenance or Out of Order",
			ofCost: "of original cost",
			flowTitle: "Asset Additions vs Disposals — Last 6 Months",
			flowNote: "Cost of assets added and disposed, by month",
			additions: "Additions",
			disposals: "Disposals",
			noFlow: "No asset additions or disposals were recorded during this period.",
			categoryTitle: "Book Value by Asset Category",
			categoryNote: "Net value after depreciation per category",
			noCategory: "No asset value is available to display.",
			latestTitle: "Latest Registered Assets",
			latestNote: "The 8 most recently created assets",
			noLatest: "No assets are registered yet.",
			colAsset: "Asset",
			colCategory: "Category",
			colLocation: "Location",
			colPurchased: "Purchase Date",
			colCost: "Cost",
			colBook: "Book Value",
			colStatus: "Status",
			stDraft: "Draft",
			stSubmitted: "Submitted",
			stPartial: "Partially Depreciated",
			stFull: "Fully Depreciated",
			stSold: "Sold",
			stScrapped: "Scrapped",
			stMaintenance: "In Maintenance",
			stOutOfOrder: "Out of Order",
			stIssue: "Issued",
			stReceipt: "Received",
			stCapitalized: "Capitalized",
			stWip: "Work In Progress",
		},
	},
	kpis: [
		{ id: "net-value", tone: "navy", icon: "◈", label: "netValue" },
		{ id: "asset-count", tone: "blue", icon: "▦", label: "assetCount" },
		{ id: "depreciation", tone: "gold", icon: "↘", label: "depreciation" },
		{ id: "attention", tone: "red", icon: "!", label: "attention" },
	],
	charts: [
		{
			id: "flow", kind: "columns", title: "flowTitle", note: "flowNote", mark: "↕", markTone: "green",
			format: "money", empty: "noFlow",
			series: [
				{ id: "additions", label: "additions", tone: "incoming" },
				{ id: "disposals", label: "disposals", tone: "outgoing" },
			],
		},
		{
			id: "category", kind: "bars", title: "categoryTitle", note: "categoryNote", mark: "▥", markTone: "blue",
			format: "money", empty: "noCategory",
		},
	],
	table: {
		title: "latestTitle", note: "latestNote", mark: "▤", markTone: "blue", empty: "noLatest",
		columns: [
			{ id: "name", label: "colAsset", kind: "link", doctype: "Asset", nameField: "name", labelField: "asset_name", subField: "name" },
			{ id: "asset_category", label: "colCategory", kind: "text" },
			{ id: "location", label: "colLocation", kind: "text" },
			{ id: "purchase_date", label: "colPurchased", kind: "date" },
			{ id: "gross_purchase_amount", label: "colCost", kind: "money" },
			{ id: "value_after_depreciation", label: "colBook", kind: "money" },
			{ id: "status", label: "colStatus", kind: "status", map: STATUS },
		],
	},
	navIcon,
	sources(ctx) {
		const { company, today, getList, aggregate, money, fmt, monthStart } = ctx;
		const scope = company ? [["Asset", "company", "=", company]] : [];
		const live = [["Asset", "docstatus", "=", 1], ["Asset", "status", "not in", NOT_LIVE]].concat(scope);
		const from = monthStart(today, -5);

		const grossLive = aggregate("Asset", "SUM", "gross_purchase_amount", "gross_total", live);
		const bookLive = aggregate("Asset", "SUM", "value_after_depreciation", "book_total", live);

		const byMonth = (field, filters) =>
			getList("Asset", [field, { SUM: "gross_purchase_amount", as: "total_value" }],
				filters.concat([["Asset", field, ">=", from], ["Asset", field, "<=", today]]).concat(scope),
				{ group_by: field, order_by: field + " asc", limit_page_length: 1000 })
				.then((rows) => (Array.isArray(rows) ? rows.map((r) => ({ date: r[field], value: r.total_value })) : null));

		return {
			kpis: {
				"net-value": bookLive.then((value) => ({ display: money(value) })),
				"asset-count": aggregate("Asset", "COUNT", "*", "asset_total", live).then((value) => ({ display: fmt(value) })),
				"depreciation": Promise.all([grossLive, bookLive]).then(([gross, book]) => {
					const accumulated = Math.max(0, gross - book);
					const pct = gross > 0 ? (accumulated / gross) * 100 : 0;
					return { display: money(accumulated), caption: fmt(pct, 1) + "% " + ctx.t().ofCost };
				}),
				"attention": aggregate("Asset", "COUNT", "*", "attention_total",
					[["Asset", "docstatus", "=", 1], ["Asset", "status", "in", NEEDS_ATTENTION]].concat(scope))
					.then((value) => ({ display: fmt(value) })),
			},
			charts: {
				flow: Promise.all([
					byMonth("purchase_date", [["Asset", "docstatus", "=", 1]]),
					byMonth("disposal_date", [["Asset", "docstatus", "=", 1], ["Asset", "status", "in", DISPOSED]]),
				]).then(([additions, disposals]) => (additions === null || disposals === null ? null : { additions, disposals })),
				category: getList("Asset", ["asset_category", { SUM: "value_after_depreciation", as: "total_value" }], live,
					{ group_by: "asset_category", order_by: "total_value desc", limit_page_length: 8 })
					.then((rows) => (Array.isArray(rows) ? rows.map((r) => ({ label: r.asset_category || "—", value: r.total_value })) : null)),
			},
			table: getList("Asset",
				["name", "asset_name", "asset_category", "location", "purchase_date", "gross_purchase_amount", "value_after_depreciation", "status"],
				[["Asset", "docstatus", "<", 2]].concat(scope),
				{ order_by: "creation desc", limit_page_length: 8 }),
		};
	},
});

export { assetsDashboard };
