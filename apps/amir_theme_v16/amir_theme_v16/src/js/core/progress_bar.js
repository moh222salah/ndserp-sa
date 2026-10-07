/**
 * Request progress bar.
 *
 * A 2px bar across the top of the viewport that appears while the desk is
 * waiting on the server and finishes when the last request lands. On a healthy
 * site it is almost never seen; under load it is the difference between "the
 * app is working on it" and "the app has frozen".
 *
 * WHY THIS HOOK
 * Frappe already maintains the exact signal we need — it counts in-flight
 * requests off jQuery's global ajax events (frappe/public/js/frappe/request.js
 * lines 660-672). Subscribing to those same events is purely additive: no
 * polling loop, no MutationObserver, no patched Frappe function, and nothing
 * that runs at all while the desk is idle.
 *
 * We keep our OWN in-flight counter rather than reading
 * frappe.request.ajax_count, because that value depends on whether Frappe's
 * handler happens to run before or after ours in jQuery's dispatch order.
 * Counting locally makes the bar correct regardless of registration order.
 *
 * COST
 *   before first use  — nothing in the DOM at all; the element is created lazily
 *   idle after use    — one `display: none` leaf that is reused forever; the CSS
 *                       animation is detached with it, so no frames are drawn
 *                       (measured: computed animation-name is `none` when idle)
 *   fast request      — one setTimeout that is cleared before it ever fires
 *   slow request      — that one element, animated entirely by CSS
 *
 * In practice the desk's own boot requests are slow enough to create the element
 * during page load, so expect it to exist — hidden and inert — from then on.
 * There is deliberately no requestAnimationFrame loop. The growth curve is a
 * CSS animation, so it runs on the compositor and keeps moving smoothly even
 * when the main thread is busy — which is precisely when the bar matters.
 *
 * SAFETY
 * Every handler body is wrapped in try/catch. These callbacks run inside
 * jQuery's global ajax event chain, and an exception thrown from one handler
 * stops the handlers registered after it — so an unguarded error here could
 * break unrelated Frappe code. The bar is cosmetic; it must never be able to
 * take anything else down with it.
 *
 * The element is `pointer-events: none`, so it cannot intercept a click, and it
 * is appended to <body> as a leaf — it never wraps content, so it cannot become
 * an ancestor of a child-table grid (see the transform/containing-block trap
 * documented in components/_hijri-date.scss).
 */

// Below this, a request is over before a human would register the bar at all;
// showing it would read as a flicker rather than as feedback.
const SHOW_AFTER_MS = 180;
// Long enough for the 100% fill to be seen, short enough not to linger.
const FADE_OUT_MS = 420;

let bar = null;
let inFlight = 0;
let showTimer = null;
let hideTimer = null;
let revealed = false;

function ensureBar() {
	if (bar && bar.isConnected) return bar;
	bar = document.createElement("div");
	bar.className = "amt-progress";
	bar.setAttribute("aria-hidden", "true");
	const fill = document.createElement("div");
	fill.className = "amt-progress__fill";
	bar.appendChild(fill);
	document.body.appendChild(bar);
	return bar;
}

function reveal() {
	showTimer = null;
	if (inFlight <= 0) return; // finished while we were waiting out the threshold
	const el = ensureBar();
	clearTimeout(hideTimer);
	hideTimer = null;
	el.classList.remove("is-done");
	// Force a reflow so re-showing restarts the CSS animation from 0 instead of
	// resuming wherever the previous run left off.
	void el.offsetWidth;
	el.classList.add("is-active");
	revealed = true;
}

function finish() {
	clearTimeout(showTimer);
	showTimer = null;
	if (!revealed || !bar) return; // never shown — nothing to wind down
	revealed = false;

	const fill = bar.querySelector(".amt-progress__fill");
	if (fill) {
		// Freeze the animation at its current width, then hand off to the
		// `is-done` transition. Without pinning the computed width first, killing
		// the animation would snap the fill back to 0 and the bar would appear to
		// run backwards before completing.
		const w = getComputedStyle(fill).width;
		fill.style.animation = "none";
		fill.style.width = w;
		void fill.offsetWidth;
		fill.style.width = "";
	}
	bar.classList.add("is-done");

	hideTimer = setTimeout(() => {
		hideTimer = null;
		if (revealed || !bar) return; // a new request started mid-fade; leave it alone
		bar.classList.remove("is-active", "is-done");
		const f = bar.querySelector(".amt-progress__fill");
		if (f) f.style.animation = "";
	}, FADE_OUT_MS);
}

function onSend() {
	try {
		inFlight++;
		if (inFlight === 1 && !revealed && showTimer === null) {
			showTimer = setTimeout(reveal, SHOW_AFTER_MS);
		}
	} catch (e) {
		/* cosmetic only — never break the ajax chain */
	}
}

function onComplete() {
	try {
		// Guard against going negative: a request that was already in flight when
		// this module mounted will fire `complete` without a matching `send`.
		inFlight = Math.max(0, inFlight - 1);
		if (inFlight === 0) finish();
	} catch (e) {
		/* cosmetic only — never break the ajax chain */
	}
}

export const progressBar = {
	mount() {
		if (typeof window.$ !== "function") return;
		$(document).ajaxSend(onSend);
		$(document).ajaxComplete(onComplete);
	},
};
