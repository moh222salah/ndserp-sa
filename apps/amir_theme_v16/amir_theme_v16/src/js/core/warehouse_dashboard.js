/*
 * NDS ERP Saudi — Warehouse Workspace dashboard.
 * UI-only. Reads inventory through standard Frappe list APIs and never writes records.
 */
const warehouseDashboard = (() => {
  "use strict";
  const ID = "nds-warehouse-dashboard";
  const READY = "nds-warehouse-dashboard-ready";
  const TARGETS = ["مخازن NDS ERP", "المخازن NDS ERP", "لوحة المخازن", "Warehouse Dashboard", "Warehouses NDS ERP", "NDS ERP Warehouses"];
  let installed = false, domObserver = null, langObserver = null, observedBody = null, timers = [];
  const TXT = {
    ar: {
      title:"لوحة المخازن",module:"المخازن",overview:"نظرة عامة",period:"آخر 6 أشهر",
      value:"قيمة المخزون الحالية",warehouses:"المستودعات النشطة",items:"الأصناف المخزنية النشطة",shortages:"حالات نقص المخزون",
      movement:"حركة المخزون — وارد مقابل صادر",movementNote:"الكميات المسجلة خلال آخر 6 أشهر",incoming:"وارد",outgoing:"صادر",
      distribution:"التوزيع حسب المستودع",distributionNote:"قيمة المخزون حسب المستودع",
      reorder:"أصناف بحاجة لإعادة الطلب",reorderNote:"أصناف ذات كمية متوقعة سالبة وفق سجلات المخزون",
      item:"الصنف",warehouse:"المستودع",actual:"الكمية الفعلية",projected:"الكمية المتوقعة",uom:"الوحدة",
      navigation:"أقسام المخازن",navigationNote:"روابط مباشرة مأخوذة من أقسام الصفحة الأصلية.",homeSection:"الرئيسية",reportsSection:"التقارير المخزنية",movementsSection:"الحركات المخزنية",noNavigationLinks:"لا توجد روابط متاحة في القسم الأصلي لهذا القسم.",
      source:"من بيانات المخزون المسجلة",loading:"جارٍ تحميل البيانات...",
      unavailable:"تعذّر تحميل البيانات بسبب الصلاحيات أو الاتصال.",
      noMovement:"لا توجد حركة مخزون مسجلة خلال الفترة المحددة.",noDistribution:"لا توجد قيمة مخزون متاحة للعرض.",
      noShortages:"لا توجد حالات نقص مخزون مسجلة حاليًا."
    },
    en: {
      title:"Warehouse Dashboard",module:"Warehouses",overview:"Overview",period:"Last 6 months",
      value:"Current Stock Value",warehouses:"Active Warehouses",items:"Active Stock Items",shortages:"Stock Shortage Cases",
      movement:"Stock Movement — Incoming vs Outgoing",movementNote:"Recorded quantities over the last 6 months",incoming:"Incoming",outgoing:"Outgoing",
      distribution:"Distribution by Warehouse",distributionNote:"Stock value by warehouse",
      reorder:"Items Requiring Reorder",reorderNote:"Items with negative projected quantity in stock records",
      item:"Item",warehouse:"Warehouse",actual:"Actual Qty",projected:"Projected Qty",uom:"UOM",
      navigation:"Warehouse Sections",navigationNote:"Direct links sourced from the original workspace sections.",homeSection:"Home",reportsSection:"Stock Reports",movementsSection:"Stock Movements",noNavigationLinks:"No links are available in the original section.",
      source:"From recorded inventory data",loading:"Loading data...",
      unavailable:"Data could not be loaded due to permissions or connectivity.",
      noMovement:"No stock movement was recorded during this period.",noDistribution:"No stock value is available to display.",
      noShortages:"No stock shortage cases are currently recorded."
    }
  };
  function t() {
    const lang = String((window.frappe && frappe.boot && frappe.boot.lang) ||
      (document.documentElement && document.documentElement.getAttribute("lang")) || "en").toLowerCase();
    return TXT[lang.startsWith("ar") ? "ar" : "en"];
  }
  function norm(value) { return String(value || "").trim().toLowerCase().replace(/[_\s]+/g, "-"); }
  function isTarget() {
    try {
      const route = frappe.get_route();
      if (!Array.isArray(route) || String(route[0] || "").toLowerCase() !== "workspaces") return false;
      const expected = new Set();
      TARGETS.forEach((name) => {
        expected.add(norm(name));
        try { if (frappe.router && frappe.router.slug) expected.add(norm(frappe.router.slug(name))); } catch (_) {}
      });
      const sidebar = frappe.app && frappe.app.sidebar && frappe.app.sidebar.sidebar_title;
      const heading = document.querySelector("#page-Workspaces .workspace-title, .workspace-title")?.textContent || "";
      return [route[1], sidebar, heading].some((v) => expected.has(norm(v)));
    } catch (_) { return false; }
  }
  function setDirection(board) {
    const language = t() === TXT.ar ? "ar" : "en";
    const direction = language === "ar" ? "rtl" : "ltr";
    board.setAttribute("lang", language);
    board.setAttribute("dir", direction);

    // Apply the language direction to the whole active Workspace, not just
    // the injected dashboard; remember the previous value for clean teardown.
    const page = document.querySelector("#page-Workspaces");
    if (page) {
      if (page.dataset.ndsWarehouseDirectionApplied !== "1") {
        page.dataset.ndsWarehousePreviousDir = page.getAttribute("dir") || "";
        page.dataset.ndsWarehouseDirectionApplied = "1";
      }
      page.setAttribute("dir", direction);
    }
  }
  function el(tag, cls, value) {
    const out = document.createElement(tag);
    if (cls) out.className = cls;
    if (value !== undefined && value !== null) out.textContent = String(value);
    return out;
  }
  function rpc(method, args) {
    return new Promise((resolve, reject) => {
      if (!window.frappe || typeof frappe.call !== "function") return reject(new Error("Frappe API unavailable"));
      frappe.call({method,args,callback:(response)=>resolve(response ? response.message : null),error:(error)=>reject(error || new Error("Request failed"))});
    });
  }
  function getList(doctype, fields, filters, options) {
    return rpc("frappe.client.get_list", Object.assign({doctype,fields,filters:filters || [],limit_page_length:500},options || {}));
  }
  function defaultCompany() {
    try {
      const company = frappe.defaults && frappe.defaults.get_user_default("Company");
      if (company) return company;
    } catch (_) {}
    return (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.company) || "";
  }
  // Bin and Stock Ledger Entry do not have a company field in standard ERPNext.
  // Scope them through the warehouses owned by the selected company instead.
  function companyFilters(doctype, company) { return company ? [[doctype,"company","=",company]] : []; }
  function inventoryWarehouseFilters(doctype, company, warehouseNames) {
    if (!company) return [];
    if (Array.isArray(warehouseNames) && warehouseNames.length) return [[doctype,"warehouse","in",warehouseNames]];
    return [[doctype,"warehouse","=","__nds_no_matching_warehouse__"]];
  }
  async function aggregate(doctype, operation, field, alias, filters) {
    const expression = {}; expression[operation] = field; expression.as = alias;
    const rows = await getList(doctype,[expression],filters,{limit_page_length:1});
    if (!Array.isArray(rows) || !rows.length) return 0;
    const value = Number(rows[0][alias]);
    return Number.isFinite(value) ? value : 0;
  }
  function today() {
    try { if (frappe.datetime && frappe.datetime.get_today) return frappe.datetime.get_today(); } catch (_) {}
    const d = new Date();
    return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
  }
  function monthStart(iso, offset) {
    const p = String(iso).split("-").map(Number), d = new Date(p[0],p[1]-1+offset,1,12,0,0);
    return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
  }
  function monthKey(value) { return String(value || "").slice(0,7); }
  function monthLabel(key) {
    try { return new Intl.DateTimeFormat(t() === TXT.ar ? "ar-SA" : "en-US",{month:"short",calendar:"gregory"}).format(new Date(key+"-01T12:00:00")); }
    catch (_) { return key; }
  }
  function fmt(value, decimals) {
    const n = Number(value);
    return Number.isFinite(n) ? new Intl.NumberFormat("en-US",{minimumFractionDigits:0,maximumFractionDigits:decimals === undefined ? 0 : decimals}).format(n) : "—";
  }
  function money(value) {
    const currency = (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "SAR";
    return fmt(value) + " " + (currency === "SAR" ? (t() === TXT.ar ? "ر.س" : "SAR") : currency);
  }
  function build() {
    const c = t(), board = el("section","nds-warehouse-dashboard");
    board.id = ID; board.setAttribute("aria-label",c.title); board.setAttribute("data-warehouse-dashboard-version","2"); setDirection(board);
    board.innerHTML =
      '<section class="nds-warehouse-kpi-grid" aria-label="'+c.title+'">'+
      '<article class="nds-warehouse-kpi-card" data-kpi="stock-value"><div class="nds-warehouse-kpi-top"><span class="nds-warehouse-kpi-label">'+c.value+'</span><span class="nds-warehouse-kpi-icon" aria-hidden="true">◈</span></div><div class="nds-warehouse-kpi-value" data-kpi-value>—</div><div class="nds-warehouse-kpi-caption" data-kpi-caption>'+c.loading+'</div></article>'+
      '<article class="nds-warehouse-kpi-card" data-kpi="warehouses"><div class="nds-warehouse-kpi-top"><span class="nds-warehouse-kpi-label">'+c.warehouses+'</span><span class="nds-warehouse-kpi-icon" aria-hidden="true">▤</span></div><div class="nds-warehouse-kpi-value" data-kpi-value>—</div><div class="nds-warehouse-kpi-caption" data-kpi-caption>'+c.loading+'</div></article>'+
      '<article class="nds-warehouse-kpi-card" data-kpi="items"><div class="nds-warehouse-kpi-top"><span class="nds-warehouse-kpi-label">'+c.items+'</span><span class="nds-warehouse-kpi-icon" aria-hidden="true">▦</span></div><div class="nds-warehouse-kpi-value" data-kpi-value>—</div><div class="nds-warehouse-kpi-caption" data-kpi-caption>'+c.loading+'</div></article>'+
      '<article class="nds-warehouse-kpi-card" data-kpi="shortages"><div class="nds-warehouse-kpi-top"><span class="nds-warehouse-kpi-label">'+c.shortages+'</span><span class="nds-warehouse-kpi-icon" aria-hidden="true">!</span></div><div class="nds-warehouse-kpi-value" data-kpi-value>—</div><div class="nds-warehouse-kpi-caption" data-kpi-caption>'+c.loading+'</div></article></section>'+
      '<section class="nds-warehouse-analysis-grid" aria-label="'+c.movement+'">'+
      '<article class="nds-warehouse-panel nds-warehouse-movement-chart" aria-labelledby="nds-warehouse-movement-title"><div class="nds-warehouse-panel-heading"><div><h2 id="nds-warehouse-movement-title">'+c.movement+'</h2><p>'+c.movementNote+'</p></div><span class="nds-warehouse-panel-mark" aria-hidden="true">↕</span></div><div class="nds-warehouse-movement-legend"><span><i class="incoming"></i>'+c.incoming+'</span><span><i class="outgoing"></i>'+c.outgoing+'</span></div><div class="nds-warehouse-movement-body" data-movement-chart><div class="nds-warehouse-loading">'+c.loading+'</div></div></article>'+
      '<article class="nds-warehouse-panel nds-warehouse-distribution-chart" aria-labelledby="nds-warehouse-distribution-title"><div class="nds-warehouse-panel-heading"><div><h2 id="nds-warehouse-distribution-title">'+c.distribution+'</h2><p>'+c.distributionNote+'</p></div><span class="nds-warehouse-panel-mark is-blue" aria-hidden="true">▥</span></div><div class="nds-warehouse-distribution-body" data-distribution-chart><div class="nds-warehouse-loading">'+c.loading+'</div></div></article></section>'+
      '<section class="nds-warehouse-panel nds-warehouse-shortage-table" aria-labelledby="nds-warehouse-shortage-title"><div class="nds-warehouse-panel-heading"><div><h2 id="nds-warehouse-shortage-title">'+c.reorder+'</h2><p>'+c.reorderNote+'</p></div><span class="nds-warehouse-panel-mark is-alert" aria-hidden="true">!</span></div><div class="nds-warehouse-table-wrap"><table class="nds-warehouse-table"><thead><tr><th>'+c.item+'</th><th>'+c.warehouse+'</th><th>'+c.actual+'</th><th>'+c.projected+'</th><th>'+c.uom+'</th></tr></thead><tbody data-shortage-rows><tr><td colspan="5" class="nds-warehouse-table-empty">'+c.loading+'</td></tr></tbody></table></div></section>'+
      '<section class="nds-warehouse-navigation" aria-label="'+c.navigation+'">'+
      '<div class="nds-warehouse-navigation-heading"><div><h2 data-warehouse-navigation-title>'+c.navigation+'</h2><p data-warehouse-navigation-note>'+c.navigationNote+'</p></div></div>'+
      '<div class="nds-warehouse-navigation-grid" data-warehouse-navigation-grid>'+
      '<article class="nds-warehouse-nav-card" data-warehouse-nav-category="home"><div class="nds-warehouse-nav-card-heading"><h3 data-nav-title="home">'+c.homeSection+'</h3><span aria-hidden="true">⌂</span></div><div class="nds-warehouse-nav-links" data-warehouse-nav-links="home"></div></article>'+
      '<article class="nds-warehouse-nav-card" data-warehouse-nav-category="reports"><div class="nds-warehouse-nav-card-heading"><h3 data-nav-title="reports">'+c.reportsSection+'</h3><span aria-hidden="true">▤</span></div><div class="nds-warehouse-nav-links" data-warehouse-nav-links="reports"></div></article>'+
      '<article class="nds-warehouse-nav-card" data-warehouse-nav-category="movements"><div class="nds-warehouse-nav-card-heading"><h3 data-nav-title="movements">'+c.movementsSection+'</h3><span aria-hidden="true">↔</span></div><div class="nds-warehouse-nav-links" data-warehouse-nav-links="movements"></div></article>'+
      '</div></section>';
    return board;
  }
  function normalizeNavigationText(value) {
    return String(value || "").normalize("NFD")
      .replace(/[\u0300-\u036f\u064B-\u065F\u0670\u0640]/g, "")
      .toLowerCase().replace(/[_\s-]+/g, " ").trim();
  }
  function navigationCategory(value) {
    const text = normalizeNavigationText(value);
    if (/(التقارير المخزنية|تقارير المخازن|تقارير المخزون|التقارير|تقارير|stock reports?|warehouse reports?|inventory reports?|^reports?$|stock ledger|stock balance report|stock valuation|inventory report|item ageing|item aging)/i.test(text)) return "reports";
    if (/(الحركات المخزنية|حركات المخازن|حركات المخزون|الحركات|حركات|stock movements?|inventory movements?|transactions?|stock entries?|stock entry|stock reconciliation|material transfers?|delivery notes?|purchase receipts?|pick lists?|packing slips?|stock issues?|stock receipts?|stock transfers?)/i.test(text)) return "movements";
    if (/(الرئيسية|الصفحة الرئيسية|^home$|^main$|main menu|warehouse home|^warehouses?$|^مخازن?$|^المخازن?$|^items?$|^الأصناف?$)/i.test(text)) return "home";
    return null;
  }
  function navigationLinkLabel(anchor) {
    const content = anchor.querySelector(".link-content");
    return [
      content ? content.textContent : anchor.textContent,
      anchor.getAttribute("href"),
      anchor.getAttribute("data-route"),
      anchor.getAttribute("title")
    ].filter(Boolean).join(" ");
  }
  function renderNavigation(board) {
    const c = t();
    const section = board.querySelector("[data-warehouse-navigation-grid]");
    if (!section) return;
    const title = board.querySelector("[data-warehouse-navigation-title]");
    const note = board.querySelector("[data-warehouse-navigation-note]");
    if (title) title.textContent = c.navigation;
    if (note) note.textContent = c.navigationNote;
    const titles = {home:c.homeSection,reports:c.reportsSection,movements:c.movementsSection};
    Object.keys(titles).forEach((key) => {
      const heading = section.querySelector('[data-nav-title="' + key + '"]');
      if (heading) heading.textContent = titles[key];
    });

    const source = document.querySelector("#page-Workspaces #editorjs");
    if (source) {
      const widgets = Array.from(source.querySelectorAll(".widget.links-widget-box"));
      widgets.forEach((widget) => {
        const links = Array.from(widget.querySelectorAll(".widget-body > a.link-item"));
        if (!links.length) return;
        const widgetTitle = widget.querySelector(".widget-head .widget-title");
        const fixedCategory = widgetTitle ? navigationCategory(widgetTitle.textContent) : null;
        links.forEach((link) => {
          const category = fixedCategory || navigationCategory(navigationLinkLabel(link)) || "home";
          const target = section.querySelector('[data-warehouse-nav-links="' + category + '"]');
          if (!target) return;
          link.classList.add("nds-warehouse-nav-link");
          const empty = target.querySelector("[data-nav-empty]");
          if (empty) empty.remove();
          if (link.parentElement !== target) target.appendChild(link);
        });
        const sourceBlock = widget.closest(".ce-block");
        if (sourceBlock && !widget.querySelector(".widget-body > a.link-item")) {
          sourceBlock.classList.add("nds-warehouse-links-consumed");
        }
      });
    }
    section.querySelectorAll("[data-warehouse-nav-links]").forEach((target) => {
      if (target.querySelector("a.link-item")) return;
      if (!target.querySelector("[data-nav-empty]")) {
        const empty = el("p", "nds-warehouse-nav-empty", c.noNavigationLinks);
        empty.setAttribute("data-nav-empty", "1");
        target.replaceChildren(empty);
      } else {
        target.querySelector("[data-nav-empty]").textContent = c.noNavigationLinks;
      }
    });
  }
    function setKpi(board,key,value,failed) {
    const card=board.querySelector('[data-kpi="'+key+'"]'); if(!card)return;
    const valueNode=card.querySelector("[data-kpi-value]"), caption=card.querySelector("[data-kpi-caption]");
    if(valueNode)valueNode.textContent=value===null||value===undefined?"—":String(value);
    if(caption)caption.textContent=failed?t().unavailable:t().source;
    card.classList.toggle("is-unavailable",Boolean(failed));
  }
  function renderMovement(board,incoming,outgoing) {
    const box=board.querySelector("[data-movement-chart]"); if(!box)return; box.replaceChildren();
    if(incoming===null||outgoing===null)return box.appendChild(el("div","nds-warehouse-chart-empty",t().unavailable));
    const months=[], index=new Map(), end=today();
    for(let i=-5;i<=0;i++){const key=monthKey(monthStart(end,i)),r={key,label:monthLabel(key),incoming:0,outgoing:0};months.push(r);index.set(key,r);}
    (incoming||[]).forEach((r)=>{const b=index.get(monthKey(r.posting_date));if(b)b.incoming+=Math.max(0,Number(r.quantity||0));});
    (outgoing||[]).forEach((r)=>{const b=index.get(monthKey(r.posting_date));if(b)b.outgoing+=Math.abs(Math.min(0,Number(r.quantity||0)));});
    const max=Math.max(0,...months.map((r)=>Math.max(r.incoming,r.outgoing)));
    if(!max)return box.appendChild(el("div","nds-warehouse-chart-empty",t().noMovement));
    const columns=el("div","nds-warehouse-movement-columns");
    months.forEach((m)=>{const col=el("div","nds-warehouse-month-column"),bars=el("div","nds-warehouse-month-bars");
      [{key:"incoming",value:m.incoming},{key:"outgoing",value:m.outgoing}].forEach((s)=>{const track=el("div","nds-warehouse-bar-track "+s.key),bar=el("span","nds-warehouse-bar");
        bar.style.height=(s.value>0?Math.max(4,s.value/max*106):0).toFixed(1)+"px";bar.title=m.label+" — "+(s.key==="incoming"?t().incoming:t().outgoing)+": "+fmt(s.value,2);bar.setAttribute("aria-label",bar.title);track.appendChild(bar);bars.appendChild(track);});
      col.append(bars,el("span","nds-warehouse-month-label",m.label));columns.appendChild(col);});
    box.appendChild(columns);
  }
  function renderDistribution(board,rows) {
    const box=board.querySelector("[data-distribution-chart]");if(!box)return;box.replaceChildren();
    if(rows===null)return box.appendChild(el("div","nds-warehouse-chart-empty",t().unavailable));
    const data=rows.filter((r)=>Number(r.stock_value||0)>=0),max=Math.max(0,...data.map((r)=>Number(r.stock_value||0)));
    if(!data.length||max<=0)return box.appendChild(el("div","nds-warehouse-chart-empty",t().noDistribution));
    const listNode=el("div","nds-warehouse-distribution-list");
    data.slice(0,8).forEach((r)=>{const value=Number(r.stock_value||0),item=el("div","nds-warehouse-distribution-row"),head=el("div","nds-warehouse-distribution-head");
      head.append(el("span","nds-warehouse-distribution-name",r.warehouse||"—"),el("strong","nds-warehouse-distribution-value",money(value)));
      const track=el("div","nds-warehouse-distribution-track"),fill=el("span","nds-warehouse-distribution-fill");fill.style.width=Math.max(value>0?2:0,value/max*100).toFixed(1)+"%";track.appendChild(fill);item.append(head,track);listNode.appendChild(item);});
    box.appendChild(listNode);
  }
  function appendLink(cell,doctype,name,label) {
    if(!name){cell.textContent="—";return;}const anchor=el("a","",label||name);anchor.href="#";
    anchor.addEventListener("click",(event)=>{event.preventDefault();if(window.frappe&&frappe.set_route)frappe.set_route("Form",doctype,name);});cell.appendChild(anchor);
  }
  async function getShortages(company, warehouseNames) {
    const rows=await getList("Bin",["item_code","warehouse","actual_qty","projected_qty"],[["Bin","projected_qty","<",0]].concat(inventoryWarehouseFilters("Bin",company,warehouseNames)),{order_by:"projected_qty asc",limit_page_length:10});
    if(!Array.isArray(rows))return null;const codes=[...new Set(rows.map((r)=>r.item_code).filter(Boolean))];let items=[];
    if(codes.length){try{items=await getList("Item",["name","item_name","stock_uom"],[["Item","name","in",codes]],{limit_page_length:codes.length})||[];}catch(_){}}
    const itemDetails=new Map(items.map((r)=>[r.name,{item_name:r.item_name||r.name,stock_uom:r.stock_uom||""}]));
    return rows.map((r)=>Object.assign({},r,itemDetails.get(r.item_code)||{item_name:r.item_code,stock_uom:""}));
  }
  function renderShortages(board,rows) {
    const body=board.querySelector("[data-shortage-rows]");if(!body)return;body.replaceChildren();
    if(rows===null||!rows.length){const row=el("tr"),cell=el("td","nds-warehouse-table-empty",rows===null?t().unavailable:t().noShortages);cell.colSpan=5;row.appendChild(cell);body.appendChild(row);return;}
    rows.forEach((r)=>{const row=el("tr"),item=el("td"),warehouse=el("td");appendLink(item,"Item",r.item_code,r.item_name||r.item_code);item.appendChild(el("small","nds-warehouse-item-code",r.item_code));appendLink(warehouse,"Warehouse",r.warehouse,r.warehouse);
      row.append(item,warehouse,el("td","is-numeric",fmt(r.actual_qty,2)),el("td","is-numeric is-negative",fmt(r.projected_qty,2)),el("td","",r.stock_uom||"—"));body.appendChild(row);});
  }
  async function getMovement(company,end,warehouseNames) {
    const filters=[["Stock Ledger Entry","is_cancelled","=",0],["Stock Ledger Entry","posting_date",">=",monthStart(end,-5)],["Stock Ledger Entry","posting_date","<=",end]].concat(inventoryWarehouseFilters("Stock Ledger Entry",company,warehouseNames));
    const fields=["posting_date",{SUM:"actual_qty",as:"quantity"}];
    const incoming=getList("Stock Ledger Entry",fields,filters.concat([["Stock Ledger Entry","actual_qty",">",0]]),{group_by:"posting_date",order_by:"posting_date asc",limit_page_length:1000});
    const outgoing=getList("Stock Ledger Entry",fields,filters.concat([["Stock Ledger Entry","actual_qty","<",0]]),{group_by:"posting_date",order_by:"posting_date asc",limit_page_length:1000});
    const values=await Promise.all([incoming,outgoing]);return {incoming:Array.isArray(values[0])?values[0]:null,outgoing:Array.isArray(values[1])?values[1]:null};
  }
  async function loadData(board) {
    const company=defaultCompany(),end=today(),warehouseFilters=[["Warehouse","disabled","=",0],["Warehouse","is_group","=",0]].concat(companyFilters("Warehouse",company));
    const itemFilters=[["Item","disabled","=",0],["Item","is_stock_item","=",1]];
    // Resolve company-owned warehouses once, then use the real Bin/SLE warehouse field.
    const companyWarehouses = company ? await getList("Warehouse",["name"],[["Warehouse","company","=",company],["Warehouse","disabled","=",0],["Warehouse","is_group","=",0]],{limit_page_length:500}).catch(()=>[]) : [];
    const warehouseNames = Array.isArray(companyWarehouses) ? companyWarehouses.map((row)=>row.name).filter(Boolean) : [];
    const bins=inventoryWarehouseFilters("Bin",company,warehouseNames);
    const valuedBins=[["Bin","stock_value",">",0]].concat(bins),shortageBins=[["Bin","projected_qty","<",0]].concat(bins);
    const results=await Promise.all([
      aggregate("Bin","SUM","stock_value","total_stock_value",bins).catch(()=>null),
      aggregate("Warehouse","COUNT","*","active_warehouses",warehouseFilters).catch(()=>null),
      aggregate("Item","COUNT","*","active_items",itemFilters).catch(()=>null),
      aggregate("Bin","COUNT","*","shortage_cases",shortageBins).catch(()=>null),
      getMovement(company,end,warehouseNames).catch(()=>null),
      getList("Bin",["warehouse",{SUM:"stock_value",as:"stock_value"}],valuedBins,{group_by:"warehouse",order_by:"stock_value desc",limit_page_length:8}).catch(()=>null),
      getShortages(company,warehouseNames).catch(()=>null)
    ]);
    setKpi(board,"stock-value",results[0]===null?null:money(results[0]),results[0]===null);
    setKpi(board,"warehouses",results[1]===null?null:fmt(results[1]),results[1]===null);
    setKpi(board,"items",results[2]===null?null:fmt(results[2]),results[2]===null);
    setKpi(board,"shortages",results[3]===null?null:fmt(results[3]),results[3]===null);
    renderMovement(board,results[4]?results[4].incoming:null,results[4]?results[4].outgoing:null);
    renderDistribution(board,Array.isArray(results[5])?results[5]:null);
    renderShortages(board,Array.isArray(results[6])?results[6]:null);
  }
  function cleanup(){
    const current=document.getElementById(ID);
    if(current)current.remove();
    const page=document.querySelector("#page-Workspaces");
    if(page&&page.dataset.ndsWarehouseDirectionApplied==="1"){
      const previous=page.dataset.ndsWarehousePreviousDir||"";
      if(previous)page.setAttribute("dir",previous);else page.removeAttribute("dir");
      delete page.dataset.ndsWarehouseDirectionApplied;
      delete page.dataset.ndsWarehousePreviousDir;
    }
    if(document.documentElement)document.documentElement.classList.remove(READY);
  }
  function mountIfReady(){
    if(!isTarget()){cleanup();return;}if(!document.body)return;
    const host=document.querySelector("#page-Workspaces .layout-main-section");if(!host)return;
    const current=document.getElementById(ID);
    if(current&&current.isConnected&&current.parentElement===host){setDirection(current);renderNavigation(current);document.documentElement.classList.add(READY);return;}
    if(current)current.remove();const board=build();host.insertBefore(board,host.firstChild);document.documentElement.classList.add(READY);
    renderNavigation(board);
    loadData(board).catch(()=>{renderMovement(board,null,null);renderDistribution(board,null);renderShortages(board,null);});
  }
  function schedule(){timers.forEach((timer)=>window.clearTimeout(timer));timers=[0,120,350,800,1400].map((delay)=>window.setTimeout(mountIfReady,delay));}
  function mount(){
    if(installed)return;installed=true;
    const boot=()=>{
      schedule();if(window.frappe&&frappe.router&&frappe.router.on)frappe.router.on("change",schedule);
      window.addEventListener("popstate",schedule);$(document).on("page-change",schedule);
      if(!langObserver&&document.documentElement){langObserver=new MutationObserver(()=>{const board=document.getElementById(ID);if(board&&isTarget())setDirection(board);schedule();});langObserver.observe(document.documentElement,{attributes:true,attributeFilter:["dir","lang"]});}
      if(document.body&&observedBody!==document.body){if(domObserver)domObserver.disconnect();observedBody=document.body;domObserver=new MutationObserver((records)=>{const board=document.getElementById(ID);if(isTarget()){if(!board){schedule();return;}const navigationChanged=records.some((record)=>{const target=record.target&&record.target.nodeType===1?record.target:record.target&&record.target.parentElement;return target&&!board.contains(target)&&(target.closest("#editorjs")||Array.from(record.addedNodes||[]).some((node)=>node.nodeType===1&&(node.matches("#editorjs")||node.querySelector("#editorjs"))));});if(navigationChanged)renderNavigation(board);}else if(board)cleanup();});domObserver.observe(document.body,{childList:true,subtree:true});}
    };
    if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
  }
  return {mount};
})();
export { warehouseDashboard };
