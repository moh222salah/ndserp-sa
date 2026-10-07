// =====================================================================
// Dual Gregorian + Hijri dates
// =====================================================================
// Every Date and Datetime field shows its value in both calendars: the
// Gregorian value stays authoritative (the input, the save, the DB are
// never touched), and the Umm-al-Qura Hijri equivalent is added as a
// read-only companion — a small caption under the field and a second
// number in every calendar cell.
//
// How it hooks Frappe (v16.17, air-datepicker v2):
//   • ControlDate.prototype.set_date_options builds `datepicker_options`.
//     We compose (never replace) its `onRenderCell` so each cell renders
//     both numbers, and its nav events so the popup header carries the
//     Hijri month/year. ControlDatetime inherits this through super().
//   • The field caption is driven by `refresh_input`, the one hook the
//     framework calls for BOTH Date and Datetime on every value change —
//     Datetime overrides set_formatted_input without calling super, so
//     refresh_input is the only universal seam.
//
// Why this is safe for the Child Table grid (see the grid-trap memory):
//   • The datepicker popup is body-appended and absolutely positioned —
//     styling or augmenting it cannot trap the position:fixed row editor.
//   • The caption is a sibling inside `.control-input`; it is explicitly
//     skipped inside compact grid cells so it never alters row geometry.
//   • Every DOM write is textContent or a numeric string — no innerHTML
//     of user data, nothing that can throw back into Frappe.
//
// Correctness notes worth keeping:
//   • Umm-al-Qura comes from Intl (`islamic-umalqura`) — no hand-rolled
//     offset table to drift out of date.
//   • air-datepicker updates `currentDate` AFTER firing a nav event, so
//     the header is synced on the next animation frame when it is fresh.
//   • A Gregorian month spans two Hijri months; the days-view header shows
//     the range when the first and last day fall in different ones.
// =====================================================================

const HIJRI = "-u-ca-islamic-umalqura";

function uiLang() {
	return (document.documentElement.getAttribute("lang") || "en")
		.toLowerCase()
		.startsWith("ar")
		? "ar"
		: "en";
}

// One cache for every Intl.DateTimeFormat. The reference implementation
// built a fresh formatter for each month cell (12 allocations per render);
// these are keyed and reused for the life of the page.
const _fmt = Object.create(null);
function fmt(key, locale, opts) {
	const k = key + "|" + locale;
	return (_fmt[k] || (_fmt[k] = new Intl.DateTimeFormat(locale, opts)));
}

// Locale policy: Arabic MONTH NAMES with WESTERN NUMERALS. The `-nu-latn`
// numbering override keeps "صفر / ربيع الأول" while rendering the day and year
// as 7 / 1448 rather than ٧ / ١٤٤٨. This is the convention Gulf official
// documents use, and it matters here for two concrete reasons: the Hijri digit
// then aligns with the Latin Gregorian digit stacked above it in each cell, and
// a two-digit day stays the same width whether it is ٩→١٠ or 9→10. Which system
// each number belongs to is carried by an explicit م / هـ marker, not by its
// script, so the numerals are free to be uniform. English is already Latin.
function hijriLoc() {
	return uiLang() === "ar"
		? "ar-SA-u-ca-islamic-umalqura-nu-latn"
		: "en-US" + HIJRI;
}

// System markers shown before each DAY number so Gregorian vs Hijri is never
// ambiguous. Written with the trailing kashida — مـ (ميلادي) / هـ (هجري) — so
// each reads as a proper era abbreviation, matching how هـ conventionally marks
// a Hijri year. G / H in English.
function marks() {
	return uiLang() === "ar" ? { g: "مـ", h: "هـ" } : { g: "G", h: "H" };
}

function hijriDayNum(d) {
	// Day only — no era in a grid of 42 cells.
	return fmt("h-day", hijriLoc(), { day: "numeric" }).format(d);
}
function hijriMonthName(d) {
	return fmt("h-mon", hijriLoc(), { month: "long" }).format(d);
}
function gregShortMonth(d) {
	return fmt("g-mon", uiLang() === "ar" ? "ar" : "en", { month: "short" }).format(d);
}

