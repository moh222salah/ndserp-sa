/*
 * NDS ERP Saudi — "new blocks" layer for the redesigned dashboard workspaces.
 *
 * Problem this solves
 * -------------------
 * Sales / Purchases / Warehouse / Accounts replace the stock Workspace body with
 * a hand-built dashboard. Anything a manager adds afterwards through the stock
 * "Edit" mode (a section, a card, a shortcut, a number card, a chart) is saved
 * into the Workspace content, but the dashboards either hide the stock editor
 * or only know a fixed set of sections, so the new item never shows in the new
 * design (or shows in the stock ERP look).
 *
 * How it works (presentation only — no ERP data or schema is touched)
 * -------------------------------------------------------------------
 *  1. Tagging. On Save in Edit mode, every block that was not already part of
 *     the previously saved content is tagged `data.nds_new = 1` inside the
 *     Workspace content JSON. Blocks that already existed keep their original
 *     (untagged) status, so nothing the dashboards deliberately hide today
 *     reappears. Matching is by block type + name, never by Editor.js id.
 *  2. Rendering. Outside Edit mode, tagged blocks are rendered as a new-design
 *     layer (#nds-new-blocks) under the dashboard, using Frappe's own widgets
 *     (so data, charts, routes and permissions are exactly the stock ones),
 *     skinned by components/_new-blocks.scss.
 *  3. De-duplication. The stock editor copy of a tagged block is marked
 *     `.nds-new-block-native` and hidden outside Edit mode, and the dashboards'
 *     own section builders skip it through `isNativeNew()` / `flaggedCardLabels()`.
 *
 * Every entry point is wrapped so a failure here can never break the desk.
 */
