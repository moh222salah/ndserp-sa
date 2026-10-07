/**
 * Color-scheme switcher.
 *
 * Adds a palette button to the rail (next to the language toggle) that opens a
 * popover with four ready schemes plus a custom picker. A scheme only re-points
 * the brand tokens (see themes/_color-schemes.scss) via a `data-amt-scheme`
 * attribute on <html>; working surfaces stay neutral so reports/documents keep
 * their legibility. The choice is persisted per-browser in localStorage and
 * re-applied as early as the bundle loads, so there is no default-color flash.
 */

const STORAGE_KEY = "amt-color-scheme";
const CUSTOM_KEY = "amt-custom-colors";

// Preview swatches mirror the SCSS values so the popover reads true.
const SCHEMES = [
	{ id: "default", ar: "الأزرق الكلاسيكي", en: "Classic Blue",
	  descAr: "الوضع الافتراضي الحالي", descEn: "The current default",
	  primary: "#14477E", gold: "#C9A227", rail: "#0B1120" },
	{ id: "olive", ar: "الزيتوني الفاخر", en: "Luxe Olive",
	  descAr: "زيتوني هادئ بلمسة نحاسية", descEn: "Calm olive, brass accent",
	  primary: "#556B2E", gold: "#B08D3A", rail: "#151A0E" },
	{ id: "oak", ar: "البلوطي الداكن", en: "Dark Oak",
	  descAr: "بنّي دافئ برونزي", descEn: "Warm oak, bronze accent",
	  primary: "#6E4C30", gold: "#B5872F", rail: "#17110A" },
	{ id: "royal", ar: "الأحمر الملكي", en: "Royal Red",
	  descAr: "عنّابي ملكي وذهبي", descEn: "Royal burgundy, gold accent",
	  primary: "#8C2334", gold: "#C9A22C", rail: "#190A0E" },
];

// The three channels the custom picker exposes, each with a plain-language note
// so the user knows exactly what a colour drives.
const CUSTOM_FIELDS = [
	{ key: "primary", def: "#14477E", ar: "اللون الأساسي (العلامة)", en: "Primary (brand)",
	  descAr: "الأزرار والروابط والعناصر النشطة", descEn: "Buttons, links, active items" },
	{ key: "gold", def: "#C9A227", ar: "لون اللمسة المعدنية", en: "Metallic accent",
	  descAr: "التمييز الذهبي والفواصل الفاخرة", descEn: "Gold highlights & flourishes" },
	{ key: "rail", def: "#0B1120", ar: "خلفية الشريط الجانبي", en: "Sidebar rail background",
	  descAr: "خلفية شريط الأيقونات الداكن", descEn: "The dark icon-rail background" },
];

const isRtl = () => document.documentElement.getAttribute("dir") === "rtl";
const L = (ar, en) => (isRtl() ? ar : en);

