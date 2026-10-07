/**
 * Desk launcher enhancement.
 *
 * Frappe renders each app tile with a finished raster-ish <img class="app-icon">
 * (a coloured squircle). The target design needs a bare line glyph tinted per
 * business domain, and CSS cannot recolour the inside of an <img>. So the glyph
 * is swapped for an <svg><use> that points at the Lucide sprite Frappe ALREADY
 * inlines into the desk document (~1,780 symbols). No icon library is added.
 *
 * Everything visual is done in SCSS; this module only supplies the two facts
 * CSS cannot derive on its own:
 *   1. which Lucide symbol belongs to a module
 *   2. that the swap has happened (so it is never repeated)
 *
 * Colour is NOT set here — the stylesheet keys `--amt-accent` off `data-id`,
 * which keeps the palette in one reviewable place.
 *
 * Safety properties:
 *   • idempotent — a tile is marked and skipped on re-run
 *   • additive   — no Frappe listener, route or data is touched
 *   • inert      — if the sprite or a symbol is missing, the original artwork
 *                  is left exactly as Frappe drew it
 */

// Exported so the sidebar module badge (core/workspace_enhance.js) resolves a
// workspace to the SAME Lucide glyph this launcher puts on its tile — one map,
// so the two surfaces can never drift apart.
export const MODULE_ICONS = {
	Accounting: "calculator",
	Selling: "store",
	Buying: "tag",
	Stock: "package",
	Manufacturing: "factory",
	Projects: "kanban",
	Quality: "shield-check",
	Assets: "layers",
	Subcontracting: "refresh-cw",
	Approvals: "circle-check-big",
	POSNext: "monitor",
	Framework: "box",
	"ERPNext Settings": "settings",
	Payments: "credit-card",
	"Financial Reports": "chart-column",
	"Accounts Setup": "sliders-horizontal",
	Taxes: "receipt",
	Banking: "landmark",
	Budget: "wallet",
	Subscription: "repeat",
	"Share Management": "chart-pie",
	Users: "users",
	Website: "globe",
	Build: "hammer",
	Automation: "workflow",
	Data: "database",
	Email: "mail",
	Integrations: "plug",
	Printing: "printer",
	System: "server",
	Invoicing: "file-text",
	Organization: "building-2",
	HR: "user-round",
	"Human Resources": "user-round",
	// ndserp's Arabic sections. `data-id` is the workspace name, which is
	// authored in Arabic and never translated, so the key has to be the Arabic
	// string — see the note on $amt-modules in abstracts/_modules.scss.
	"الملفات الرئيسية NDS ERP": "folder-cog",
	"حسابات NDS ERP": "calculator",
	"مخازن NDS ERP": "warehouse",
	"المبيعات NDS ERP": "store",
	"المشتريات NDS ERP": "tag",
	"الاصول NDS ERP": "layers",
};

export const FALLBACK_ICON = "layout-grid";
import { onDeskReady } from "./desk_host.js";

const SVG_NS = "http://www.w3.org/2000/svg";

/** A symbol only renders if it exists in the inlined sprite. */
function symbolExists(name) {
	return !!document.getElementById(`icon-${name}`);
}

/** A glyph chosen for THIS module specifically, or null. Never the fallback. */
function pickSpecificIcon(tile) {
	const byId = MODULE_ICONS[tile.dataset.id];
	if (byId && symbolExists(byId)) return byId;

	// Frappe's own icon name is a decent second guess before the generic one.
	const byFrappe = tile.dataset.icon;
	if (byFrappe && symbolExists(byFrappe)) return byFrappe;

	return null;
}

function pickIcon(tile) {
	return pickSpecificIcon(tile) || (symbolExists(FALLBACK_ICON) ? FALLBACK_ICON : null);
}

/** True when the site owner uploaded artwork for this tile themselves. */
function hasUploadedArtwork(label) {
	try {
		return !!frappe.utils.get_desktop_icon_by_label(label)?.icon_image;
	} catch (e) {
		return false;
	}
}

function decorate(tile) {
	if (tile.dataset.amtGlyph) return; // already done

	const box = tile.querySelector(":scope > .icon-container");
	if (!box || box.classList.contains("folder-icon")) return; // folders keep their preview

	// An explicit `icon_image` upload is a deliberate branding choice — never
	// replace it with a stock glyph. Marked (not left bare) so the CSS that
	// hides Frappe's <img> can make an exception for exactly these tiles.
	if (hasUploadedArtwork(tile.dataset.id)) {
		tile.dataset.amtGlyph = "custom";
		return;
	}

	if (!box.querySelector("img.app-icon")) {
		// No shipped artwork: Frappe draws a letter avatar from alphabets.svg,
		// which only has Latin glyphs — an Arabic-titled workspace therefore
		// renders an EMPTY coloured square. So if a module-specific glyph is
		// available, draw that instead and let CSS hide the letter.
		//
		// A tile with no specific glyph keeps the letter avatar: for a Latin app
		// (POSNext -> "P") the initial is the only thing distinguishing it, and
		// swapping it for the generic fallback would lose that.
		if (!pickSpecificIcon(tile)) {
			tile.dataset.amtLetter = "1";
			return;
		}
		tile.dataset.amtGlyphOverLetter = "1";
	}

	const name = pickIcon(tile);
	if (!name) return; // sprite unavailable — leave Frappe's artwork untouched

	const svg = document.createElementNS(SVG_NS, "svg");
	svg.setAttribute("class", "amt-tile-glyph");
	svg.setAttribute("viewBox", "0 0 24 24");
	svg.setAttribute("aria-hidden", "true");
	svg.setAttribute("focusable", "false");

	const use = document.createElementNS(SVG_NS, "use");
	// Same-document reference; a cross-file `href="sprite.svg#id"` is blocked
	// by most browsers, which is why the inlined sprite matters.
	use.setAttribute("href", `#icon-${name}`);
	svg.appendChild(use);

	box.appendChild(svg);
	tile.dataset.amtGlyph = name;
}

function run() {
	const tiles = document.querySelectorAll(
		".desktop-container > .icons-container > .icons > .desktop-icon"
	);
	tiles.forEach(decorate);
	return tiles.length;
}


export const deskLauncher = {
	mount() {
		// Host lifecycle (waiting, observing, coalescing) is owned by desk_host.
		onDeskReady(run);
	},
};