const newBlocks = (() => {
	"use strict";

	const LAYER_ID = "nds-new-blocks";
	const FLAG = "nds_new";
	const NATIVE_CLASS = "nds-new-block-native";

	// Block type → [page_data collection, widget type, native wrapper attribute].
	const WIDGET_TYPES = {
		card: ["cards", "links", "card_name"],
		shortcut: ["shortcuts", "shortcut", "shortcut_name"],
		number_card: ["number_cards", "number_card", "number_card_name"],
		chart: ["charts", "chart", "chart_name"],
		quick_list: ["quick_lists", "quick_list", "quick_list_name"],
		custom_block: ["custom_blocks", "custom_block", "custom_block_name"],
	};
	const TEXT_TYPES = new Set(["header", "paragraph"]);
	// Never tagged: pure layout filler, or a type this layer does not render.
	const UNTAGGED_TYPES = new Set(["spacer", "onboarding"]);
	const NAME_KEYS = [
		"card_name", "shortcut_name", "number_card_name", "chart_name",
		"quick_list_name", "custom_block_name", "text",
	];

	let started = false;
	let timer = null;
	let flaggedCache = { raw: null, blocks: [] };

	// --- helpers -----------------------------------------------------------

	function plainText(html) {
		try {
			const doc = new DOMParser().parseFromString(String(html == null ? "" : html), "text/html");
			return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
		} catch (_) {
			return String(html == null ? "" : html).trim();
		}
	}

	function normalize(value) {
		return plainText(value)
			.toLowerCase()
			.replace(/[أإآ]/g, "ا")
			.replace(/[يى]/g, "ي")
			.replace(/[ً-ٟ]/g, "");
	}

	function blockName(block) {
		const data = (block && block.data) || {};
		for (const key of NAME_KEYS) {
			if (data[key] != null && data[key] !== "") return data[key];
		}
		return "";
	}

	function blockSignature(block) {
		return String(block && block.type || "") + "|" + normalize(blockName(block));
	}

	function parseContent(raw) {
		if (Array.isArray(raw)) return raw;
		if (typeof raw !== "string" || !raw) return null;
		try {
			const parsed = JSON.parse(raw);
			return Array.isArray(parsed) ? parsed : null;
		} catch (_) {
			return null;
		}
	}

	function workspace() {
		return window.frappe && frappe.workspace ? frappe.workspace : null;
	}

	function rawContent() {
		const ws = workspace();
		const page = ws && ws._page;
		return page && typeof page.content === "string" ? page.content : null;
	}

	function isEditMode(host) {
		return Boolean(host && host.classList.contains("edit-mode"));
	}

	function isRtl() {
		const root = document.documentElement;
		const lang = String((window.frappe && frappe.boot && frappe.boot.lang) || root.getAttribute("lang") || "").toLowerCase();
		if (lang.startsWith("ar")) return true;
		if (lang.startsWith("en")) return false;
		return String(root.getAttribute("dir") || "").toLowerCase() === "rtl";
	}

	// The host element of whichever redesigned dashboard is on screen, or null.
	// The per-dashboard "ready" classes are removed by each dashboard's cleanup, so
	// they are a reliable "this redesigned workspace is showing right now" signal.
	function dashboardHost() {
		try {
			const body = document.body;
			const root = document.documentElement;
			if (!body || !root) return null;
			const ready =
				body.classList.contains("nds-sales-dashboard-ready") ||
				body.classList.contains("nds-purchase-dashboard-ready") ||
				body.classList.contains("nds-accounts-dashboard-ready") ||
				root.classList.contains("nds-warehouse-dashboard-ready");
			if (!ready) return null;
			const route = window.frappe && typeof frappe.get_route === "function" ? frappe.get_route() : [];
			if (!Array.isArray(route) || route[0] !== "Workspaces") return null;
			const page = document.getElementById("page-Workspaces");
			return page ? page.querySelector(".layout-main-section") : null;
		} catch (_) {
			return null;
		}
	}

	// --- 1. tagging --------------------------------------------------------

	// Tags the blocks Editor.js is about to save. `previousRaw` is the content
	// that was saved before this edit session.
	function tagOutput(output, previousRaw) {
		const previous = parseContent(previousRaw);
		// Unknown previous content: tag nothing rather than risk resurfacing
		// blocks the dashboards intentionally hide.
		if (!previous || !output || !Array.isArray(output.blocks)) return;

		const pool = new Map();
		previous.forEach((block) => {
			if (!block || UNTAGGED_TYPES.has(block.type)) return;
			const signature = blockSignature(block);
			if (!pool.has(signature)) pool.set(signature, []);
			pool.get(signature).push(Boolean(block.data && Number(block.data[FLAG]) === 1));
		});

		output.blocks.forEach((block) => {
			if (!block || !block.data || UNTAGGED_TYPES.has(block.type)) return;
			if (!WIDGET_TYPES[block.type] && !TEXT_TYPES.has(block.type)) return;
			const signature = blockSignature(block);
			if (!blockName(block)) return;
			const known = pool.get(signature);
			// Seen before → inherit its status. Not seen → added in this session.
			const flagged = known && known.length ? known.shift() : true;
			if (flagged) block.data[FLAG] = 1;
			else delete block.data[FLAG];
		});
	}

	// Instance-level wrapper around Workspace#save_page: the stock method calls
	// `this.editor.save()` synchronously, so the wrapper only needs to be in
	// place for the duration of that one call.
	function patchWorkspace() {
		const ws = workspace();
		if (!ws || ws.__ndsNewBlocksPatched || typeof ws.save_page !== "function") return;
		const original = ws.save_page;
		ws.save_page = function (page) {
			let restore = null;
			try {
				const editor = this.editor;
				if (dashboardHost() && editor && typeof editor.save === "function") {
					const previous = page && page.content;
					const hadOwn = Object.prototype.hasOwnProperty.call(editor, "save");
					const realSave = editor.save;
					editor.save = function () {
						return Promise.resolve(realSave.apply(this, arguments)).then((output) => {
							try { tagOutput(output, previous); } catch (_) { /* keep the save */ }
							return output;
						});
					};
					restore = () => {
						if (hadOwn) editor.save = realSave;
						else delete editor.save;
					};
				}
			} catch (_) { /* fall through to the stock save */ }
			try {
				return original.apply(this, arguments);
			} finally {
				if (restore) restore();
			}
		};
		ws.__ndsNewBlocksPatched = true;
	}

	// --- 2. reading tagged blocks -----------------------------------------

	function flaggedBlocks() {
		const raw = rawContent();
		if (raw === flaggedCache.raw) return flaggedCache.blocks;
		const blocks = (parseContent(raw) || []).filter((block) =>
			block && block.data && Number(block.data[FLAG]) === 1 && blockName(block) &&
			(WIDGET_TYPES[block.type] || TEXT_TYPES.has(block.type))
		);
		flaggedCache = { raw, blocks };
		return blocks;
	}

	function flaggedSignatures() {
		return new Set(flaggedBlocks().map(blockSignature));
	}

	// Raw labels of tagged link-cards, for dashboards that build their own
	// sections from the Workspace link rows.
	function flaggedCardLabels() {
		try {
			return flaggedBlocks()
				.filter((block) => block.type === "card")
				.map((block) => plainText(block.data.card_name));
		} catch (_) {
			return [];
		}
	}

	// Signature of a stock Editor.js block, read back from its DOM.
	function nativeSignature(block) {
		if (!block || !block.querySelector) return null;
		for (const type of Object.keys(WIDGET_TYPES)) {
			const attribute = WIDGET_TYPES[type][2];
			const node = block.querySelector("[" + attribute + "]");
			if (node) return type + "|" + normalize(node.getAttribute(attribute));
		}
		const header = block.querySelector(".ce-header");
		if (header) return "header|" + normalize(header.textContent);
		const paragraph = block.querySelector(".ce-paragraph");
		if (paragraph) return "paragraph|" + normalize(paragraph.textContent);
		return null;
	}

	// True when `element` (a stock widget or .ce-block) is the editor copy of a
	// tagged block. Works on detached editors too.
	function isNativeNew(element) {
		try {
			if (!element) return false;
			const block = element.closest ? (element.closest(".ce-block") || element) : element;
			const signature = nativeSignature(block);
			return Boolean(signature && flaggedSignatures().has(signature));
		} catch (_) {
			return false;
		}
	}

	function markNative() {
		const editor = document.querySelector("#page-Workspaces #editorjs");
		if (!editor) return;
		const flagged = flaggedSignatures();
		editor.querySelectorAll(".ce-block").forEach((block) => {
			const signature = nativeSignature(block);
			const mark = Boolean(signature && flagged.has(signature));
			if (mark !== block.classList.contains(NATIVE_CLASS)) block.classList.toggle(NATIVE_CLASS, mark);
		});
	}

	// --- 3. rendering ------------------------------------------------------

	function findItem(collection, name) {
		const items = collection && Array.isArray(collection.items) ? collection.items : [];
		const wanted = [plainText(name)];
		try { wanted.push(plainText(__(name))); } catch (_) { /* untranslated is fine */ }
		return items.find((item) => {
			const label = plainText(item && item.label);
			return wanted.includes(label);
		}) || null;
	}

	function removeLayer() {
		const existing = document.getElementById(LAYER_ID);
		if (existing) existing.remove();
	}

	function columnSpan(block) {
		const col = parseInt(block.data && block.data.col, 10);
		if (Number.isFinite(col) && col >= 1 && col <= 12) return col;
		const fallback = block.type === "chart" || block.type === "custom_block" ? 12 : 4;
		return TEXT_TYPES.has(block.type) ? 12 : fallback;
	}

	function mountWidget(cell, block, pageData) {
		const spec = WIDGET_TYPES[block.type];
		if (!spec || !pageData || !window.frappe || !frappe.widget || !frappe.widget.SingleWidgetGroup) return false;
		const item = findItem(pageData[spec[0]], blockName(block));
		if (!item) return false;
		cell.setAttribute(spec[2], blockName(block));
		new frappe.widget.SingleWidgetGroup({
			container: cell,
			type: spec[1],
			class_name: block.type === "chart" ? "widget-charts" : "",
			options: {
				allow_sorting: false,
				allow_create: false,
				allow_delete: false,
				allow_hiding: false,
				allow_edit: false,
				allow_resize: false,
			},
			widgets: Object.assign({}, item, { in_customize_mode: false }),
		});
		return true;
	}

	function renderLayer(host) {
		const blocks = flaggedBlocks();
		const ws = workspace();
		const pageData = ws && ws.page_data;
		const rtl = isRtl();
		if (!blocks.length || !pageData) {
			removeLayer();
			return;
		}

		// Wait until Frappe's page data belongs to the page whose content we read;
		// during a workspace switch the two briefly disagree.
		const current = ws.pages && ws._page ? ws.pages[ws._page.name] : null;
		if (current && current !== pageData) return;

		const sizes = Object.keys(WIDGET_TYPES).map((type) => {
			const collection = pageData[WIDGET_TYPES[type][0]];
			return collection && Array.isArray(collection.items) ? collection.items.length : 0;
		}).join(",");
		const signature = (rtl ? "rtl" : "ltr") + "|" + sizes + "|" + rawContent();
		const existing = document.getElementById(LAYER_ID);
		if (existing && existing.parentElement === host && existing.dataset.signature === signature) return;
		if (existing) existing.remove();

		const layer = document.createElement("section");
		layer.id = LAYER_ID;
		layer.className = "nds-nb";
		layer.dataset.signature = signature;
		layer.setAttribute("dir", rtl ? "rtl" : "ltr");
		layer.setAttribute("lang", rtl ? "ar" : "en");

		const grid = document.createElement("div");
		grid.className = "nds-nb-grid";
		layer.appendChild(grid);
		// Attach before building the widgets: charts size themselves from the DOM.
		host.appendChild(layer);

		blocks.forEach((block) => {
			const cell = document.createElement("div");
			cell.className = "nds-nb-cell nds-nb-" + block.type.replace(/_/g, "-");
			cell.style.setProperty("--nds-nb-col", String(columnSpan(block)));

			if (block.type === "header") {
				const heading = document.createElement("h3");
				heading.className = "nds-nb-heading";
				heading.textContent = plainText(block.data.text);
				cell.appendChild(heading);
			} else if (block.type === "paragraph") {
				const note = document.createElement("p");
				note.className = "nds-nb-note";
				note.textContent = plainText(block.data.text);
				cell.appendChild(note);
			} else {
				let mounted = false;
				try { mounted = mountWidget(cell, block, pageData); } catch (_) { mounted = false; }
				if (!mounted) return;
			}
			grid.appendChild(cell);
		});

		if (!grid.children.length) layer.remove();
	}

	// --- driver ------------------------------------------------------------

	function sync() {
		try {
			patchWorkspace();
			const host = dashboardHost();
			if (!host) {
				removeLayer();
				return;
			}
			if (isEditMode(host)) {
				removeLayer();
				return;
			}
			markNative();
			renderLayer(host);
		} catch (_) { /* never let this layer break the desk */ }
	}

	function schedule() {
		if (timer) return;
		timer = window.setTimeout(() => {
			timer = null;
			sync();
		}, 150);
	}

	function install() {
		if (started) return;
		started = true;
		const boot = () => {
			schedule();
			if (window.frappe && frappe.router && typeof frappe.router.on === "function") {
				frappe.router.on("change", schedule);
			}
			window.addEventListener("popstate", schedule);
			if (window.$) $(document).on("page-change", schedule);
			if (document.body) {
				// Structure changes (render / re-render) and the Edit-mode class toggle.
				new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
				new MutationObserver(schedule).observe(document.body, {
					attributes: true,
					subtree: true,
					attributeFilter: ["class"],
				});
			}
		};
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", boot, { once: true });
		} else {
			boot();
		}
	}

	return { mount: install, isNativeNew, flaggedCardLabels };
})();

export { newBlocks };
