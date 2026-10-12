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

	// Same rule Frappe applies on save: the two injected "Custom ..." cards are
	// display-only and are never written back into the Workspace content.
	function isInjectedCard(block) {
		const name = block && block.type === "card" && block.data ? block.data.card_name : "";
		return name === "Custom Documents" || name === "Custom Reports";
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
			if (flagged && !isFixedCard(block)) block.data[FLAG] = 1;
			else delete block.data[FLAG];
		});
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

	// --- 4. deleting -------------------------------------------------------

	let deleting = false;

	// Removes one tagged block from the saved Workspace content through Frappe's
	// own `save_page` endpoint (same call and permission check as the stock Save).
	// The server's clean-up then drops the matching shortcut / chart / number card /
	// link rows, and `reload()` re-renders the page so the block disappears at once.
	function removeBlock(block) {
		const ws = workspace();
		const page = ws && ws._page;
		const t = text();
		if (deleting || !page || !page.is_editable || !window.frappe) return;

		const signature = blockSignature(block);
		const content = (parseContent(rawContent()) || []).filter((item) => !isInjectedCard(item));
		const index = content.findIndex((item) =>
			item && item.data && Number(item.data[FLAG]) === 1 && blockSignature(item) === signature
		);
		if (index === -1) return;
		content.splice(index, 1);

		deleting = true;
		frappe.call({
			method: "frappe.desk.doctype.workspace.workspace.save_page",
			args: {
				name: page.name,
				public: page.public || 0,
				new_widgets: {},
				blocks: JSON.stringify(content),
			},
			freeze: true,
			callback: (response) => {
				deleting = false;
				if (!response || !response.message) return;
				try { page.content = JSON.stringify(content); } catch (_) { /* reload refetches it */ }
				flaggedCache = { raw: null, blocks: [] };
				removeLayer();
				Promise.resolve(ws.reload()).catch(() => {});
				frappe.show_alert({ message: t.done, indicator: "green" });
			},
			error: () => {
				deleting = false;
				frappe.show_alert({ message: t.failed, indicator: "red" });
			},
		});
	}

	function deleteButton(block) {
		const t = text();
		const button = document.createElement("button");
		button.type = "button";
		button.className = "nds-nb-delete";
		button.title = t.remove;
		button.setAttribute("aria-label", t.remove);
		button.innerHTML = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
			'<path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
		button.addEventListener("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			const name = plainText(blockName(block));
			frappe.confirm(escapeHtml(t.confirm(name)), () => removeBlock(block));
		});
		return button;
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
		const editable = canEdit();
		const signature = (rtl ? "rtl" : "ltr") + "|" + (editable ? "edit" : "view") + "|" + sizes + "|" + rawContent();
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
			if (editable) cell.appendChild(deleteButton(block));
			grid.appendChild(cell);
		});

		if (!grid.children.length) layer.remove();
	}

	// --- 5. edit-mode controls ---------------------------------------------

	const ADD_TYPES = ["card", "shortcut", "number_card", "chart", "quick_list"];
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

	function prefillLabel(hint) {
		let tries = 0;
		const attempt = () => {
			const dialog = window.cur_dialog;
			const field = dialog && typeof dialog.get_field === "function" ? dialog.get_field("label") : null;
			if (field) {
				if (!dialog.get_value("label")) dialog.set_value("label", hint);
				return;
			}
			tries += 1;
			if (tries < 10) window.setTimeout(attempt, 80);
		};
		window.setTimeout(attempt, 80);
	}

	// Inserts an empty block of the chosen type; the stock block then opens its own
	// creation dialog, exactly as when it is picked from the editor toolbox.
	async function insertBlock(type, key, hint) {
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
			if (type === "card" && hint) prefillLabel(hint);
			schedule();
		} catch (_) { /* the stock editor keeps working */ }
	}

	function openAddDialog(key, hint) {
		if (!window.frappe || !frappe.ui || !frappe.ui.Dialog) return;
		const t = text();
		const labels = ADD_TYPES.map((type) => t.types[type]);
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
				const type = ADD_TYPES[labels.indexOf(values.kind)];
				dialog.hide();
				if (type) window.setTimeout(() => insertBlock(type, key, hint), 250);
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
			openAddDialog(slotKey(slot), slotHint(slot));
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
			openAddDialog(null, "");
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

	// Edit mode: delete button on every workspace-backed card. Any mode, for people who may
	// edit: a "+" placeholder where a card is missing. Edit mode only: the "+" tile that ends
	// the sections. Everything is added only when absent so the DOM observers settle.
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
				if (editing) ensureChild(slot, "nds-nb-slot-delete", slotDeleteButton);
				else dropChild(slot, "nds-nb-slot-delete");
			} else {
				dropChild(slot, "nds-nb-slot-delete");
				ensureChild(slot, "nds-nb-slot-add", slotAddButton);
			}
		});
		syncAddTile(host, Boolean(editing && holders));
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
	const PANEL_SELECTOR = ".nds-sales-panel, .nds-purchase-panel, .nds-warehouse-panel, .nds-accounts-panel";

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
			const id = node.getAttribute(WIDGET_ATTR);
			ensureEditing().then((ok) => { if (ok) setWidgetHidden(id, false); }).catch(() => {});
		});
		return button;
	}

	function decorateWidgets(host, editing) {
		tagWidgets(host);
		const editable = canEdit();
		const hidden = effectiveHidden();
		host.querySelectorAll("[" + WIDGET_ATTR + "]").forEach((node) => {
			if (!hidden.has(node.getAttribute(WIDGET_ATTR))) {
				toggleClass(node, "nds-widget-gone", false);
				toggleClass(node, "nds-nb-slot-empty", false);
				dropChild(node, "nds-nb-slot-add");
				if (editing && editable) ensureChild(node, "nds-nb-slot-delete", widgetDeleteButton);
				else dropChild(node, "nds-nb-slot-delete");
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
		document.querySelectorAll("#page-Workspaces [" + WIDGET_ATTR + "]").forEach((node) => {
			toggleClass(node, "nds-widget-gone", false);
			clearSlot(node);
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
				removeLayer();
				decorate(host, true);
				decorateWidgets(host, true);
				return;
			}
			markNative();
			renderLayer(host);
			decorate(host, false);
			decorateWidgets(host, false);
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

	return { mount: install, isNativeNew, flaggedCardLabels, registerFixedCards, CARD_ATTR };
})();

export { newBlocks };
