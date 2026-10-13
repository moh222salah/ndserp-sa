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
 *  4. Edit-mode controls. Section cards a dashboard builds from a Workspace card carry
 *     `data-nds-card-labels`; while editing, each gets a delete button, a deleted (or
 *     missing) card shows a "+" placeholder, and the end of the sections gets a "+" tile.
 *     Delete / add act on the stock Editor.js instance, so nothing is stored until the
 *     stock Save button is pressed, and Save re-renders the dashboards at once.
 *
 *  5. Layout. The layer is a stack of rows. In Edit mode it is also the editing surface:
 *     blocks drag between rows, a "..." menu edits / resizes / deletes one, and every row
 *     ends with a "+". Row and width are stored on the block (`data.row`, `data.col`) by
 *     the stock Save button; nothing is stored before that, Discard throws it away.
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

	const CARD_ATTR = "data-nds-card-labels";
	const fixedCardMatchers = [];

	// Layout edits made in Edit mode, applied by the stock Save (tagOutput) and dropped by
	// the reload that follows Save / Discard.
	const pendingRows = new Map();
	const pendingCols = new Map();
	let pendingAdd = null;

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

	// Frappe keeps `_page.content` as a JSON string until the page is shown, then
	// replaces it with the parsed array (show_page) — so the steady state while a
	// dashboard is on screen is an array. Both forms must be read, otherwise the
	// layer never sees the saved blocks and nothing renders after Save.
	function rawContent() {
		const ws = workspace();
		const page = ws && ws._page;
		if (!page) return null;
		if (typeof page.content === "string") return page.content;
		if (Array.isArray(page.content)) {
			try { return JSON.stringify(page.content); } catch (_) { return null; }
		}
		return null;
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

	const TEXT = {
		ar: {
			remove: "حذف",
			confirm: (name) => "هل تريد حذف «" + name + "» من هذه الصفحة؟ سيُحذف من مساحة العمل ولا يمكن التراجع عن ذلك.",
			done: "تم الحذف",
			failed: "تعذّر الحذف. حاول مرة أخرى.",
			stageConfirm: (name) => "هل تريد حذف «" + name + "»؟ سيتم الحذف عند الضغط على «حفظ»، ويمكنك التراجع بالضغط على «إهمال».",
			add: "إضافة جديد",
			options: "خيارات",
			edit: "تعديل",
			wider: "توسيع",
			narrower: "تضييق",
			drag: "اسحب لنقل العنصر",
			rowAdd: "إضافة في هذا الصف",
			newRow: "صف جديد",
				earlier: "تقديم",
				later: "تأخير",
				laneAdd: "إضافة عنصر جديد",
			noEditor: "تعذّر فتح التعديل لهذا العنصر.",
			addTitle: "إضافة جديدة",
			addKind: "ماذا تريد أن تضيف؟",
			addAction: "إضافة",
			types: { card: "قسم (كارت روابط)", shortcut: "اختصار", number_card: "كارت رقمي", chart: "مخطط", quick_list: "قائمة سريعة" },
		},
		en: {
			remove: "Delete",
			confirm: (name) => "Delete “" + name + "” from this page? It will be removed from the workspace and this cannot be undone.",
			done: "Deleted",
			failed: "Could not delete. Please try again.",
			stageConfirm: (name) => "Delete “" + name + "”? It is removed when you press Save, and Discard brings it back.",
			add: "Add new",
			options: "Options",
			edit: "Edit",
			wider: "Wider",
			narrower: "Narrower",
			drag: "Drag to move",
			rowAdd: "Add to this row",
			newRow: "New row",
				earlier: "Move earlier",
				later: "Move later",
				laneAdd: "Add a new item",
			noEditor: "This item cannot be edited here.",
			addTitle: "Add new",
			addKind: "What do you want to add?",
			addAction: "Add",
			types: { card: "Section (link card)", shortcut: "Shortcut", number_card: "Number card", chart: "Chart", quick_list: "Quick list" },
		},
	};

	function text() {
		return isRtl() ? TEXT.ar : TEXT.en;
	}

	function escapeHtml(value) {
		return String(value == null ? "" : value)
			.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	}

	function canEdit() {
		const ws = workspace();
		return Boolean(ws && ws._page && ws._page.is_editable);
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
				root.classList.contains("nds-warehouse-dashboard-ready") ||
				root.classList.contains("nds-assets-dashboard-ready") ||
				root.classList.contains("nds-hr-dashboard-ready");
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

	function registerFixedCards(matcher) {
		if (typeof matcher === "function") fixedCardMatchers.push(matcher);
	}

	// A card that maps onto one of a dashboard's own fixed sections is rendered there,
	// so it must not also be tagged as a new block.
	function isFixedCard(block) {
		if (!block || block.type !== "card") return false;
		const name = plainText(blockName(block));
		return fixedCardMatchers.some((matcher) => {
			try { return Boolean(matcher(name)); } catch (_) { return false; }
		});
	}

	function savedRow(block) {
		const row = parseInt(block && block.data && block.data.row, 10);
		return Number.isFinite(row) && row >= 0 ? row : null;
	}

	// Tags the blocks Editor.js is about to save and writes their layout (row, width).
	// `previousRaw` is the content that was saved before this edit session.
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
			pool.get(signature).push({
				flagged: Boolean(block.data && Number(block.data[FLAG]) === 1),
				row: savedRow(block),
			});
		});

		output.blocks.forEach((block) => {
			if (!block || !block.data || UNTAGGED_TYPES.has(block.type)) return;
			if (!WIDGET_TYPES[block.type] && !TEXT_TYPES.has(block.type)) return;
			const signature = blockSignature(block);
			if (!blockName(block)) return;
			const known = pool.get(signature);
			const entry = known && known.length ? known.shift() : null;
			// Seen before → inherit its status. Not seen → added in this session.
			const flagged = entry ? entry.flagged : true;
			if (flagged && !isFixedCard(block)) {
				block.data[FLAG] = 1;
				let row = null;
				if (pendingRows.has(signature)) row = pendingRows.get(signature);
				else if (entry) row = entry.row;
				else if (pendingAdd && (!pendingAdd.type || pendingAdd.type === block.type)) row = pendingAdd.row;
				if (row != null) block.data.row = row;
				else delete block.data.row;
				if (pendingCols.has(signature)) block.data.col = pendingCols.get(signature);
			} else {
				delete block.data[FLAG];
				delete block.data.row;
			}
		});
		pendingAdd = null;
	}

	// Instance-level wrapper around Workspace#reload: Save and Discard both end in a
	// reload, so this is the moment the dashboards must rebuild from the new content.
	function patchReload() {
		const ws = workspace();
		if (!ws || ws.__ndsReloadPatched || typeof ws.reload !== "function") return;
		const original = ws.reload;
		ws.reload = function () {
			const result = original.apply(this, arguments);
			Promise.resolve(result).then(() => {
				anchors.clear();
				pendingHidden = null;
				pendingLayout = null;
				pendingRows.clear();
				pendingCols.clear();
				pendingAdd = null;
				flaggedCache = { raw: null, blocks: [] };
				try { document.dispatchEvent(new CustomEvent("nds-workspace-reloaded")); } catch (_) { /* optional */ }
				schedule();
			}).catch(() => {});
			return result;
		};
		ws.__ndsReloadPatched = true;
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
								try { writeHidden(output, previous); } catch (_) { /* keep the save */ }
								try { writeLayout(output, previous); } catch (_) { /* keep the save */ }
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

	// --- 4. layout: rows, drag and drop, per-block menu ---------------------

	const SPAN_STEPS = [3, 4, 6, 8, 12];
	let currentRows = [];
	let dragSig = null;
	let openMenu = null;
	let layoutPage = null;

	function spanOf(block) {
		const signature = blockSignature(block);
		return pendingCols.has(signature) ? pendingCols.get(signature) : columnSpan(block);
	}

	// Order of the blocks in the stock editor, by signature. The stock editor is what gets
	// saved, so while editing it decides which blocks still exist and in which order.
	function liveOrder() {
		const editor = editorApi();
		const holders = editor ? blockHolders(editor) : null;
		if (!holders) return null;
		const order = new Map();
		holders.forEach((holder, index) => {
			const signature = nativeSignature(holder);
			if (signature && !order.has(signature)) order.set(signature, index);
		});
		return order;
	}

	function layerBlocks(editing) {
		const saved = flaggedBlocks();
		if (!editing) return saved;
		const live = liveOrder();
		if (!live) return saved;
		return saved
			.filter((block) => live.has(blockSignature(block)))
			.sort((a, b) => live.get(blockSignature(a)) - live.get(blockSignature(b)));
	}

	// Rows with an explicit number keep it; blocks without one (saved before rows existed)
	// flow into rows of 12 columns after them, which is how the grid used to place them.
	function buildRows(blocks) {
		const explicit = new Map();
		const loose = [];
		blocks.forEach((block) => {
			const signature = blockSignature(block);
			const row = pendingRows.has(signature) ? pendingRows.get(signature) : savedRow(block);
			if (row == null) {
				loose.push(block);
				return;
			}
			if (!explicit.has(row)) explicit.set(row, []);
			explicit.get(row).push(block);
		});
		const rows = Array.from(explicit.keys()).sort((a, b) => a - b).map((key) => explicit.get(key));
		let current = [];
		let used = 0;
		loose.forEach((block) => {
			const span = spanOf(block);
			if (current.length && used + span > 12) {
				rows.push(current);
				current = [];
				used = 0;
			}
			current.push(block);
			used += span;
		});
		if (current.length) rows.push(current);
		return rows;
	}

	// Pins the rows being shown, so every block has an explicit row when Save stores them.
	function normalizeRows() {
		currentRows.forEach((row, index) => row.forEach((signature) => pendingRows.set(signature, index)));
	}

	function holderIndex(signature) {
		const editor = editorApi();
		const holders = editor ? blockHolders(editor) : null;
		if (!holders) return -1;
		return holders.findIndex((holder) => nativeSignature(holder) === signature);
	}

	function moveInEditor(signature, target) {
		const editor = editorApi();
		if (!editor || !target || typeof editor.blocks.move !== "function") return;
		const from = holderIndex(signature);
		const at = holderIndex(target.signature);
		if (from === -1 || at === -1) return;
		const to = target.side === "before" ? (from < at ? at - 1 : at) : (from < at ? at : at + 1);
		if (to !== from) editor.blocks.move(to, from);
	}

	// target: { type: "cell", signature, side } | { type: "row", index } | { type: "new" }
	function moveBlockTo(signature, target) {
		const rows = currentRows.map((row) => row.slice());
		rows.forEach((row) => {
			const at = row.indexOf(signature);
			if (at !== -1) row.splice(at, 1);
		});
		let editorTarget = null;
		if (target.type === "cell") {
			if (target.signature === signature) return;
			const row = rows.find((candidate) => candidate.includes(target.signature));
			if (!row) return;
			row.splice(row.indexOf(target.signature) + (target.side === "after" ? 1 : 0), 0, signature);
			editorTarget = { signature: target.signature, side: target.side };
		} else if (target.type === "row") {
			const row = rows[target.index];
			if (!row) return;
			row.push(signature);
			if (row.length > 1) editorTarget = { signature: row[row.length - 2], side: "after" };
		} else {
			rows.push([signature]);
		}
		rows.filter((row) => row.length).forEach((row, index) => row.forEach((item) => pendingRows.set(item, index)));
		try { moveInEditor(signature, editorTarget); } catch (_) { /* the row change still applies */ }
		schedule();
	}

	function resizeBlock(block, direction) {
		const signature = blockSignature(block);
		const now = spanOf(block);
		let index = SPAN_STEPS.findIndex((step) => step >= now);
		if (index === -1) index = SPAN_STEPS.length - 1;
		const next = SPAN_STEPS[Math.max(0, Math.min(SPAN_STEPS.length - 1, index + direction))];
		pendingCols.set(signature, next);
		schedule();
	}

	// Staged delete: removes the block from the stock editor. Nothing is stored until the
	// stock Save button runs `save_page`, and Discard brings the block back.
	async function stageDeleteBlock(signature) {
		const editor = editorApi();
		const index = holderIndex(signature);
		if (!editor || index === -1) return;
		await editor.blocks.delete(index);
		pendingRows.delete(signature);
		pendingCols.delete(signature);
		schedule();
	}

	// The stock widget keeps its own edit dialog behind a (hidden) control of its editor block.
	function editBlock(signature) {
		const editor = editorApi();
		const holders = editor ? blockHolders(editor) : null;
		const holder = holders && holders[holderIndex(signature)];
		const control = holder && holder.querySelector(".widget-control .edit-button, .edit-button");
		if (control) {
			control.click();
			return;
		}
		if (window.frappe && typeof frappe.show_alert === "function") {
			frappe.show_alert({ message: text().noEditor, indicator: "orange" });
		}
	}

	function closeMenu() {
		if (!openMenu) return;
		const button = openMenu.parentElement && openMenu.parentElement.querySelector(".nds-nb-more");
		if (button) button.setAttribute("aria-expanded", "false");
		openMenu.remove();
		openMenu = null;
	}

	function menuItem(label, run, danger) {
		const item = document.createElement("button");
		item.type = "button";
		item.className = "nds-nb-menu-item" + (danger ? " is-danger" : "");
		item.setAttribute("role", "menuitem");
		item.textContent = label;
		item.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			closeMenu();
			run();
		});
		return item;
	}

	function toggleMenu(cell, block, button) {
		const wasOpen = Boolean(openMenu) && openMenu.parentElement === cell;
		closeMenu();
		if (wasOpen) return;
		const t = text();
		const signature = blockSignature(block);
		const menu = document.createElement("div");
		menu.className = "nds-nb-menu";
		menu.setAttribute("role", "menu");
		if (WIDGET_TYPES[block.type]) {
			menu.appendChild(menuItem(t.edit, () => editBlock(signature)));
			menu.appendChild(menuItem(t.wider, () => resizeBlock(block, 1)));
			menu.appendChild(menuItem(t.narrower, () => resizeBlock(block, -1)));
		}
		menu.appendChild(menuItem(t.remove, () => {
			frappe.confirm(escapeHtml(t.stageConfirm(plainText(blockName(block)))), () => stageDeleteBlock(signature));
		}, true));
		cell.appendChild(menu);
		button.setAttribute("aria-expanded", "true");
		openMenu = menu;
	}

	function dragSide(event, cell) {
		const rect = cell.getBoundingClientRect();
		const left = event.clientX < rect.left + rect.width / 2;
		const rtl = isRtl();
		return { visual: left ? "left" : "right", side: left === !rtl ? "before" : "after" };
	}

	function clearDragMarks() {
		document.querySelectorAll("#" + LAYER_ID + " .drop-left, #" + LAYER_ID + " .drop-right, #" + LAYER_ID + " .is-drop-target")
			.forEach((node) => node.classList.remove("drop-left", "drop-right", "is-drop-target"));
	}

	function endDrag() {
		dragSig = null;
		clearDragMarks();
		document.querySelectorAll("#" + LAYER_ID + " .is-dragging").forEach((node) => node.classList.remove("is-dragging"));
	}

	function iconSvg(path) {
		return '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' + path + "</svg>";
	}

	function handleButton(cell, block) {
		const t = text();
		const signature = blockSignature(block);
		const handle = document.createElement("span");
		handle.className = "nds-nb-handle";
		handle.setAttribute("role", "button");
		handle.setAttribute("tabindex", "-1");
		handle.setAttribute("draggable", "true");
		handle.title = t.drag;
		handle.setAttribute("aria-label", t.drag);
		handle.innerHTML = iconSvg('<g fill="currentColor"><circle cx="5.5" cy="4" r="1.3"/><circle cx="10.5" cy="4" r="1.3"/><circle cx="5.5" cy="8" r="1.3"/><circle cx="10.5" cy="8" r="1.3"/><circle cx="5.5" cy="12" r="1.3"/><circle cx="10.5" cy="12" r="1.3"/></g>');
		handle.addEventListener("dragstart", (event) => {
			closeMenu();
			dragSig = signature;
			cell.classList.add("is-dragging");
			if (event.dataTransfer) {
				event.dataTransfer.effectAllowed = "move";
				try { event.dataTransfer.setData("text/plain", signature); } catch (_) { /* optional */ }
				try { event.dataTransfer.setDragImage(cell, 24, 24); } catch (_) { /* optional */ }
			}
		});
		handle.addEventListener("dragend", endDrag);
		return handle;
	}

	function moreButton(cell, block) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-more";
		button.title = t.options;
		button.setAttribute("aria-label", t.options);
		button.setAttribute("aria-haspopup", "menu");
		button.setAttribute("aria-expanded", "false");
		button.innerHTML = iconSvg('<g fill="currentColor"><circle cx="3" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="13" cy="8" r="1.4"/></g>');
		button.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			toggleMenu(cell, block, button);
		});
		return button;
	}

	function bindCellDrop(cell, signature) {
		cell.addEventListener("dragover", (event) => {
			if (!dragSig || dragSig === signature) return;
			event.preventDefault();
			event.stopPropagation();
			if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
			clearDragMarks();
			cell.classList.add("drop-" + dragSide(event, cell).visual);
		});
		cell.addEventListener("dragleave", () => cell.classList.remove("drop-left", "drop-right"));
		cell.addEventListener("drop", (event) => {
			if (!dragSig) return;
			event.preventDefault();
			event.stopPropagation();
			const moved = dragSig;
			const side = dragSide(event, cell).side;
			endDrag();
			moveBlockTo(moved, { type: "cell", signature, side });
		});
	}

	function bindZoneDrop(zone, target) {
		zone.addEventListener("dragover", (event) => {
			if (!dragSig) return;
			event.preventDefault();
			if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
			clearDragMarks();
			zone.classList.add("is-drop-target");
		});
		zone.addEventListener("dragleave", (event) => {
			if (!zone.contains(event.relatedTarget)) zone.classList.remove("is-drop-target");
		});
		zone.addEventListener("drop", (event) => {
			if (!dragSig) return;
			event.preventDefault();
			const moved = dragSig;
			endDrag();
			moveBlockTo(moved, target);
		});
	}

	// "+" asks what to add, then the stock creation dialog runs; Save places the new block
	// in `row` (an existing row number, or one past the last for a new row).
	function startRowAdd(row) {
		normalizeRows();
		openAddDialog(null, { row });
	}

	function rowAddButton(rowIndex) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-row-add";
		button.title = t.rowAdd;
		button.setAttribute("aria-label", t.rowAdd);
		button.innerHTML = plusIcon();
		button.addEventListener("click", (event) => {
			event.preventDefault();
			startRowAdd(rowIndex);
		});
		return button;
	}

	function newRowButton() {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-row-new";
		button.title = t.newRow;
		button.setAttribute("aria-label", t.newRow);
		button.innerHTML = plusIcon() + "<span>" + escapeHtml(t.newRow) + "</span>";
		button.addEventListener("click", (event) => {
			event.preventDefault();
			startRowAdd(currentRows.length);
		});
		bindZoneDrop(button, { type: "new" });
		return button;
	}

	function buildCell(block, pageData, editing) {
		const cell = document.createElement("div");
		cell.className = "nds-nb-cell nds-nb-" + block.type.replace(/_/g, "-");
		cell.dataset.sig = blockSignature(block);
		cell.style.setProperty("--nds-nb-col", String(spanOf(block)));

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
			if (!mounted) return null;
		}
		if (editing) {
			cell.appendChild(handleButton(cell, block));
			cell.appendChild(moreButton(cell, block));
			bindCellDrop(cell, blockSignature(block));
		}
		return cell;
	}

	function renderLayer(host, editing) {
		const ws = workspace();
		const pageData = ws && ws.page_data;
		const rtl = isRtl();

		const pageName = currentPageName();
		if (layoutPage !== pageName) {
			pendingRows.clear();
			pendingCols.clear();
			pendingAdd = null;
			layoutPage = pageName;
		}

		const blocks = layerBlocks(editing);
		if (!blocks.length || !pageData) {
			removeLayer();
			currentRows = [];
			return;
		}

		// Wait until Frappe's page data belongs to the page whose content we read;
		// during a workspace switch the two briefly disagree.
		const current = ws.pages && ws._page ? ws.pages[ws._page.name] : null;
		if (current && current !== pageData) return;

		const rows = buildRows(blocks);
		currentRows = rows.map((row) => row.map(blockSignature));

		const sizes = Object.keys(WIDGET_TYPES).map((type) => {
			const collection = pageData[WIDGET_TYPES[type][0]];
			return collection && Array.isArray(collection.items) ? collection.items.length : 0;
		}).join(",");
		const signature = [
			rtl ? "rtl" : "ltr", editing ? "edit" : "view", sizes, rawContent(),
			JSON.stringify(currentRows), JSON.stringify(Array.from(pendingCols)),
		].join("|");
		const existing = document.getElementById(LAYER_ID);
		if (existing && existing.parentElement === host && existing.dataset.signature === signature) return;
		closeMenu();
		if (existing) existing.remove();

		const layer = document.createElement("section");
		layer.id = LAYER_ID;
		layer.className = "nds-nb" + (editing ? " is-editing" : "");
		layer.dataset.signature = signature;
		layer.setAttribute("dir", rtl ? "rtl" : "ltr");
		layer.setAttribute("lang", rtl ? "ar" : "en");

		const stack = document.createElement("div");
		stack.className = "nds-nb-grid";
		layer.appendChild(stack);
		// Attach before building the widgets: charts size themselves from the DOM.
		host.appendChild(layer);

		rows.forEach((row, rowIndex) => {
			const wrap = document.createElement("div");
			wrap.className = "nds-nb-row-wrap";
			wrap.dataset.row = String(rowIndex);
			const grid = document.createElement("div");
			grid.className = "nds-nb-row";
			wrap.appendChild(grid);
			row.forEach((block) => {
				const cell = buildCell(block, pageData, editing);
				if (cell) grid.appendChild(cell);
			});
			if (!grid.children.length) return;
			if (editing) {
				wrap.appendChild(rowAddButton(rowIndex));
				bindZoneDrop(wrap, { type: "row", index: rowIndex });
			}
			stack.appendChild(wrap);
		});
		if (editing && stack.children.length) stack.appendChild(newRowButton());

		if (!stack.children.length) layer.remove();
	}

	// --- 5. edit-mode controls ---------------------------------------------

	// The blocks the stock Workspace editor offers in its own "+" menu, in its order.
	const STOCK_ADD_TYPES = [
		"header", "paragraph", "card", "shortcut", "chart",
		"number_card", "quick_list", "onboarding", "custom_block", "spacer",
	];
	const STOCK_TITLES = {
		header: "Heading", paragraph: "Text", card: "Card", shortcut: "Shortcut", chart: "Chart",
		number_card: "Number Card", quick_list: "Quick List", onboarding: "Onboarding",
		custom_block: "Custom Block", spacer: "Spacer",
	};
	const anchors = new Map();

	function editorApi() {
		const ws = workspace();
		const editor = ws && ws.editor;
		return editor && editor.blocks && typeof editor.blocks.getBlocksCount === "function" ? editor : null;
	}

	function blockHolders(editor) {
		try {
			const holders = [];
			const count = editor.blocks.getBlocksCount();
			for (let index = 0; index < count; index += 1) {
				const api = editor.blocks.getBlockByIndex(index);
				holders.push(api && api.holder ? api.holder : null);
			}
			return holders;
		} catch (_) {
			return null;
		}
	}

	function cardName(holder) {
		const node = holder && holder.querySelector ? holder.querySelector("[card_name]") : null;
		return node ? node.getAttribute("card_name") : null;
	}

	// A name as stored and as translated: link rows come back from the server translated,
	// while card blocks keep the stored name.
	function nameVariants(name) {
		const out = new Set([normalize(name)]);
		try { out.add(normalize(__(name))); } catch (_) { /* untranslated is fine */ }
		out.delete("");
		return out;
	}

	function labelSet(labels) {
		const set = new Set();
		(labels || []).forEach((label) => nameVariants(label).forEach((value) => set.add(value)));
		return set;
	}

	function matchesLabels(name, set) {
		for (const value of nameVariants(name)) {
			if (set.has(value)) return true;
		}
		return false;
	}

	function findCardIndex(holders, set) {
		return holders.findIndex((holder) => {
			const name = cardName(holder);
			return name != null && matchesLabels(name, set);
		});
	}

	function slotLabels(slot) {
		try {
			const labels = JSON.parse(slot.getAttribute(CARD_ATTR));
			return Array.isArray(labels) ? labels : [];
		} catch (_) {
			return [];
		}
	}

	function slotHint(slot) {
		return slot.getAttribute("data-nds-card-hint") || slotLabels(slot)[0] || "";
	}

	function slotKey(slot) {
		return normalize(slotHint(slot));
	}

	function toggleClass(node, className, on) {
		if (node.classList.contains(className) !== on) node.classList.toggle(className, on);
	}

	function plusIcon() {
		return '<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" focusable="false">' +
			'<path d="M8 3v10M3 8h10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
	}

	// Staged delete: removes the card block from the stock editor. Nothing is stored
	// until the stock Save button runs `save_page`, and Discard restores it.
	async function stageDelete(slot) {
		const editor = editorApi();
		const set = labelSet(slotLabels(slot));
		if (!editor || !set.size) return;
		let holders = blockHolders(editor);
		if (!holders) return;
		let index = findCardIndex(holders, set);
		if (index === -1) return;
		anchors.set(slotKey(slot), holders[index + 1] || null);
		while (index !== -1) {
			await editor.blocks.delete(index);
			holders = blockHolders(editor) || [];
			index = findCardIndex(holders, set);
		}
		schedule();
	}

	// Same steps as the stock "Edit" menu item, so a "+" shown in view mode can start editing.
	async function ensureEditing() {
		const ws = workspace();
		if (!ws || !ws._page || !ws._page.is_editable || !ws.editor) return false;
		if (!ws.is_read_only) return true;
		if (!ws.editor.readOnly || typeof ws.editor.readOnly.toggle !== "function") return false;
		ws.is_read_only = false;
		await ws.editor.readOnly.toggle();
		await ws.editor.isReady;
		ws.setup_customization_buttons(ws._page);
		if (typeof ws.make_blocks_sortable === "function") ws.make_blocks_sortable();
		return true;
	}

	function translate(value) {
		try { return typeof __ === "function" ? __(value) : value; } catch (_) { return value; }
	}

	// Titles come from the stock tools themselves, so the chooser reads exactly like the
	// editor's own "+" menu (and follows its translations).
	function addOptions() {
		const editor = editorApi();
		const tools = (editor && editor.configuration && editor.configuration.tools) || {};
		const known = Object.keys(tools).length > 0;
		return STOCK_ADD_TYPES.filter((type) => !known || tools[type]).map((type) => {
			const tool = tools[type];
			const toolClass = tool && (tool.class || tool);
			const title = toolClass && toolClass.toolbox && toolClass.toolbox.title;
			return { type, label: translate(title || STOCK_TITLES[type]) };
		});
	}

	// A new widget block is complete once its stock creation dialog has filled in the
	// block's name attribute. The stock Save button then runs, so the addition is stored
	// and drawn on the dashboard at once. Closing the dialog removes the block: nothing is saved.
	function saveWhenFilled(holder, type) {
		const spec = WIDGET_TYPES[type];
		const ws = workspace();
		if (!spec || !holder || !ws) return;
		const startedAt = Date.now();
		const watch = window.setInterval(() => {
			if (!holder.isConnected || ws.is_read_only || Date.now() - startedAt > 600000) {
				window.clearInterval(watch);
				return;
			}
			const node = holder.querySelector("[" + spec[2] + "]");
			if (!node || !node.getAttribute(spec[2])) return;
			window.clearInterval(watch);
			window.setTimeout(() => {
				const button = ws.page && ws.page.btn_primary;
				if (button && button.length && !ws.is_read_only) button.trigger("click");
			}, 350);
		}, 300);
	}

	// Inserts an empty block of the chosen type; the stock block then opens its own
	// creation dialog, exactly as when it is picked from the editor toolbox. Nothing is
	// pre-filled: a new block never reuses the name of one that was deleted.
	async function insertBlock(type, key) {
		try {
			if (!(await ensureEditing())) return;
			const editor = editorApi();
			if (!editor) return;
			const holders = blockHolders(editor) || [];
			let index = holders.length;
			const anchor = key ? anchors.get(key) : null;
			if (anchor) {
				const found = holders.indexOf(anchor);
				if (found !== -1) index = found;
			}
			if (key) anchors.delete(key);
			await editor.blocks.insert(type, {}, {}, index, true);
			saveWhenFilled((blockHolders(editor) || [])[index], type);
			schedule();
		} catch (_) { /* the stock editor keeps working */ }
	}

	function openAddDialog(key, context) {
		if (!window.frappe || !frappe.ui || !frappe.ui.Dialog) return;
		const t = text();
		const options = addOptions();
		if (!options.length) return;
		const labels = options.map((option) => option.label);
		const dialog = new frappe.ui.Dialog({
			title: t.addTitle,
			fields: [{
				fieldname: "kind",
				fieldtype: "Select",
				label: t.addKind,
				options: labels.join("\n"),
				default: labels[0],
				reqd: 1,
			}],
			primary_action_label: t.addAction,
			primary_action: (values) => {
				const picked = options[labels.indexOf(values.kind)];
				dialog.hide();
				if (picked && context) pendingAdd = { row: context.row, type: picked.type };
				if (picked) window.setTimeout(() => insertBlock(picked.type, key), 250);
			},
		});
		dialog.show();
	}

	function slotDeleteButton(slot) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-slot-delete";
		button.title = t.remove;
		button.setAttribute("aria-label", t.remove);
		button.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
			'<path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
		button.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			const name = plainText(slotHint(slot));
			frappe.confirm(escapeHtml(text().stageConfirm(name)), () => stageDelete(slot));
		});
		return button;
	}

	function slotAddButton(slot) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-slot-add";
		button.title = t.add;
		button.setAttribute("aria-label", t.add);
		button.innerHTML = plusIcon();
		button.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			openAddDialog(slotKey(slot));
		});
		return button;
	}

	function addTile() {
		const t = text();
		const tile = document.createElement("button");
		tile.type = "button";
		tile.className = "nds-nb-add-tile";
		tile.title = t.add;
		tile.setAttribute("aria-label", t.add);
		tile.innerHTML = plusIcon();
		tile.addEventListener("click", (event) => {
			event.preventDefault();
			openAddDialog(null);
		});
		return tile;
	}

	function ensureChild(slot, className, build) {
		if (!slot.querySelector(":scope > ." + className)) slot.appendChild(build(slot));
	}

	function dropChild(slot, className) {
		const child = slot.querySelector(":scope > ." + className);
		if (child) child.remove();
	}

	function clearSlot(slot) {
		toggleClass(slot, "nds-nb-slot-empty", false);
		dropChild(slot, "nds-nb-slot-delete");
		dropChild(slot, "nds-nb-slot-add");
	}

	function syncAddTile(host, show) {
		const grid = host.querySelector("[data-nds-add-grid]");
		let tile = host.querySelector(".nds-nb-add-tile");
		if (!show) {
			if (tile) tile.remove();
			return;
		}
		if (tile && grid && tile.parentElement !== grid) {
			tile.remove();
			tile = null;
		}
		if (!tile) tile = addTile();
		if (grid) {
			toggleClass(tile, "is-bar", false);
			if (grid.lastElementChild !== tile) grid.appendChild(tile);
			return;
		}
		toggleClass(tile, "is-bar", true);
		const anchor = host.querySelector(".editor-js-container");
		const parent = anchor ? anchor.parentNode : host;
		if (tile.parentNode !== parent || (anchor && tile.nextElementSibling !== anchor)) {
			parent.insertBefore(tile, anchor || null);
		}
	}

	// Edit mode only: a delete button on every workspace-backed card, a "+" placeholder where
	// a card is missing, and the "+" tile that ends the sections. View mode shows none of
	// them. Everything is added only when absent so the DOM observers settle.
	function decorate(host, editing) {
		const ws = workspace();
		const editable = Boolean(ws && ws._page && ws._page.is_editable);
		const editor = editable ? editorApi() : null;
		const holders = editor ? blockHolders(editor) : null;
		const known = Boolean(holders && holders.some((holder) => cardName(holder) != null));
		host.querySelectorAll("[" + CARD_ATTR + "]").forEach((slot) => {
			if (!known) {
				clearSlot(slot);
				return;
			}
			const labels = slotLabels(slot);
			const exists = labels.length > 0 && findCardIndex(holders, labelSet(labels)) !== -1;
			toggleClass(slot, "nds-nb-slot-empty", !exists);
			if (exists) {
				dropChild(slot, "nds-nb-slot-add");
				dropChild(slot, "nds-nb-slot-delete");
			} else {
				dropChild(slot, "nds-nb-slot-delete");
				ensureChild(slot, "nds-nb-slot-add", slotAddButton);
			}
		});
		syncAddTile(host, Boolean(editing && holders));
	}

	// View mode: the sections are drawn exactly as the dashboard builds them.
	function clearSlots(host) {
		host.querySelectorAll("[" + CARD_ATTR + "]").forEach(clearSlot);
		host.querySelectorAll(".nds-nb-add-tile").forEach((tile) => tile.remove());
	}

	function clearDecorations() {
		document.querySelectorAll("#page-Workspaces [" + CARD_ATTR + "]").forEach(clearSlot);
		document.querySelectorAll("#page-Workspaces .nds-nb-add-tile").forEach((tile) => tile.remove());
	}

	// --- 6. fixed widgets: KPI cards, charts and tables ---------------------
	//
	// Every dashboard draws its KPI cards, chart panels and latest-documents table in
	// code, so none of them is a Workspace block. They get the same Edit-mode controls
	// as the section cards: "x" hides one (staged), a dashed "+" shows where it was and
	// brings it back. The hidden ids ride along on the first block of the saved
	// Workspace content (`data.nds_hidden`), exactly like the "new block" tag, so they
	// are stored by the stock Save button and thrown away by Discard.

	const HIDDEN_KEY = "nds_hidden";
	const WIDGET_ATTR = "data-nds-widget";
	const KPI_SELECTOR = '[class*="-kpi-card"][data-kpi]';
	const PANEL_SELECTOR = ".nds-sales-panel, .nds-purchase-panel, .nds-warehouse-panel, .nds-accounts-panel, .nds-assets-panel, .nds-hr-panel";

	let pendingHidden = null;
	let pendingPage = null;
	let hiddenCache = { raw: null, ids: new Set() };

	function parseHidden(raw) {
		const ids = new Set();
		(parseContent(raw) || []).forEach((block) => {
			const value = block && block.data ? block.data[HIDDEN_KEY] : null;
			if (typeof value !== "string") return;
			value.split(",").forEach((id) => {
				const clean = id.trim();
				if (clean) ids.add(clean);
			});
		});
		return ids;
	}

	function savedHidden() {
		const raw = rawContent();
		if (raw !== hiddenCache.raw) hiddenCache = { raw, ids: parseHidden(raw) };
		return hiddenCache.ids;
	}

	function currentPageName() {
		const ws = workspace();
		return ws && ws._page ? ws._page.name || null : null;
	}

	// Staged ids while editing, otherwise the saved ones. A staged set never leaks
	// onto another workspace page.
	function effectiveHidden() {
		if (pendingHidden && pendingPage !== currentPageName()) pendingHidden = null;
		return pendingHidden || savedHidden();
	}

	function setWidgetHidden(id, hide) {
		const next = new Set(effectiveHidden());
		if (hide) next.add(id);
		else next.delete(id);
		pendingHidden = next;
		pendingPage = currentPageName();
		schedule();
	}

	// Called while the stock editor saves: writes the ids onto the first block.
	function writeHidden(output, previousRaw) {
		if (!output || !Array.isArray(output.blocks)) return;
		const ids = pendingHidden && pendingPage === currentPageName() ? pendingHidden : parseHidden(previousRaw);
		output.blocks.forEach((block) => {
			if (block && block.data) delete block.data[HIDDEN_KEY];
		});
		if (!ids.size) return;
		const first = output.blocks.find((block) => block && block.data);
		if (first) first.data[HIDDEN_KEY] = Array.from(ids).sort().join(",");
	}

	function tagWidgets(host) {
		host.querySelectorAll(KPI_SELECTOR).forEach((node) => {
			const id = "kpi:" + node.getAttribute("data-kpi");
			if (node.getAttribute(WIDGET_ATTR) !== id) node.setAttribute(WIDGET_ATTR, id);
		});
		// Panels have no unique class of their own, so their position is the id. Hidden
		// panels stay in the DOM, which keeps the positions stable.
		let index = 0;
		host.querySelectorAll(PANEL_SELECTOR).forEach((node) => {
			if (node.parentElement && node.parentElement.closest("[" + WIDGET_ATTR + "]")) return;
			const id = "panel:" + index;
			index += 1;
			if (node.getAttribute(WIDGET_ATTR) !== id) node.setAttribute(WIDGET_ATTR, id);
		});
	}

	function widgetLabel(node) {
		const heading = node.querySelector('[class*="-kpi-label"], h2, h3');
		return plainText(heading ? heading.textContent : "") || node.getAttribute(WIDGET_ATTR) || "";
	}

	function widgetDeleteButton(node) {
		const button = slotDeleteButton(node);
		const fresh = button.cloneNode(true);
		fresh.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			const id = node.getAttribute(WIDGET_ATTR);
			frappe.confirm(escapeHtml(text().stageConfirm(widgetLabel(node))), () => setWidgetHidden(id, true));
		});
		return fresh;
	}

	function widgetAddButton(node) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-slot-add";
		button.title = t.add;
		button.setAttribute("aria-label", t.add);
		button.innerHTML = plusIcon();
		button.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			openAddDialog(null);
		});
		return button;
	}

	function decorateWidgets(host, editing) {
		tagWidgets(host);
		// Controls and placeholders exist in Edit mode only; the dashboard itself just
		// leaves a deleted widget out.
		const editable = Boolean(editing) && canEdit();
		const hidden = effectiveHidden();
		host.querySelectorAll("[" + WIDGET_ATTR + "]").forEach((node) => {
			if (!hidden.has(node.getAttribute(WIDGET_ATTR))) {
				toggleClass(node, "nds-widget-gone", false);
				toggleClass(node, "nds-nb-slot-empty", false);
				dropChild(node, "nds-nb-slot-add");
				dropChild(node, "nds-nb-slot-delete");
				return;
			}
			dropChild(node, "nds-nb-slot-delete");
			if (!editable) {
				toggleClass(node, "nds-widget-gone", true);
				toggleClass(node, "nds-nb-slot-empty", false);
				dropChild(node, "nds-nb-slot-add");
				return;
			}
			toggleClass(node, "nds-widget-gone", false);
			toggleClass(node, "nds-nb-slot-empty", true);
			ensureChild(node, "nds-nb-slot-add", widgetAddButton);
		});
	}

	function clearWidgets() {
		pendingHidden = null;
		pendingLayout = null;
		clearLayout(document);
		document.querySelectorAll("#page-Workspaces [" + WIDGET_ATTR + "]").forEach((node) => {
			toggleClass(node, "nds-widget-gone", false);
			clearSlot(node);
		});
	}

	// --- 7. layout of the fixed widgets: lanes, drag, "..." menu, "+" ---------
	//
	// KPI cards, chart panels, the latest-documents table and the dashboards' section cards
	// get the same Edit-mode controls as the new-block layer: a drag handle, a "..." menu
	// (Wider / Narrower / Move earlier / Move later / Delete) and a "+" that ends every lane.
	// A lane is the container a group of such widgets sits in. Order and width are applied
	// with CSS (`order`, `grid-column`), never by moving DOM nodes, so the dashboards can
	// rebuild themselves at any time. Both ride along on the first block of the saved
	// Workspace content (`data.nds_layout`), exactly like `nds_hidden`: the stock Save
	// button stores them and Discard / reload throws the staged change away.
	// Order needs a grid or flex lane; a plain block container keeps only Delete.

	const LAYOUT_KEY = "nds_layout";
	const MOVABLE_SELECTOR = "[" + WIDGET_ATTR + "], [" + CARD_ATTR + "]";

	let pendingLayout = null;
	let pendingLayoutPage = null;
	let layoutCache = { raw: null, layout: { o: {}, w: {} } };
	let dragWidget = null;

	function emptyLayout() {
		return { o: {}, w: {} };
	}

	function cloneLayout(layout) {
		const copy = emptyLayout();
		Object.keys(layout.o).forEach((key) => { copy.o[key] = layout.o[key].slice(); });
		Object.keys(layout.w).forEach((key) => { copy.w[key] = layout.w[key]; });
		return copy;
	}

	function parseLayout(raw) {
		const layout = emptyLayout();
		(parseContent(raw) || []).forEach((block) => {
			const value = block && block.data ? block.data[LAYOUT_KEY] : null;
			if (typeof value !== "string" || !value) return;
			try {
				const parsed = JSON.parse(value);
				if (parsed && parsed.o && typeof parsed.o === "object") {
					Object.keys(parsed.o).forEach((key) => {
						if (Array.isArray(parsed.o[key])) layout.o[key] = parsed.o[key].map(String);
					});
				}
				if (parsed && parsed.w && typeof parsed.w === "object") {
					Object.keys(parsed.w).forEach((key) => {
						const span = parseInt(parsed.w[key], 10);
						if (Number.isFinite(span) && span >= 1 && span <= 12) layout.w[key] = span;
					});
				}
			} catch (_) { /* a damaged value is ignored */ }
		});
		return layout;
	}

	function savedLayout() {
		const raw = rawContent();
		if (raw !== layoutCache.raw) layoutCache = { raw, layout: parseLayout(raw) };
		return layoutCache.layout;
	}

	function effectiveLayout() {
		if (pendingLayout && pendingLayoutPage !== currentPageName()) pendingLayout = null;
		return pendingLayout || savedLayout();
	}

	function changeLayout(mutate) {
		const next = cloneLayout(effectiveLayout());
		mutate(next);
		pendingLayout = next;
		pendingLayoutPage = currentPageName();
		schedule();
	}

	// Called while the stock editor saves: writes the layout onto the first block.
	function writeLayout(output, previousRaw) {
		if (!output || !Array.isArray(output.blocks)) return;
		const layout = pendingLayout && pendingLayoutPage === currentPageName() ? pendingLayout : parseLayout(previousRaw);
		output.blocks.forEach((block) => {
			if (block && block.data) delete block.data[LAYOUT_KEY];
		});
		if (!Object.keys(layout.o).length && !Object.keys(layout.w).length) return;
		const first = output.blocks.find((block) => block && block.data);
		if (first) first.data[LAYOUT_KEY] = JSON.stringify(layout);
	}

	function movableId(node) {
		if (node.hasAttribute(WIDGET_ATTR)) return node.getAttribute(WIDGET_ATTR);
		return "card:" + slotKey(node);
	}

	function movableNodes(host) {
		return Array.from(host.querySelectorAll(MOVABLE_SELECTOR)).filter((node) => {
			const outer = node.parentElement ? node.parentElement.closest(MOVABLE_SELECTOR) : null;
			return !outer && (node.hasAttribute(WIDGET_ATTR) || slotKey(node));
		});
	}

	// Groups the widgets by their container, in document order. Lane numbers are positions,
	// which stay stable because order is applied with CSS and nodes are never moved.
	function collectLanes(host) {
		const lanes = [];
		movableNodes(host).forEach((node) => {
			const parent = node.parentElement;
			if (!parent) return;
			let lane = lanes.find((candidate) => candidate.parent === parent);
			if (!lane) {
				lane = { parent, index: lanes.length, nodes: [] };
				lanes.push(lane);
			}
			lane.nodes.push(node);
		});
		return lanes;
	}

	function laneKind(parent) {
		const display = window.getComputedStyle(parent).display || "";
		if (display.indexOf("grid") !== -1) return "grid";
		if (display.indexOf("flex") !== -1) return "flex";
		return "block";
	}

	function laneColumns(parent) {
		if (laneKind(parent) !== "grid") return 0;
		const tracks = String(window.getComputedStyle(parent).gridTemplateColumns || "").split(/\s+/).filter(Boolean);
		return tracks.length;
	}

	// Widget ids of a lane in the order they are shown: the stored order first, then any
	// widget the stored order does not know yet, in document order.
	function laneOrder(lane, layout) {
		const present = lane.nodes.map(movableId);
		const stored = (layout.o["L" + lane.index] || []).filter((id) => present.includes(id));
		return stored.concat(present.filter((id) => !stored.includes(id)));
	}

	function parseSpan(node) {
		const end = String(window.getComputedStyle(node).gridColumnEnd || "");
		const match = end.match(/span\s+(\d+)/);
		return match ? parseInt(match[1], 10) : 1;
	}

	function applyLane(lane, layout) {
		const kind = laneKind(lane.parent);
		const order = laneOrder(lane, layout);
		const byId = new Map(lane.nodes.map((node) => [movableId(node), node]));
		// The widgets swap places among themselves; everything else in the lane (the "+"
		// tile, other content) keeps its own position.
		const children = Array.from(lane.parent.children);
		const slots = children.filter((child) => lane.nodes.includes(child));
		const shown = new Map();
		slots.forEach((child, index) => shown.set(byId.get(order[index]), children.indexOf(child)));
		children.forEach((child, index) => {
			const position = shown.has(child) ? shown.get(child) : index;
			const value = kind === "block" ? "" : String(position);
			if (child.style.order !== value) child.style.order = value;
		});
		const columns = laneColumns(lane.parent);
		lane.nodes.forEach((node) => {
			const span = layout.w[movableId(node)];
			const value = span && columns ? "span " + Math.min(span, columns) : "";
			if (node.style.gridColumn !== value) node.style.gridColumn = value;
		});
	}

	function moveWithin(lane, id, to) {
		changeLayout((layout) => {
			const order = laneOrder(lane, layout).filter((item) => item !== id);
			order.splice(Math.max(0, Math.min(order.length, to)), 0, id);
			layout.o["L" + lane.index] = order;
		});
	}

	function resizeWidget(lane, node, direction) {
		const columns = laneColumns(lane.parent);
		if (!columns) return;
		const id = movableId(node);
		const now = effectiveLayout().w[id] || parseSpan(node);
		const next = Math.max(1, Math.min(columns, now + direction));
		changeLayout((layout) => { layout.w[id] = next; });
	}

	function deleteWidget(node) {
		if (node.hasAttribute(WIDGET_ATTR)) {
			const id = node.getAttribute(WIDGET_ATTR);
			frappe.confirm(escapeHtml(text().stageConfirm(widgetLabel(node))), () => setWidgetHidden(id, true));
			return;
		}
		frappe.confirm(escapeHtml(text().stageConfirm(plainText(slotHint(node)))), () => stageDelete(node));
	}

	function laneOf(node) {
		const host = dashboardHost();
		if (!host) return null;
		return collectLanes(host).find((lane) => lane.parent === node.parentElement) || null;
	}

	function placeFloatingMenu(menu, button) {
		const rect = button.getBoundingClientRect();
		const width = menu.offsetWidth || 160;
		const height = menu.offsetHeight || 160;
		let left = isRtl() ? rect.left : rect.right - width;
		left = Math.max(8, Math.min(window.innerWidth - width - 8, left));
		let top = rect.bottom + 6;
		if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 6);
		menu.style.left = left + "px";
		menu.style.top = top + "px";
	}

	function toggleWidgetMenu(node, button) {
		const wasOpen = Boolean(openMenu) && openMenu.parentElement === node;
		closeMenu();
		if (wasOpen) return;
		const t = text();
		const lane = laneOf(node);
		const menu = document.createElement("div");
		menu.className = "nds-nb-menu is-floating";
		menu.setAttribute("role", "menu");
		if (lane) {
			const id = movableId(node);
			const order = laneOrder(lane, effectiveLayout());
			const at = order.indexOf(id);
			if (laneKind(lane.parent) !== "block" && order.length > 1) {
				if (at > 0) menu.appendChild(menuItem(t.earlier, () => moveWithin(lane, id, at - 1)));
				if (at < order.length - 1) menu.appendChild(menuItem(t.later, () => moveWithin(lane, id, at + 1)));
			}
			if (laneColumns(lane.parent) > 1) {
				menu.appendChild(menuItem(t.wider, () => resizeWidget(lane, node, 1)));
				menu.appendChild(menuItem(t.narrower, () => resizeWidget(lane, node, -1)));
			}
		}
		menu.appendChild(menuItem(t.remove, () => deleteWidget(node), true));
		node.appendChild(menu);
		placeFloatingMenu(menu, button);
		button.setAttribute("aria-expanded", "true");
		openMenu = menu;
	}

	function widgetMoreButton(node) {
		const button = moreButton(node, null);
		const fresh = button.cloneNode(true);
		fresh.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			toggleWidgetMenu(node, fresh);
		});
		return fresh;
	}

	function dropSide(event, target) {
		const rect = target.getBoundingClientRect();
		const source = dragWidget
			? Array.from(document.querySelectorAll(MOVABLE_SELECTOR)).find((candidate) => movableId(candidate) === dragWidget.id)
			: null;
		const from = source ? source.getBoundingClientRect() : null;
		const stacked = from && (rect.top >= from.bottom - 2 || rect.bottom <= from.top + 2);
		if (stacked) {
			const upper = event.clientY < rect.top + rect.height / 2;
			return { visual: upper ? "top" : "bottom", side: upper ? "before" : "after" };
		}
		const left = event.clientX < rect.left + rect.width / 2;
		return { visual: left ? "left" : "right", side: left === !isRtl() ? "before" : "after" };
	}

	function clearWidgetDragMarks() {
		document.querySelectorAll(".nds-wd-top, .nds-wd-bottom, .nds-wd-left, .nds-wd-right")
			.forEach((node) => node.classList.remove("nds-wd-top", "nds-wd-bottom", "nds-wd-left", "nds-wd-right"));
	}

	function endWidgetDrag() {
		dragWidget = null;
		clearWidgetDragMarks();
		document.querySelectorAll(".nds-wd-dragging").forEach((node) => node.classList.remove("nds-wd-dragging"));
	}

	function bindWidgetDrop(node) {
		if (node.__ndsWidgetDrop) return;
		node.__ndsWidgetDrop = true;
		node.addEventListener("dragover", (event) => {
			if (!dragWidget || dragWidget.parent !== node.parentElement || movableId(node) === dragWidget.id) return;
			event.preventDefault();
			event.stopPropagation();
			if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
			clearWidgetDragMarks();
			node.classList.add("nds-wd-" + dropSide(event, node).visual);
		});
		node.addEventListener("dragleave", (event) => {
			if (!node.contains(event.relatedTarget)) clearWidgetDragMarks();
		});
		node.addEventListener("drop", (event) => {
			if (!dragWidget || dragWidget.parent !== node.parentElement) return;
			event.preventDefault();
			event.stopPropagation();
			const moved = dragWidget.id;
			const side = dropSide(event, node).side;
			const targetId = movableId(node);
			endWidgetDrag();
			if (moved === targetId) return;
			const lane = laneOf(node);
			if (!lane) return;
			const order = laneOrder(lane, effectiveLayout()).filter((id) => id !== moved);
			const at = order.indexOf(targetId);
			if (at === -1) return;
			moveWithin(lane, moved, at + (side === "after" ? 1 : 0));
		});
	}

	function widgetHandle(node) {
		const t = text();
		const handle = document.createElement("span");
		handle.className = "nds-nb-handle";
		handle.setAttribute("role", "button");
		handle.setAttribute("tabindex", "-1");
		handle.setAttribute("draggable", "true");
		handle.title = t.drag;
		handle.setAttribute("aria-label", t.drag);
		handle.innerHTML = iconSvg('<g fill="currentColor"><circle cx="5.5" cy="4" r="1.3"/><circle cx="10.5" cy="4" r="1.3"/><circle cx="5.5" cy="8" r="1.3"/><circle cx="10.5" cy="8" r="1.3"/><circle cx="5.5" cy="12" r="1.3"/><circle cx="10.5" cy="12" r="1.3"/></g>');
		handle.addEventListener("dragstart", (event) => {
			closeMenu();
			dragWidget = { id: movableId(node), parent: node.parentElement };
			node.classList.add("nds-wd-dragging");
			if (event.dataTransfer) {
				event.dataTransfer.effectAllowed = "move";
				try { event.dataTransfer.setData("text/plain", dragWidget.id); } catch (_) { /* optional */ }
				try { event.dataTransfer.setDragImage(node, 24, 24); } catch (_) { /* optional */ }
			}
		});
		handle.addEventListener("dragend", endWidgetDrag);
		return handle;
	}

	function laneAddButton() {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-lane-add";
		button.title = t.laneAdd;
		button.setAttribute("aria-label", t.laneAdd);
		button.innerHTML = plusIcon();
		button.addEventListener("click", (event) => {
			event.preventDefault();
			openAddDialog(null);
		});
		return button;
	}

	function clearLayout(root) {
		root.querySelectorAll("#page-Workspaces .nds-nb-lane-add, #page-Workspaces [" + WIDGET_ATTR + "] > .nds-nb-handle, #page-Workspaces [" + WIDGET_ATTR + "] > .nds-nb-more, #page-Workspaces [" + CARD_ATTR + "] > .nds-nb-handle, #page-Workspaces [" + CARD_ATTR + "] > .nds-nb-more")
			.forEach((node) => node.remove());
		root.querySelectorAll("#page-Workspaces [data-nds-lane]").forEach((lane) => {
			lane.removeAttribute("data-nds-lane");
			Array.from(lane.children).forEach((child) => {
				if (child.style.order) child.style.order = "";
				if (child.style.gridColumn && (child.hasAttribute(WIDGET_ATTR) || child.hasAttribute(CARD_ATTR))) child.style.gridColumn = "";
			});
		});
	}

	function decorateLayout(host, editing) {
		const layout = effectiveLayout();
		const editable = Boolean(editing) && canEdit();
		const lanes = collectLanes(host);
		lanes.forEach((lane) => {
			lane.parent.setAttribute("data-nds-lane", String(lane.index));
			applyLane(lane, layout);
			const movable = laneKind(lane.parent) !== "block";
			let visible = 0;
			lane.nodes.forEach((node) => {
				const idle = node.classList.contains("nds-nb-slot-empty") || node.classList.contains("nds-widget-gone");
				if (!idle) visible += 1;
				const show = editable && !idle;
				if (show) {
					if (movable) {
						ensureChild(node, "nds-nb-handle", widgetHandle);
						bindWidgetDrop(node);
					} else {
						dropChild(node, "nds-nb-handle");
					}
					ensureChild(node, "nds-nb-more", widgetMoreButton);
				} else {
					dropChild(node, "nds-nb-handle");
					dropChild(node, "nds-nb-more");
				}
			});
			if (editable && movable && visible) {
				ensureChild(lane.parent, "nds-nb-lane-add", laneAddButton);
			} else {
				dropChild(lane.parent, "nds-nb-lane-add");
			}
		});
		// Lanes that no longer hold any widget lose their controls.
		host.querySelectorAll(".nds-nb-lane-add").forEach((button) => {
			const parent = button.parentElement;
			if (!parent || !lanes.some((lane) => lane.parent === parent)) button.remove();
		});
	}


	// --- driver ------------------------------------------------------------

	function sync() {
		try {
			patchWorkspace();
			patchReload();
			const host = dashboardHost();
			if (!host) {
				removeLayer();
				clearDecorations();
				clearWidgets();
				return;
			}
			if (isEditMode(host)) {
				markNative();
				renderLayer(host, true);
				decorate(host, true);
				decorateWidgets(host, true);
				decorateLayout(host, true);
				return;
			}
			markNative();
			renderLayer(host, false);
			clearSlots(host);
			decorateWidgets(host, false);
			decorateLayout(host, false);
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
			// The row "..." menu closes on any click outside it and on Escape.
			document.addEventListener("click", (event) => {
				const target = event.target;
				if (openMenu && !openMenu.contains(target) && !(target && target.closest && target.closest(".nds-nb-more"))) closeMenu();
			}, true);
			document.addEventListener("keydown", (event) => {
				if (event.key === "Escape") closeMenu();
			});
			window.addEventListener("scroll", () => {
				if (openMenu && openMenu.classList.contains("is-floating")) closeMenu();
			}, true);
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

	return { mount: install, isNativeNew, flaggedCardLabels, registerFixedCards, CARD_ATTR };
})();

export { newBlocks };