// Intl always attaches the era to a non-Gregorian year, even for year-only
// output, and it does so in the locale's own script. Split the parts so the
// era can be placed exactly once — on a single year and at the end of a span —
// instead of "1447 AH–1448 AH".
function hijriYearParts(d) {
	const parts = fmt("h-year", hijriLoc(), { year: "numeric" }).formatToParts(d);
	return {
		y: (parts.find((p) => p.type === "year") || {}).value || "",
		era: (parts.find((p) => p.type === "era") || {}).value || "",
	};
}
function hijriYearCell(d) {
	const { y, era } = hijriYearParts(d);
	return era ? y + " " + era : y;
}

// A Gregorian year straddles two Hijri years — show the span for a single
// year cell and for the year/decade nav header, with the era written once.
function hijriYearSpan(gYearStart, gYearEnd) {
	const a = hijriYearParts(new Date(gYearStart, 0, 15));
	const b = hijriYearParts(new Date(gYearEnd, 11, 15));
	const tail = b.era ? " " + b.era : "";
	return a.y === b.y ? a.y + tail : a.y + "–" + b.y + tail;
}

// Days-view header. If the displayed Gregorian month opens in one Hijri
// month and closes in the next, name both; the era (هـ / AH) rides along
// from Intl's month+year format on the closing month.
function hijriHeaderForMonth(d) {
	const y = d.getFullYear();
	const m = d.getMonth();
	const first = new Date(y, m, 1);
	const last = new Date(y, m + 1, 0);
	const withEra = fmt("h-my", hijriLoc(), { month: "long", year: "numeric" });
	if (hijriMonthName(first) === hijriMonthName(last)) {
		return withEra.format(new Date(y, m, 15));
	}
	return hijriMonthName(first) + " – " + withEra.format(last);
}

function hijriFull(d) {
	return fmt("h-full", hijriLoc(), {
		day: "numeric",
		month: "long",
		year: "numeric",
	}).format(d);
}

// ---------------------------------------------------------------------
// Calendar cells — compose air-datepicker's onRenderCell
// ---------------------------------------------------------------------
function cellHtml(g, h, type) {
	// Markers earn their place only on the day grid, where both figures are bare
	// numbers. In the month view the names tell the calendars apart (يناير vs
	// رجب), and in the year view the Hijri era already labels it (1440 هـ) — a
	// marker there would either read as one word or double the era.
	if (type === "day") {
		const mk = marks();
		return (
			'<span class="amt-dc amt-dc--day">' +
			'<span class="amt-dc-g"><i class="amt-dc-mk">' + mk.g + "</i>" + g + "</span>" +
			(h ? '<span class="amt-dc-h"><i class="amt-dc-mk">' + mk.h + "</i>" + h + "</span>" : "") +
			"</span>"
		);
	}
	return (
		'<span class="amt-dc amt-dc--' + type + '">' +
		'<span class="amt-dc-g">' + g + "</span>" +
		(h ? '<span class="amt-dc-h">' + h + "</span>" : "") +
		"</span>"
	);
}

function enhanceOptions(ctrl) {
	const o = ctrl.datepicker_options;
	if (!o) return;

	const prevRender = o.onRenderCell;
	o.onRenderCell = (date, cellType) => {
		let base;
		try {
			base = prevRender ? prevRender(date, cellType) : undefined;
		} catch (e) {
			base = undefined;
		}
		if (date instanceof Date) {
			let g = "", h = "";
			if (cellType === "day") {
				g = date.getDate();
				h = hijriDayNum(date);
			} else if (cellType === "month") {
				g = gregShortMonth(date);
				h = hijriMonthName(date);
			} else if (cellType === "year") {
				g = date.getFullYear();
				h = hijriYearCell(date);
			}
			if (g !== "") {
				const html = cellHtml(g, h, cellType);
				return base && typeof base === "object" ? { ...base, html } : { html };
			}
		}
		return base;
	};

	// Keep the popup header's Hijri line correct on EVERY navigation path.
	// The reference only hooked onChangeMonth, so the header went stale the
	// moment the user jumped by year, decade, or view.
	const syncOnAllNav = ["onShow", "onChangeMonth", "onChangeYear", "onChangeDecade", "onChangeView"];
	for (const name of syncOnAllNav) {
		const prev = o[name];
		o[name] = (...args) => {
			try {
				if (prev) prev.apply(ctrl, args);
			} catch (e) {}
			scheduleHeader(ctrl.datepicker);
		};
	}
}

