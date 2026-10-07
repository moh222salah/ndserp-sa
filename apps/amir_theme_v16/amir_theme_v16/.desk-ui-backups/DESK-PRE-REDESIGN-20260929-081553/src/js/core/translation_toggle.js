/**
 * Rail toggle for the `incontext_translation` app's Translation Mode.
 *
 * Progressive enhancement, not a hard dependency: the button only appears
 * when `window.inctx` (the global that app exposes) is actually present —
 * total no-op, no button, no console error, on any site that doesn't have
 * incontext_translation installed. Never assumes the app exists.
 *
 * Delegates entirely to that app's own `window.inctx.toggle(bool)` — this
 * file owns none of the pencil-scanning/dialog logic, only the rail
 * affordance. State is read back from `<html data-inctx>` (the same flag
 * incontext_translation itself sets), watched via MutationObserver so the
 * icon stays in sync even when toggled another way (its Ctrl+Alt+T shortcut,
 * or the "Enable/Disable Translation Mode" item it injects into the navbar
 * dropdown) — one source of truth, never a second state machine.
 */

const SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>`;

function L(ar, en) {
	const lang = document.documentElement.getAttribute("lang");
	return lang === "ar" ? ar : en;
}

function isEnabled() {
	return document.documentElement.hasAttribute("data-inctx");
}

function syncActiveState($btn) {
	$btn.toggleClass("active", isEnabled());
}

/** Inject the translation-mode button into the rail bottom, between the
 * palette button and the language toggle. */
function attach($rail) {
	if (!$rail || !$rail.length) return;
	if (!window.inctx || typeof window.inctx.toggle !== "function") return;

	const $bottom = $rail.find(".amt-rail-bottom");
	if (!$bottom.length || $bottom.find(".amt-rail-translate").length) return;

	const $btn = $(
		`<div class="amt-rail-translate" title="${L("وضع الترجمة الفورية", "In-context translation")}" tabindex="0">` +
			`${SVG}<span class="amt-rail-translate-label">${L("ترجمة", "Translate")}</span></div>`
	);
	// The language toggle is optional (it can be moved to the navbar or hidden
	// via "Amir Theme Settings"), and `.before()` on an empty set silently does
	// nothing — which would drop this button too. `.amt-rail-toggle` is always
	// present, so fall back to it to keep the ordering stable either way.
	const $anchor = $bottom.find(".amt-rail-lang, .amt-rail-toggle").first();
	$anchor.length ? $anchor.before($btn) : $bottom.append($btn);
	syncActiveState($btn);

	$btn.on("click", (e) => {
		e.stopPropagation();
		window.inctx.toggle(!isEnabled());
	});
	$btn.on("keydown", (e) => {
		if (e.key === "Enter" || e.key === " ") {
			e.preventDefault();
			window.inctx.toggle(!isEnabled());
		}
	});

	const observer = new MutationObserver(() => syncActiveState($btn));
	observer.observe(document.documentElement, {
		attributes: true,
		attributeFilter: ["data-inctx"],
	});
}

export const translationToggle = { attach };
