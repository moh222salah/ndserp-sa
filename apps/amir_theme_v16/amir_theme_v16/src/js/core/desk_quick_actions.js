/**
 * Desktop quick actions.
 *
 * Adds permission-filtered create shortcuts to the Desk landing page only.
 * It reuses Frappe's new-document flow and create-permission list; report navigation
 * uses standard Frappe routing without adding custom APIs or business rules.
 */
import { onDeskReady } from "./desk_host.js";

const ACTIONS = [
	{ doctype: "Sales Invoice", ar: "فاتورة مبيعات", en: "Sales Invoice", icon: "invoice" },
	{ doctype: "Purchase Invoice", ar: "فاتورة مشتريات", en: "Purchase Invoice", icon: "briefcase" },
	{ doctype: "Payment Entry", ar: "سند قبض", en: "Payment Receipt", icon: "credit-card" },
	{ doctype: "Customer", ar: "عميل جديد", en: "New Customer", icon: "user" },
	{ doctype: "Stock Entry", ar: "حركة مخزون", en: "Stock Entry", icon: "package" },
	{ doctype: "Journal Entry", ar: "قيد يومية", en: "Journal Entry", icon: "ledger" },
	{ route: ["List", "Report"], ar: "التقارير", en: "Reports", icon: "chart" },
];

function isArabic() {
	const lang = String(frappe.boot?.lang || document.documentElement.lang || "").toLowerCase();
	return document.documentElement.dir === "rtl" || lang.startsWith("ar");
}

function allowedActions() {
	const permitted = frappe.boot?.user?.can_create;
	const canCreate = new Set(Array.isArray(permitted) ? permitted : []);
	// Reports is a navigation shortcut, not a document-creation action.
	return ACTIONS.filter(({ doctype, route }) => route || (doctype && canCreate.has(doctype)));
}

const ICONS = {
	invoice:
		'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
		'<path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M8 9h2"/>',
	briefcase:
		'<rect x="3" y="7" width="18" height="14" rx="2"/>' +
		'<path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' +
		'<path d="M3 12h18"/><path d="M10 12v2h4v-2"/>',
	"credit-card":
		'<rect x="2" y="5" width="20" height="14" rx="2"/>' +
		'<path d="M2 10h20"/><path d="M6 15h4"/>',
	user:
		'<circle cx="12" cy="8" r="4"/>' +
		'<path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
	package:
		'<path d="m12 3 9 5-9 5-9-5 9-5Z"/>' +
		'<path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/><path d="m7.5 5.5 9 5"/>',
	ledger:
		'<path d="M6 3h13a2 2 0 0 1 2 2v16H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Z"/>' +
		'<path d="M6 3v18"/><path d="M10 8h7"/><path d="M10 12h7"/><path d="M10 16h5"/>',
	chart:
		'<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6" rx=".5"/>' +
		'<rect x="13" y="8" width="3" height="10" rx=".5"/><rect x="19" y="5" width="2" height="13" rx=".5"/>',
};

function iconMarkup(name, className) {
	const drawing = ICONS[name] || ICONS.invoice;
	return (
		'<svg class="' + className + '" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
		drawing +
		'</svg>'
	);
}

function enableHorizontalMotion(viewport, track) {
	// This component explicitly requires visible motion; scrollLeft is avoided
	// because its RTL semantics vary by browser. Animation pauses on interaction.
	const speed = 18; // balanced, continuous movement in pixels per second
	const rtl = getComputedStyle(viewport).direction === "rtl";
	let offset = 0;
	let direction = 1;
	let previousTime = 0;
	let focusInside = false;
	let frameId = 0;

	viewport.dataset.motionState = "running";
	track.style.willChange = "transform";

	const tick = (time) => {
		if (!viewport.isConnected || !track.isConnected) {
			cancelAnimationFrame(frameId);
			track.style.willChange = "";
			return;
		}

		const overflow = Math.max(0, track.scrollWidth - viewport.clientWidth);
		if (overflow > 1 && !focusInside && document.visibilityState !== "hidden") {
			const elapsed = previousTime ? Math.min((time - previousTime) / 1000, 0.05) : 0;
			offset += direction * speed * elapsed;

			if (offset >= overflow) {
				offset = overflow;
				direction = -1;
			} else if (offset <= 0) {
				offset = 0;
				direction = 1;
			}

			// Transform the content track itself instead of relying on RTL-dependent
			// scrollLeft semantics, which differ across browser engines.
			const translateX = rtl ? offset : -offset;
			track.style.transform = "translate3d(" + translateX.toFixed(2) + "px, 0, 0)";
		}
		previousTime = time;
		frameId = requestAnimationFrame(tick);
	};

	viewport.addEventListener("focusin", () => {
		focusInside = true;
		previousTime = 0;
	});
	viewport.addEventListener("focusout", (event) => {
		focusInside = viewport.contains(event.relatedTarget);
		previousTime = 0;
	});

	frameId = requestAnimationFrame(tick);
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

	const track = document.createElement("div");
	track.className = "amt-quick-actions-track";

	for (const action of actions) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "amt-quick-action";
		if (action.doctype) button.dataset.doctype = action.doctype;
		button.setAttribute("aria-label", action[arabic ? "ar" : "en"]);

		const icon = document.createElement("span");
		icon.className = "amt-quick-action-icon";
		icon.innerHTML = iconMarkup(action.icon, "amt-quick-action-glyph");

		const label = document.createElement("span");
		label.className = "amt-quick-action-label";
		label.textContent = action[arabic ? "ar" : "en"];

		button.append(icon, label);
		button.addEventListener("click", () => {
			if (action.route) {
				if (typeof frappe.set_route === "function") frappe.set_route(action.route);
				return;
			}

			// Re-check the boot permission before opening the native form flow.
			const permitted = frappe.boot?.user?.can_create;
			if (!Array.isArray(permitted) || !permitted.includes(action.doctype)) return;
			if (typeof frappe.new_doc === "function") frappe.new_doc(action.doctype);
		});
		track.appendChild(button);
	}

	if (actions.length) {
		grid.appendChild(track);
		section.append(header, grid);
		enableHorizontalMotion(grid, track);
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