function syncHeader(dp) {
	const $dp = dp && dp.$datepicker;
	if (!$dp || !$dp[0]) return;
	const nav = $dp[0].querySelector(".datepicker--nav-title");
	if (!nav) return;

	const view = dp.currentView;
	const cur = dp.currentDate instanceof Date ? dp.currentDate : new Date();
	let label = "";
	if (view === "days") {
		label = hijriHeaderForMonth(cur);
	} else if (view === "months") {
		label = hijriYearSpan(cur.getFullYear(), cur.getFullYear());
	} else if (view === "years") {
		const start = Math.floor(cur.getFullYear() / 10) * 10;
		label = hijriYearSpan(start, start + 9);
	}

	const sig = view + "|" + label;
	let sub = nav.querySelector(".amt-dp-hijri");
	// air-datepicker rewrites the nav title on navigation, wiping our node;
	// the signature guard makes the re-append idempotent and loop-free.
	if (sub && sub.dataset.sig === sig) return;
	if (!sub) {
		sub = document.createElement("span");
		sub.className = "amt-dp-hijri";
		nav.appendChild(sub);
	}
	sub.textContent = label;
	sub.dataset.sig = sig;
}

// currentDate is only fresh after the nav method returns; rAF also coalesces
// a burst of events (view change + month change) into a single header write.
function scheduleHeader(dp) {
	if (!dp || dp.__amtHdrQueued) return;
	dp.__amtHdrQueued = true;
	requestAnimationFrame(() => {
		dp.__amtHdrQueued = false;
		try {
			syncHeader(dp);
		} catch (e) {}
	});
}

// ---------------------------------------------------------------------
// Field caption — the Hijri equivalent of the field's value
// ---------------------------------------------------------------------
function getDate(ctrl) {
	try {
		// The field VALUE is authoritative and must be read first. The
		// datepicker's `selectedDates` is only a UI cache and lags behind a
		// programmatic change — set_value, a fetch, a formula (e.g. due_date =
		// posting_date + 30) — so preferring it froze the caption on the old
		// date even across a refresh. It is used only as a last-resort fallback.
		const v = ctrl.get_value && ctrl.get_value();
		if (v) {
			// Parse yyyy-mm-dd as a LOCAL date so a behind-UTC timezone can't
			// shift a pure Date back a day; str_to_obj handles Datetime + time.
			let m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
			if (m) {
				return new Date(
					+m[1], +m[2] - 1, +m[3],
					+(m[4] || 0), +(m[5] || 0), +(m[6] || 0)
				);
			}
			if (frappe.datetime && frappe.datetime.str_to_obj) {
				const d = frappe.datetime.str_to_obj(v);
				if (d && !isNaN(d.getTime())) return d;
			}
			m = String(v).match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/);
			if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
		}
		const sel = ctrl.datepicker && ctrl.datepicker.selectedDates;
		if (sel && sel[0] instanceof Date) return sel[0];
	} catch (e) {}
	return null;
}

const _capQueued = new WeakSet();
function scheduleCaption(ctrl) {
	// set_formatted_input and refresh_input can both fire for one change;
	// coalesce to one DOM pass per frame per control.
	if (_capQueued.has(ctrl)) return;
	_capQueued.add(ctrl);
	requestAnimationFrame(() => {
		_capQueued.delete(ctrl);
		updateCaption(ctrl);
	});
}

