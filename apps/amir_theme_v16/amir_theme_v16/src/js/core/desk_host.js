/**
 * Desk host lifecycle.
 *
 * The launcher is rendered asynchronously, well after document.ready, so a
 * module that queries `.desktop-container` on load finds nothing. Every desk
 * enhancement needs the same "wait for the host, then re-run when it changes"
 * behaviour, so it lives here once instead of being copied into each module.
 *
 * Guarantees given to subscribers:
 *   • called once as soon as the host exists (or immediately if it already did)
 *   • called again, coalesced to one call per frame, whenever the host subtree
 *     changes — covers route changes and app add/remove
 *   • called again after the desk is re-rendered from scratch on SPA re-entry
 *   • a subscriber that throws cannot stop the others
 *
 * WHY THE HOST IS TRACKED BY IDENTITY
 * -----------------------------------
 * Frappe does not update the desk in place. `on_page_show` calls
 * `DesktopPage.update()` -> `make()`, and `make()` starts with
 * `$(this.page.body).empty()` before re-rendering the template — so
 * `.desktop-container` is a BRAND NEW element on every SPA return to the desk.
 *
 * A MutationObserver bound to the previous container is therefore left watching
 * a detached node: it never fires again, the freshly rendered tiles are never
 * decorated, and the launcher comes back as bare Frappe artwork. That is the
 * "frozen / cached icons" symptom this module used to have, and the reason a
 * `window.location.reload()` workaround once sat in the bundle.
 *
 * The fix is to treat the host as a value that can be REPLACED, not a fixed
 * node: `watchHost` rebinds whenever the element identity changes, and the
 * settle passes below re-resolve the host after each route change so the rebind
 * actually happens. No reload required.
 *
 * Cost control: still exactly ONE MutationObserver on the host for the whole
 * theme. The bootstrap observer on <body> disconnects the moment the host
 * appears and hard-stops after 15s, so a route that never shows the desk leaves
 * nothing running. The settle passes are a fixed, bounded set of timers per
 * route change — never a poll.
 */

const subscribers = new Set();
const HOST_SELECTOR = ".desktop-container";
const BOOTSTRAP_TIMEOUT_MS = 15000;

/*
 * Frappe rebuilds the desk AFTER `page-change` has fired, so the container
 * visible at that instant is usually the outgoing one. These are the points at
 * which we re-resolve the host and re-run decoration. Bounded and few: the
 * observer handles everything that happens after the last pass, so this only
 * has to cover the gap between the route change and the new host existing.
 */
const SETTLE_DELAYS_MS = [0, 120, 400, 1000];

let hostObserver = null;
let watchedHost = null; // the exact node hostObserver is bound to
let bootstrapObserver = null;
let bootstrapTimer = null;
let frameQueued = false;
let settleTimers = [];

function notify() {
	for (const fn of subscribers) {
		try {
			fn();
		} catch (e) {
			// One broken enhancement must not take the others down with it.
			// eslint-disable-next-line no-console
			console.error("[amir_theme] desk subscriber failed:", e);
		}
	}
}

function scheduleNotify() {
	if (frameQueued) return;
	frameQueued = true;
	requestAnimationFrame(() => {
		frameQueued = false;
		notify();
	});
}

/**
 * The host, but only if it is actually still in the document. A container that
 * has been swapped out by `make()` can linger in a detached jQuery fragment;
 * decorating it would be invisible work.
 */
function liveHost() {
	const host = document.querySelector(HOST_SELECTOR);
	return host && host.isConnected ? host : null;
}

function watchHost(host) {
	// Same node we are already bound to — nothing to do. This makes the settle
	// passes cheap: only the pass that first sees a NEW container pays for a
	// rebind.
	if (watchedHost === host && hostObserver) return;
	if (hostObserver) hostObserver.disconnect();
	watchedHost = host;
	hostObserver = new MutationObserver(scheduleNotify);
	hostObserver.observe(host, { childList: true, subtree: true });
}

function clearSettle() {
	settleTimers.forEach(clearTimeout);
	settleTimers = [];
}

function settleOnce() {
	const host = liveHost();
	if (!host) return;
	watchHost(host); // rebinds if Frappe replaced the container
	notify();
}

function scheduleSettle() {
	clearSettle();
	settleTimers = SETTLE_DELAYS_MS.map((ms) => setTimeout(settleOnce, ms));
}

function stopBootstrap() {
	if (bootstrapObserver) {
		bootstrapObserver.disconnect();
		bootstrapObserver = null;
	}
	if (bootstrapTimer) {
		clearTimeout(bootstrapTimer);
		bootstrapTimer = null;
	}
}

function armBootstrap() {
	if (bootstrapObserver) return; // already waiting
	bootstrapObserver = new MutationObserver(() => {
		const el = liveHost();
		if (!el) return;
		stopBootstrap();
		watchHost(el);
		notify();
	});
	bootstrapObserver.observe(document.body, { childList: true, subtree: true });
	bootstrapTimer = setTimeout(stopBootstrap, BOOTSTRAP_TIMEOUT_MS);
}

/** Register a callback to run whenever the desk host is present or changes. */
export function onDeskReady(fn) {
	subscribers.add(fn);

	const host = liveHost();
	if (host) {
		watchHost(host);
		try {
			fn();
		} catch (e) {
			// eslint-disable-next-line no-console
			console.error("[amir_theme] desk subscriber failed:", e);
		}
		return;
	}

	armBootstrap();
}

/** Re-arm after a route change; cheap when the host is unchanged. */
export function refreshDeskHost() {
	if (!subscribers.size) return;

	const host = liveHost();
	if (host) {
		watchHost(host);
		notify();
	} else {
		// Host gone (navigated away from the desk, or mid-rebuild) — wait for it.
		armBootstrap();
	}

	// Run regardless of what we just found: on a return to the desk the node
	// above is typically the OUTGOING container, and the replacement only
	// appears a tick or two later. Each pass re-resolves the host, so the first
	// one that sees the new node rebinds the observer and decorates it.
	scheduleSettle();
}
