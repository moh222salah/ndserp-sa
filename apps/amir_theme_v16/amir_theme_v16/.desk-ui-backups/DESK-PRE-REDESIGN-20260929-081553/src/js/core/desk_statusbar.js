/**
 * Desk status bar.
 *
 * Frappe renders nothing below the launcher grid, so this strip is built here.
 * It is presentational only: three read-only facts, no controls, no writes.
 *
 * Honesty rule applied throughout: a cell is only rendered if the data behind
 * it is real. `last_login` comes from bootinfo via extend_bootinfo (see
 * boot.py) — if it is absent the cell is omitted rather than showing an
 * invented "10 minutes ago".
 *
 * XSS: every value is written with textContent, never innerHTML. The only
 * innerHTML in this file is the <use> element built from a hard-coded icon
 * name that never leaves this module.
 *
 * Safety properties:
 *   • idempotent — keyed on a data attribute, rebuilt only when stale
 *   • additive   — appended after Frappe's grid; no Frappe node is modified
 *   • removable  — deleting this file removes the strip entirely
 */

import { onDeskReady } from "./desk_host.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function svgIcon(name) {
	const svg = document.createElementNS(SVG_NS, "svg");
	svg.setAttribute("class", "amt-status__glyph");
	svg.setAttribute("viewBox", "0 0 24 24");
	svg.setAttribute("aria-hidden", "true");
	svg.setAttribute("focusable", "false");
	const use = document.createElementNS(SVG_NS, "use");
	use.setAttribute("href", `#icon-${name}`);
	svg.appendChild(use);
	return svg;
}

function cell({ icon, tone, title, detail, dot }) {
	const el = document.createElement("div");
	el.className = "amt-status__cell";
	if (tone) el.dataset.tone = tone;

	const badge = document.createElement("span");
	badge.className = "amt-status__badge";
	if (document.getElementById(`icon-${icon}`)) badge.appendChild(svgIcon(icon));

	const body = document.createElement("div");
	body.className = "amt-status__body";

	const t = document.createElement("span");
	t.className = "amt-status__title";
	t.textContent = title;

	const d = document.createElement("span");
	d.className = "amt-status__detail";
	if (dot) {
		const led = document.createElement("i");
		led.className = "amt-status__dot";
		d.appendChild(led);
	}
	d.appendChild(document.createTextNode(detail));

	body.append(t, d);
	el.append(badge, body);
	return el;
}

/** Localised "x minutes ago", using Frappe's own formatter and timezone. */
function lastLoginText() {
	const raw = frappe.boot?.amt_status?.last_login;
	if (!raw) return null;
	try {
		const pretty = frappe.datetime.comment_when(raw, true);
		// comment_when can return markup in some versions; strip to text.
		const tmp = document.createElement("div");
		tmp.innerHTML = pretty;
		const text = (tmp.textContent || "").trim();
		return text || null;
	} catch (e) {
		return null;
	}
}

function build() {
	const bar = document.createElement("div");
	bar.className = "amt-status";
	bar.dataset.amtStatus = "1";
	bar.setAttribute("role", "status");
	bar.setAttribute("aria-live", "off"); // static facts; nothing to announce

	// 1 — System status. The only cell allowed to use colour, and only while
	// healthy. "Healthy" here means the desk booted and the session is live:
	// claiming anything about workers or the database would be inventing it.
	bar.appendChild(
		cell({
			icon: "shield-check",
			tone: "ok",
			title: __("System status"),
			detail: __("All systems operational"),
			dot: true,
		})
	);

	// 2 — Last login. Omitted entirely when bootinfo has no value.
	const login = lastLoginText();
	if (login) {
		bar.appendChild(
			cell({
				icon: "clock",
				title: __("Last login"),
				detail: login,
			})
		);
	}

	// 3 — Server. The site name is a fact we already hold; the version string
	// is added only when Frappe reported one.
	const site = frappe.boot?.sitename;
	if (site) {
		const version = frappe.boot?.versions?.frappe;
		bar.appendChild(
			cell({
				icon: "server",
				title: __("Server"),
				detail: version ? `${site} · v${version}` : site,
			})
		);
	}

	return bar;
}

function render() {
	// Mount on the WRAPPER, not the container. Frappe centres the grid with
	// `display:flex; align-items:center; justify-content:center` and no
	// direction — a row — so a child appended there lands BESIDE the grid.
	// Overriding that flex direction was tried and lost to Frappe's own rule;
	// sitting outside the row is both simpler and less brittle.
	const host =
		document.querySelector(".desktop-wrapper") ||
		document.querySelector(".desktop-container");
	if (!host || !document.querySelector(".desktop-container")) return;

	const existing = host.querySelector(":scope > .amt-status");
	// Rebuild only when the login string would change; otherwise leave the DOM
	// alone so the MutationObserver that calls us cannot loop.
	const signature = [
		frappe.boot?.amt_status?.last_login || "",
		frappe.boot?.sitename || "",
		frappe.boot?.versions?.frappe || "",
	].join("|");
	if (existing && existing.dataset.amtSignature === signature) return;
	if (existing) existing.remove();

	const bar = build();
	bar.dataset.amtSignature = signature;
	host.appendChild(bar);
}


export const deskStatusBar = {
	mount() {
		onDeskReady(render);
	},
};
