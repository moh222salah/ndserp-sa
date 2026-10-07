/*
 * VA System — Desk Quick Actions
 * Presentation/navigation layer only.
 * No authentication, permission or server logic changes.
 */

import { onDeskReady } from "./desk_host.js";

const ICONS = {
sales: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h16v13H4z"/><path d="M8 9h8M8 13h5M8 16h3"/></svg>',
purchase: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h17v11h-17z"/><path d="M7 6.5v-2h10v2M8 11h8M8 15h5"/></svg>',
payment: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 9h17M7 14h3"/></svg>',
customer: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 19c.8-3.5 3-5.2 6.5-5.2s5.7 1.7 6.5 5.2"/></svg>',
stock: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 8 4.3v9.4L12 21l-8-4.3V7.3z"/><path d="m4.3 7.4 7.7 4.1 7.7-4.1M12 11.5V21"/></svg>',
journal: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4.5h12v15H6z"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
reports: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19V9M12 19V5M19 19v-7"/><path d="M3.5 19.5h17"/></svg>',
arrow: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>'
};

const ACTIONS = [
{
key: "sales",
label: { ar: "فاتورة مبيعات", en: "Sales Invoice" },
icon: ICONS.sales,
run: () => window.frappe.new_doc("Sales Invoice")
},
{
key: "purchase",
label: { ar: "فاتورة مشتريات", en: "Purchase Invoice" },
icon: ICONS.purchase,
run: () => window.frappe.new_doc("Purchase Invoice")
},
{
key: "payment",
label: { ar: "سند قبض", en: "Receipt Voucher" },
icon: ICONS.payment,
run: () => window.frappe.new_doc("Payment Entry", { payment_type: "Receive" })
},
{
key: "customer",
label: { ar: "عميل جديد", en: "New Customer" },
icon: ICONS.customer,
run: () => window.frappe.new_doc("Customer")
},
{
key: "stock",
label: { ar: "حركة مخزون", en: "Stock Movement" },
icon: ICONS.stock,
run: () => window.frappe.new_doc("Stock Entry")
},
{
key: "journal",
label: { ar: "قيد يومية", en: "Journal Entry" },
icon: ICONS.journal,
run: () => window.frappe.new_doc("Journal Entry")
},
{
key: "reports",
label: { ar: "التقارير", en: "Reports" },
icon: ICONS.reports,
run: () => window.frappe.set_route("List", "Report")
}
];

function vaDeskLanguage() {
return (window.frappe?.boot?.lang || document.documentElement.lang || "en").toLowerCase();
}

function vaIsArabic() {
return vaDeskLanguage().startsWith("ar");
}

function vaLocalizedText(value) {
if (typeof value === "string") {
return value;
}

return vaIsArabic() ? value.ar : value.en;
}

function createAction(action) {
const button = document.createElement("button");
const label = vaLocalizedText(action.label);

button.type = "button";
button.className = "amt-quick-action";
button.dataset.action = action.key;
button.setAttribute("aria-label", label);
button.title = label;

button.innerHTML = `
<span class="amt-quick-action-icon">${action.icon}</span>
<span class="amt-quick-action-label">${label}</span>
<span class="amt-quick-action-arrow">${ICONS.arrow}</span>
`;

button.addEventListener("click", () => {
try {
action.run();
} catch (error) {
console.error("[amir_theme] quick action failed:", action.key, error);
}
});

return button;
}

function mountQuickActions() {
const container = document.querySelector(".desktop-container");
const icons = container?.querySelector(".icons-container > .icons");
const iconsContainer = icons?.closest(".icons-container");

if (!container || !icons || !iconsContainer || container.querySelector(".amt-quick-actions")) {
return;
}

const section = document.createElement("section");
section.className = "amt-quick-actions";
section.setAttribute("aria-labelledby", "amt-quick-actions-title");

const title = vaLocalizedText({
ar: "الإجراءات السريعة",
en: "Quick Actions"
});

section.innerHTML = `
<div class="amt-quick-actions-header">
<h2 id="amt-quick-actions-title" class="amt-quick-actions-title">${title}</h2>
<span class="amt-quick-actions-rule" aria-hidden="true"></span>
</div>
<div class="amt-quick-actions-grid"></div>
`;

const grid = section.querySelector(".amt-quick-actions-grid");

ACTIONS.forEach((action) => {
grid.appendChild(createAction(action));
});

iconsContainer.after(section);
}

onDeskReady(mountQuickActions);
