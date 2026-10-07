/*
 * Console hygiene — neutralise two well-known, harmless noise sources that
 * frappe-charts (bundled in frappe core's desk.bundle) emits while rendering the
 * dashboard/workspace charts. Neither indicates a real problem, but one of them
 * surfaces as an *uncaught* red error, which looks alarming and can trip error
 * reporters. We fix them defensively here instead of patching vendored core.
 *
 * 1) Uncaught NotFoundError: Failed to execute 'removeChild' … not a child.
 *    BaseChart.makeChartArea() does `this.container.removeChild(this.svg)`
 *    unconditionally. Its ResizeObserver (boundDrawFn) can fire AFTER the
 *    workspace/editor.js re-rendered and already detached that SVG, so the node
 *    is no longer a child → the call throws. We shim removeChild/insertBefore to
 *    no-op in exactly the case they would otherwise throw (node not a child of
 *    the target). This is the same guard React apps ship against Google-Translate
 *    style DOM mutation; it can never change behaviour of *correct* calls, since
 *    a correct removeChild is never made on a non-child.
 *
 * 2) `"" is not a valid color.` — BaseChart.validateColors() warns when a chart
 *    config carries an empty colour string. Purely cosmetic; we filter only this
 *    exact message and pass every other warning through untouched.
 */
export const consoleHygiene = {
	install() {
		this._guardDomRace();
		this._filterChartColorWarning();
	},

	_guardDomRace() {
		const proto = Node.prototype;

		const originalRemoveChild = proto.removeChild;
		proto.removeChild = function (child) {
			if (child && child.parentNode !== this) {
				// Would throw NotFoundError; the node is already gone → treat as done.
				return child;
			}
			return originalRemoveChild.apply(this, arguments);
		};

		const originalInsertBefore = proto.insertBefore;
		proto.insertBefore = function (newNode, referenceNode) {
			if (referenceNode && referenceNode.parentNode !== this) {
				// Would throw NotFoundError; append instead of crashing.
				return originalInsertBefore.call(this, newNode, null);
			}
			return originalInsertBefore.apply(this, arguments);
		};
	},

	_filterChartColorWarning() {
		const originalWarn = console.warn.bind(console);
		console.warn = function (...args) {
			const first = args[0];
			if (typeof first === "string" && first.indexOf("is not a valid color") !== -1) {
				return; // benign frappe-charts noise
			}
			return originalWarn(...args);
		};
	},
};