/** Lighten a #rrggbb toward white by `amt` (0..1) — used for the rail border. */
function lighten(hex, amt) {
	const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
	if (!m) return hex;
	const n = parseInt(m[1], 16);
	const mix = (c) => Math.round(c + (255 - c) * amt);
	const r = mix((n >> 16) & 255), g = mix((n >> 8) & 255), b = mix(n & 255);
	return "#" + [r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function readCustom() {
	try { return JSON.parse(localStorage.getItem(CUSTOM_KEY) || "null"); } catch (e) { return null; }
}

/** Apply a scheme id (+ custom colours) to <html>. Pure DOM, no persistence. */
function apply(id, custom) {
	const root = document.documentElement;
	if (id === "default") root.removeAttribute("data-amt-scheme");
	else root.setAttribute("data-amt-scheme", id);

	// Custom channels live as inline vars the SCSS `custom` scheme reads.
	if (id === "custom") {
		const c = custom || readCustom() || {};
		const set = (k, v) => v && root.style.setProperty(k, v);
		set("--amt-custom-primary", c.primary);
		set("--amt-custom-gold", c.gold);
		set("--amt-custom-rail-bg", c.rail);
		if (c.rail) root.style.setProperty("--amt-custom-rail-border", lighten(c.rail, 0.14));
	}
}

/** Re-apply the saved scheme as soon as the bundle loads (avoids a colour flash). */
function applyEarly() {
	try { apply(localStorage.getItem(STORAGE_KEY) || "default", readCustom()); } catch (e) { /* ignore */ }
}

function save(id, custom) {
	try {
		localStorage.setItem(STORAGE_KEY, id);
		if (custom) localStorage.setItem(CUSTOM_KEY, JSON.stringify(custom));
	} catch (e) { /* private mode — still apply for the session */ }
	apply(id, custom);
}

const PALETTE_SVG =
	'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
	'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
	'<circle cx="13.5" cy="6.5" r="1.2"></circle><circle cx="17.5" cy="10.5" r="1.2"></circle>' +
	'<circle cx="8.5" cy="7.5" r="1.2"></circle><circle cx="6.5" cy="12.5" r="1.2"></circle>' +
	'<path d="M12 2a10 10 0 1 0 0 20 2.5 2.5 0 0 0 2-4 2.5 2.5 0 0 1 2-4h1a5 5 0 0 0 5-5 10 10 0 0 0-10-7z"></path></svg>';

let $pop = null;

function buildPopover() {
	const active = localStorage.getItem(STORAGE_KEY) || "default";
	const custom = readCustom() || {};

	const card = (s) => `
		<button type="button" class="amt-cs-card${active === s.id ? " active" : ""}" data-scheme="${s.id}"
			title="${L(s.descAr, s.descEn)}">
			<span class="amt-cs-swatches">
				<i style="background:${s.primary}"></i><i style="background:${s.gold}"></i><i style="background:${s.rail}"></i>
			</span>
			<span class="amt-cs-name">${L(s.ar, s.en)}</span>
			<span class="amt-cs-desc">${L(s.descAr, s.descEn)}</span>
		</button>`;

	const field = (f) => `
		<label class="amt-cs-field">
			<input type="color" data-key="${f.key}" value="${custom[f.key] || f.def}">
			<span class="amt-cs-field-text">
				<span class="amt-cs-field-name">${L(f.ar, f.en)}</span>
				<span class="amt-cs-field-desc">${L(f.descAr, f.descEn)}</span>
			</span>
		</label>`;

	const $p = $(`
		<div class="amt-cs-pop" role="dialog" aria-label="${L("أنظمة الألوان", "Color schemes")}">
			<div class="amt-cs-head">${L("أنظمة الألوان", "Color schemes")}</div>
			<div class="amt-cs-grid">${SCHEMES.map(card).join("")}</div>
			<div class="amt-cs-sep"><span>${L("ألوان مخصّصة", "Custom colors")}</span></div>
			<div class="amt-cs-custom${active === "custom" ? " active" : ""}">
				${CUSTOM_FIELDS.map(field).join("")}
				<button type="button" class="amt-cs-apply">${L("تطبيق الألوان المخصّصة", "Apply custom colors")}</button>
			</div>
		</div>
	`);

	// Preset click → save + refresh active state.
	$p.on("click", ".amt-cs-card", function () {
		const id = $(this).data("scheme");
		save(id, null);
		$p.find(".amt-cs-card").removeClass("active");
		$(this).addClass("active");
		$p.find(".amt-cs-custom").removeClass("active");
	});

	// Custom apply → collect the three inputs, persist, mark custom active.
	$p.on("click", ".amt-cs-apply", function () {
		const c = {};
		$p.find(".amt-cs-field input[type=color]").each(function () {
			c[$(this).data("key")] = this.value;
		});
		save("custom", c);
		$p.find(".amt-cs-card").removeClass("active");
		$p.find(".amt-cs-custom").addClass("active");
	});

	return $p;
}

function positionPopover($btn) {
	const r = $btn[0].getBoundingClientRect();
	const w = $pop.outerWidth(), h = $pop.outerHeight();
	const gap = 12;
	// Rail sits on the right in RTL (open to its left) and left in LTR.
	let left = isRtl() ? r.left - w - gap : r.right + gap;
	left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
	let top = r.top + r.height / 2 - h / 2;
	top = Math.max(8, Math.min(top, window.innerHeight - h - 8));
	$pop.css({ top: top + "px", left: left + "px" });
}

function togglePopover($btn) {
	if ($pop && $pop.hasClass("open")) { closePopover(); return; }
	if (!$pop) { $pop = buildPopover().appendTo("body"); }
	$pop.addClass("open");
	positionPopover($btn);
	$btn.addClass("active");
	setTimeout(() => $(document).on("mousedown.amtcs", (e) => {
		if (!$(e.target).closest(".amt-cs-pop, .amt-rail-scheme").length) closePopover();
	}), 0);
	$(document).on("keydown.amtcs", (e) => { if (e.key === "Escape") closePopover(); });
}

function closePopover() {
	if ($pop) $pop.removeClass("open");
	$(".amt-rail-scheme").removeClass("active");
	$(document).off("mousedown.amtcs keydown.amtcs");
}

/** Inject the palette button into the rail bottom, just before the language toggle. */
function attach($rail) {
	if (!$rail || !$rail.length) return;
	const $bottom = $rail.find(".amt-rail-bottom");
	if (!$bottom.length || $bottom.find(".amt-rail-scheme").length) return;

	const $btn = $(
		`<div class="amt-rail-scheme" title="${L("أنظمة الألوان", "Color schemes")}" tabindex="0">` +
			`${PALETTE_SVG}<span class="amt-rail-scheme-label">C-Style</span></div>`
	);
	// Anchor on the language toggle when it is on the rail, otherwise on the
	// expand/collapse control. The language toggle is optional now — "Amir
	// Theme Settings → Language Switcher Position" can move it to the navbar or
	// hide it — and `.before()` on an empty set is a silent no-op, which would
	// have made this button vanish along with it. `.amt-rail-toggle` is always
	// rendered, so it is the reliable fallback.
	const $anchor = $bottom.find(".amt-rail-lang, .amt-rail-toggle").first();
	$anchor.length ? $anchor.before($btn) : $bottom.append($btn);
	$btn.on("click", (e) => { e.stopPropagation(); togglePopover($btn); });
	$btn.on("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); togglePopover($btn); } });
}

export const colorScheme = { applyEarly, attach };
