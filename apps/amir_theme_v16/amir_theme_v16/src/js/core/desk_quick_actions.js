/**
 * Desktop quick actions.
 *
 * Adds permission-filtered create shortcuts to the Desk landing page only.
 * It reuses Frappe's existing new-document flow and boot-time create-permission
 * list; no API, route, database schema, or business rule is added.
 */
import { onDeskReady } from "./desk_host.js";

const ACTIONS = [
	{ doctype: "Sales Invoice", ar: "فاتورة مبيعات جديدة", en: "New Sales Invoice", icon: "file-text" },
	{ doctype: "Sales Order", ar: "أمر بيع جديد", en: "New Sales Order", icon: "clipboard-list" },
	{ doctype: "Customer", ar: "عميل جديد", en: "New Customer", icon: "users" },
	{ doctype: "Payment Entry", ar: "تسجيل دفعة", en: "New Payment Entry", icon: "credit-card" },
	{ doctype: "Purchase Invoice", ar: "فاتورة مشتريات جديدة", en: "New Purchase Invoice", icon: "receipt" },
	{ doctype: "Purchase Order", ar: "أمر شراء جديد", en: "New Purchase Order", icon: "shopping-cart" },
	{ doctype: "Supplier", ar: "مورد جديد", en: "New Supplier", icon: "truck" },
	{ doctype: "Item", ar: "صنف جديد", en: "New Item", icon: "package" },
];

function isArabic() {
	const lang = String(frappe.boot?.lang || document.documentElement.lang || "").toLowerCase();
	return document.documentElement.dir === "rtl" || lang.startsWith("ar");
}

function allowedActions() {
	const permitted = frappe.boot?.user?.can_create;
	if (!Array.isArray(permitted)) return [];
	const canCreate = new Set(permitted);
	return ACTIONS.filter(({ doctype }) => canCreate.has(doctype));
}

function iconMarkup(name, className) {
	const symbol = document.getElementById(`icon-${name}`) ? name : "layout-grid";
	return (
		`<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
		`<use href="#icon-${symbol}"></use></svg>`
	);
}

function buildSection(actions, arabic) {
	const section = document.createElement("section");
	section.className = "amt-quick-actions";
	section.setAttribute("role", "region");
	section.setAttribute("aria-labelledby", "amt-quick-actions-title");

	const header = document.createElement("div");
	header.className = "amt-quick-actions-header";

	const title = document.createElement("h2");
	title.className = "amt-quick-actions-title";
	title.id = "amt-quick-actions-title";
	title.textContent = arabic ? "الإجراءات السريعة" : "Quick Actions";

	const rule = document.createElement("span");
	rule.className = "amt-quick-actions-rule";
	rule.setAttribute("aria-hidden", "true");
	header.append(title, rule);

	const grid = document.createElement("div");
	grid.className = "amt-quick-actions-grid";

	for (const action of actions) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "amt-quick-action";
		button.dataset.doctype = action.doctype;
		button.setAttribute("aria-label", action[arabic ? "ar" : "en"]);

		const icon = document.createElement("span");
		icon.className = "amt-quick-action-icon";
		icon.innerHTML = iconMarkup(action.icon, "amt-quick-action-glyph");

		const label = document.createElement("span");
		label.className = "amt-quick-action-label";
		label.textContent = action[arabic ? "ar" : "en"];

		const arrow = document.createElement("span");
		arrow.className = "amt-quick-action-arrow";
		arrow.innerHTML = iconMarkup(arabic ? "arrow-left" : "arrow-right", "amt-quick-action-arrow-glyph");

		button.append(icon, label, arrow);
		button.addEventListener("click", () => {
			// Re-check the boot permission before opening the native form flow.
			const permitted = frappe.boot?.user?.can_create;
			if (!Array.isArray(permitted) || !permitted.includes(action.doctype)) return;
			if (typeof frappe.new_doc === "function") frappe.new_doc(action.doctype);
		});
		grid.appendChild(button);
	}

	if (actions.length) {
		section.append(header, grid);
	} else {
		const empty = document.createElement("p");
		empty.className = "amt-quick-actions-empty";
		empty.textContent = arabic
			? "لا توجد إجراءات إنشاء متاحة لحسابك."
			: "No create actions are available for your account.";
		section.append(header, empty);
	}
	return section;
}

function render() {
	const host = document.querySelector(".desktop-container");
	if (!host || !host.isConnected) return;

	// Never add a second copy if the section is already present.
	const existing = host.querySelector(".amt-quick-actions");
	if (existing) {
		host.classList.add("amt-has-quick-actions");
		return;
	}

	const actions = allowedActions();
	const launcher = host.querySelector(":scope > .icons-container");
	if (!launcher) {
		console.warn("[amir_theme] Quick Actions: Desk launcher host not found.");
		return;
	}

	const section = buildSection(actions, isArabic());
	// Keep the existing app icons first; quick actions follow the main launcher.
	launcher.after(section);
	host.classList.add("amt-has-quick-actions");
}

export const quickActions = {
	mount() {
		onDeskReady(render);
	},
};