function updateCaption(ctrl) {
	try {
		if (!ctrl || !ctrl.$wrapper || !ctrl.$wrapper[0]) return;
		const ft = ctrl.df && ctrl.df.fieldtype;
		if (ft !== "Date" && ft !== "Datetime") return;

		const wrap = ctrl.$wrapper[0];
		// The caption belongs on form fields, not on the compact controls of
		// the grid row, the filter bar, or a filter popover — a pill there
		// would clutter a tight strip and could nudge its height. The row-open
		// editor (.grid-row-open) is a normal form, so it is NOT excluded here.
		if (
			wrap.closest(
				".grid-static-col, .standard-filter-section, .filter-section, " +
					".filter-box, .filter-edit-area, .filter-selector"
			)
		)
			return;

		// Mount the caption as a SIBLING of the input box inside
		// .control-input-wrapper — never inside .control-input itself. The theme
		// draws the field-type glyph as `.control-input::before`, vertically
		// centred on that box; a caption placed inside makes the box taller and
		// drags the glyph down, out of the input (the reported misalignment). As
		// a sibling, .control-input keeps the input's own height and the glyph
		// stays centred, while the caption still reads directly under the value.
		const wrapper = wrap.querySelector(".control-input-wrapper");
		const ci = wrap.querySelector(".control-input");
		const host = wrapper || (ci && ci.parentElement);
		if (!host) return;

		const d = getDate(ctrl);
		let cap = host.querySelector(":scope > .amt-hijri-value");
		if (!d) {
			if (cap) {
				cap.textContent = "";
				cap.style.display = "none";
			}
			return;
		}
		const text = hijriFull(d) || "";
		if (!cap) {
			cap = document.createElement("small");
			cap.className = "amt-hijri-value";
			// The input already carries the authoritative value; this is a
			// visual aid, so it is hidden from the accessibility tree.
			cap.setAttribute("aria-hidden", "true");
			// Right after the input box, ahead of control-value / help-box.
			if (ci && ci.parentElement === host) {
				ci.insertAdjacentElement("afterend", cap);
			} else {
				host.appendChild(cap);
			}
		}
		if (cap.textContent !== text) cap.textContent = text;
		cap.style.display = text ? "" : "none";
	} catch (e) {
		// never throw back into Frappe's render path
	}
}

// ---------------------------------------------------------------------
// Prototype patch — applied once, defensively
// ---------------------------------------------------------------------
let patched = false;
function patch() {
	if (patched) return true;
	const CD = window.frappe && frappe.ui && frappe.ui.form && frappe.ui.form.ControlDate;
	if (!CD) return false;
	const proto = CD.prototype;
	if (proto.__amtHijri) return (patched = true);

	const origOpts = proto.set_date_options;
	proto.set_date_options = function (...a) {
		const out = origOpts.apply(this, a);
		try {
			enhanceOptions(this);
		} catch (e) {
			// eslint-disable-next-line no-console
			console.warn("[amir_theme] hijri options", e);
		}
		return out;
	};

	// Date fields update through set_formatted_input (calls super)...
	const origSFI = proto.set_formatted_input;
	if (typeof origSFI === "function") {
		proto.set_formatted_input = function (...a) {
			const out = origSFI.apply(this, a);
			scheduleCaption(this);
			return out;
		};
	}

	// ...Datetime overrides that without super, so refresh_input — inherited
	// from base_input and called by the framework for every control — is the
	// hook that covers BOTH. Reading it here resolves up the prototype chain;
	// assigning shadows it for Date and Datetime alike.
	const origRI = proto.refresh_input;
	if (typeof origRI === "function") {
		proto.refresh_input = function (...a) {
			const out = origRI.apply(this, a);
			scheduleCaption(this);
			return out;
		};
	}

	proto.__amtHijri = true;

	// Marks the document so the calendar-cell skin in _hijri-date.scss can scope
	// itself to "the dual-number renderer is actually running".
	//
	// This is load-bearing, not cosmetic. That skin repaints every cell state
	// onto an inset ::after card, including a SOLID --primary fill for the
	// selected day, and recolours the figures to --amt-dp-on-accent through the
	// .amt-dc-* spans this file injects. With the Hijri feature switched off
	// (Amir Theme Settings) those spans never exist, so the cell holds a bare
	// text node: it would keep the dark --text-color AND paint *underneath* the
	// filled card (a positioned ::after at z-index 0 draws above non-positioned
	// inline text), leaving the selected day as a blank navy square. Scoping the
	// skin to this attribute means "no renderer -> stock air-datepicker styling",
	// which is readable on its own.
	document.documentElement.setAttribute("data-amt-hijri", "");

	return (patched = true);
}

export const hijriDate = {
	mount() {
		if (patch()) return;
		// ControlDate may not be defined yet on a cold desk load; poll briefly.
		let n = 0;
		const iv = setInterval(() => {
			if (patch() || ++n > 80) clearInterval(iv);
		}, 250);
	},
};
