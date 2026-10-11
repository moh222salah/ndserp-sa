#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/workspaces/ndserp-sa"
PORT="8080"
cd "$ROOT"

echo "=== NDS ERP SAUDI — LIVE HEADER VERIFICATION ==="
echo "ROOT=$ROOT"
echo "SOURCE_HEAD=$(git rev-parse HEAD)"
echo "GITHUB_MAIN=$(git rev-parse origin/main 2>/dev/null || git rev-parse HEAD)"

test -s sites/assets/assets.json || { echo "ASSET_MANIFEST=FAIL"; exit 10; }

ASSET_PATH="$("$ROOT/env/bin/python" - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("sites/assets/assets.json").read_text(encoding="utf-8"))
path = manifest.get("amir_theme.bundle.css")
if not isinstance(path, str) or not path:
    raise SystemExit("MISSING_AMIR_THEME_CSS_MAPPING")
print(path)
PY
)" || { echo "ASSET_MAPPING=FAIL"; exit 11; }

case "$ASSET_PATH" in
  http://*|https://*) ASSET_URL="$ASSET_PATH" ;;
  /*) ASSET_URL="http://127.0.0.1:$PORT$ASSET_PATH" ;;
  *) ASSET_URL="http://127.0.0.1:$PORT/$ASSET_PATH" ;;
esac

SITE_ASSET="$ROOT/sites/${ASSET_PATH#/}"
REPO_ASSET="$ROOT/${ASSET_PATH#/}"
if [ -f "$SITE_ASSET" ]; then
  LOCAL_ASSET="$SITE_ASSET"
else
  LOCAL_ASSET="$REPO_ASSET"
fi
if [ ! -f "$LOCAL_ASSET" ]; then
  echo "BUILT_HEADER_CSS=FAIL:MISSING_FILE:$LOCAL_ASSET"
  exit 12
fi

LOCAL_CSS="$(mktemp)"
SERVED_CSS="$(mktemp)"
trap 'rm -f "$LOCAL_CSS" "$SERVED_CSS"' EXIT
tr '[:upper:]' '[:lower:]' < "$LOCAL_ASSET" > "$LOCAL_CSS"
for marker in 'body .navbar' '58px' '#0a2342' 'html[dir=rtl] body .navbar .navbar-nav' 'html[dir=rtl] .page-head .navbar-breadcrumbs' 'html[dir=ltr] body .navbar .navbar-nav'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_HEADER_CSS=FAIL:MISSING_MARKER:$marker"
    exit 13
  fi
done
echo "BUILT_HEADER_CSS=PASS"
echo "BUILT_HEADER_CSS_SHA256=$(sha256sum "$LOCAL_ASSET" | awk '{print $1}')"

# Verify the actual new Quick Actions styles before contacting the web server.
tr '[:upper:]' '[:lower:]' < "$LOCAL_ASSET" | tr -d '[:space:]' > "$LOCAL_CSS"
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' '.amt-quick-actions-track' 'display:grid' 'grid-template-columns:repeat(7,minmax(0,1fr))' 'grid-template-columns:repeat(4,minmax(0,1fr))' 'grid-template-columns:repeat(2,minmax(0,1fr))' 'height:92px' 'min-height:92px' 'width:30px' 'width:16px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 24
  fi
done
echo "BUILT_QUICK_ACTIONS_CSS=PASS"
for marker in '.nds-warehouse-workspace' 'border-block-start:3pxsolid#0a2342' '.nds-warehouse-dashboard' '.nds-warehouse-kpi-grid' '.nds-warehouse-movement-chart' '.nds-warehouse-distribution-chart' '.nds-warehouse-shortage-table' '#page-workspaces[dir=rtl]' '#page-workspaces[dir=ltr]' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_WAREHOUSE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 26
  fi
done
echo "BUILT_WAREHOUSE_WORKSPACE_CSS=PASS"
for marker in '.amt-accounts-workspace' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#bd5548' '.nds-accounts-dashboard' '.nds-accounts-kpi-grid' '.nds-accounts-kpi-indicator' '.nds-accounts-analysis-grid' '.nds-accounts-expense-list' '.nds-accounts-expenses-axis' '.nds-accounts-chart-plot' '.nds-accounts-month-bars' '.nds-accounts-invoice-table' '.nds-accounts-status.overdue' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_ACCOUNTS_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 30
  fi
done
echo "BUILT_ACCOUNTS_WORKSPACE_CSS=PASS"
for marker in '.nds-sales-workspace-redesign' '#page-workspaces' '#d4af37'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_SALES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 34
  fi
done
echo "BUILT_SALES_WORKSPACE_CSS=PASS"
for marker in 'sales-rtl-direction-v3' '[dir=rtl].page-head' '[dir=ltr].page-head' 'direction:rtl!important' 'text-align:right!important' 'direction:ltr!important' 'text-align:left!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_SALES_WORKSPACE_DIRECTION_CSS=FAIL:MISSING_MARKER:$marker"
    exit 51
  fi
done
echo "BUILT_SALES_WORKSPACE_DIRECTION_CSS=PASS"
for marker in '.nds-sales-dashboard' '.nds-sales-kpi-grid' '.nds-sales-revenue-chart' '.nds-sales-channels-chart' '.nds-sales-invoices' '.nds-sales-dashboard[dir=rtl]' '.nds-sales-dashboard[dir=ltr]' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_SALES_DASHBOARD_CSS=FAIL:MISSING_MARKER:$marker"
    exit 42
  fi
done
if grep -Fq 'nds-sales-dashboard-ready#page-workspaces.page-head{display:none!important' "$LOCAL_CSS"; then
  echo "BUILT_SALES_HEADER=FAIL:HIDDEN_BY_THEME"
  exit 48
fi
echo "BUILT_SALES_HEADER=PASS"
for marker in '.nds-sales-workspace-sections' '.nds-sales-workspace-sections[dir=rtl]' '.nds-sales-workspace-sections[dir=ltr]' '.nds-sales-section-grid' '.nds-sales-section-card' '.nds-sales-section-card[dir=rtl]' '.nds-sales-section-card[dir=ltr]' '.nds-sales-section-link' 'grid-template-columns:repeat(2,minmax(0,1fr))' 'grid-template-columns:minmax(0,1fr)'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_SALES_WORKSPACE_SECTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 50
  fi
done
echo "BUILT_SALES_WORKSPACE_SECTIONS_CSS=PASS"
echo "BUILT_SALES_DASHBOARD_CSS=PASS"
for marker in '.nds-purchase-workspace-redesign' '#page-workspaces' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#c58b3c' 'grid-column:span7' 'grid-column:span5' 'border-collapse:separate'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_PURCHASE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 38
  fi
done
echo "BUILT_PURCHASE_WORKSPACE_CSS=PASS"
for marker in '.nds-purchase-dashboard' '.nds-purchase-kpi-grid' '.nds-purchase-charts-grid' '.nds-purchase-category-fill' '.nds-purchase-month-columns' '.nds-purchase-orders-table' '.nds-purchase-dashboard[dir=rtl]' '.nds-purchase-dashboard[dir=ltr]'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_PURCHASE_DASHBOARD_CSS=FAIL:MISSING_MARKER:$marker"
    exit 54
  fi
done
echo "BUILT_PURCHASE_DASHBOARD_CSS=PASS"
for marker in '.nds-master-files-workspace' '.widget.shortcut-widget-box' '.widget.number-widget-box' '#164e8f' '#d4af37' 'prefers-reduced-motion:reduce'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "BUILT_MASTER_FILES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 58
  fi
done
echo "BUILT_MASTER_FILES_WORKSPACE_CSS=PASS"
echo "ASSET_URL=$ASSET_URL"

READY=0
for _ in $(seq 1 90); do
  if curl --connect-timeout 2 --max-time 5 -fsS "$ASSET_URL" -o "$SERVED_CSS"; then
    READY=1
    break
  fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "SERVED_HEADER_CSS=FAIL:HTTP_UNAVAILABLE"
  exit 14
fi

tr '[:upper:]' '[:lower:]' < "$SERVED_CSS" > "$LOCAL_CSS"
for marker in 'body .navbar' '58px' '#0a2342'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_HEADER_CSS=FAIL:MISSING_MARKER:$marker"
    exit 15
  fi
done
echo "SERVED_HEADER_CSS=PASS"
echo "SERVED_HEADER_CSS_SHA256=$(sha256sum "$SERVED_CSS" | awk '{print $1}')"
if [ "$(sha256sum "$LOCAL_ASSET" | awk '{print $1}')" != "$(sha256sum "$SERVED_CSS" | awk '{print $1}')" ]; then
  echo "SERVED_HEADER_CSS=FAIL:HASH_MISMATCH"
  exit 16
fi
echo "SERVED_HEADER_CSS_MATCH=PASS"

# Verify the target Quick Actions styles in the CSS actually served to the browser.
tr '[:upper:]' '[:lower:]' < "$SERVED_CSS" | tr -d '[:space:]' > "$LOCAL_CSS"
for marker in '.amt-quick-actions' '.amt-quick-actions-grid' '.amt-quick-actions-track' 'display:grid' 'grid-template-columns:repeat(7,minmax(0,1fr))' 'grid-template-columns:repeat(4,minmax(0,1fr))' 'grid-template-columns:repeat(2,minmax(0,1fr))' 'height:92px' 'min-height:92px' 'width:30px' 'width:16px' 'margin-top:auto' 'background:#eef1f4' 'display:none!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_QUICK_ACTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 17
  fi
done
echo "SERVED_QUICK_ACTIONS_CSS=PASS"
for marker in '.nds-warehouse-workspace' 'border-block-start:3pxsolid#0a2342' '.nds-warehouse-dashboard' '.nds-warehouse-kpi-grid' '.nds-warehouse-movement-chart' '.nds-warehouse-distribution-chart' '.nds-warehouse-shortage-table' '#page-workspaces[dir=rtl]' '#page-workspaces[dir=ltr]' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_WAREHOUSE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 27
  fi
done
echo "SERVED_WAREHOUSE_WORKSPACE_CSS=PASS"
for marker in '.amt-accounts-workspace' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#bd5548' '.nds-accounts-dashboard' '.nds-accounts-kpi-grid' '.nds-accounts-kpi-indicator' '.nds-accounts-analysis-grid' '.nds-accounts-expense-list' '.nds-accounts-expenses-axis' '.nds-accounts-chart-plot' '.nds-accounts-month-bars' '.nds-accounts-invoice-table' '.nds-accounts-status.overdue' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_ACCOUNTS_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 31
  fi
done
echo "SERVED_ACCOUNTS_WORKSPACE_CSS=PASS"
for marker in '.nds-sales-workspace-redesign' '#page-workspaces' '#d4af37'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_SALES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 35
  fi
done
echo "SERVED_SALES_WORKSPACE_CSS=PASS"
for marker in 'sales-rtl-direction-v3' '[dir=rtl].page-head' '[dir=ltr].page-head' 'direction:rtl!important' 'text-align:right!important' 'direction:ltr!important' 'text-align:left!important'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_SALES_WORKSPACE_DIRECTION_CSS=FAIL:MISSING_MARKER:$marker"
    exit 53
  fi
done
echo "SERVED_SALES_WORKSPACE_DIRECTION_CSS=PASS"
for marker in '.nds-sales-dashboard' '.nds-sales-kpi-grid' '.nds-sales-revenue-chart' '.nds-sales-channels-chart' '.nds-sales-invoices' '.nds-sales-dashboard[dir=rtl]' '.nds-sales-dashboard[dir=ltr]' 'grid-template-columns:repeat(4,minmax(0,1fr))'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_SALES_DASHBOARD_CSS=FAIL:MISSING_MARKER:$marker"
    exit 43
  fi
done
if grep -Fq 'nds-sales-dashboard-ready#page-workspaces.page-head{display:none!important' "$LOCAL_CSS"; then
  echo "SERVED_SALES_HEADER=FAIL:HIDDEN_BY_THEME"
  exit 49
fi
echo "SERVED_SALES_HEADER=PASS"
for marker in '.nds-sales-workspace-sections' '.nds-sales-workspace-sections[dir=rtl]' '.nds-sales-workspace-sections[dir=ltr]' '.nds-sales-section-grid' '.nds-sales-section-card' '.nds-sales-section-card[dir=rtl]' '.nds-sales-section-card[dir=ltr]' '.nds-sales-section-link' 'grid-template-columns:repeat(2,minmax(0,1fr))' 'grid-template-columns:minmax(0,1fr)'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_SALES_WORKSPACE_SECTIONS_CSS=FAIL:MISSING_MARKER:$marker"
    exit 52
  fi
done
echo "SERVED_SALES_WORKSPACE_SECTIONS_CSS=PASS"
echo "SERVED_SALES_DASHBOARD_CSS=PASS"
for marker in '.nds-purchase-workspace-redesign' '#page-workspaces' '.codex-editor__redactor' 'grid-template-columns:repeat(12,minmax(0,1fr))' '#c58b3c' 'grid-column:span7' 'grid-column:span5' 'border-collapse:separate'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_PURCHASE_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 39
  fi
done
echo "SERVED_PURCHASE_WORKSPACE_CSS=PASS"
for marker in '.nds-purchase-dashboard' '.nds-purchase-kpi-grid' '.nds-purchase-charts-grid' '.nds-purchase-category-fill' '.nds-purchase-month-columns' '.nds-purchase-orders-table' '.nds-purchase-dashboard[dir=rtl]' '.nds-purchase-dashboard[dir=ltr]'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_PURCHASE_DASHBOARD_CSS=FAIL:MISSING_MARKER:$marker"
    exit 54
  fi
done
echo "SERVED_PURCHASE_DASHBOARD_CSS=PASS"
for marker in '.nds-master-files-workspace' '.widget.shortcut-widget-box' '.widget.number-widget-box' '#164e8f' '#d4af37' 'prefers-reduced-motion:reduce'; do
  if ! grep -Fq "$marker" "$LOCAL_CSS"; then
    echo "SERVED_MASTER_FILES_WORKSPACE_CSS=FAIL:MISSING_MARKER:$marker"
    exit 59
  fi
done
echo "SERVED_MASTER_FILES_WORKSPACE_CSS=PASS"

JS_ASSET_PATH="$("$ROOT/env/bin/python" - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path("sites/assets/assets.json").read_text(encoding="utf-8"))
path = manifest.get("amir_theme.bundle.js")
if not isinstance(path, str) or not path:
    raise SystemExit("MISSING_AMIR_THEME_JS_MAPPING")
print(path)
PY
)" || { echo "JS_ASSET_MAPPING=FAIL"; exit 18; }
case "$JS_ASSET_PATH" in
  http://*|https://*) JS_ASSET_URL="$JS_ASSET_PATH" ;;
  /*) JS_ASSET_URL="http://127.0.0.1:$PORT$JS_ASSET_PATH" ;;
  *) JS_ASSET_URL="http://127.0.0.1:$PORT/$JS_ASSET_PATH" ;;
esac
SITE_JS_ASSET="$ROOT/sites/${JS_ASSET_PATH#/}"
REPO_JS_ASSET="$ROOT/${JS_ASSET_PATH#/}"
if [ -f "$SITE_JS_ASSET" ]; then LOCAL_JS_ASSET="$SITE_JS_ASSET"; else LOCAL_JS_ASSET="$REPO_JS_ASSET"; fi
if [ ! -f "$LOCAL_JS_ASSET" ]; then
  echo "BUILT_QUICK_ACTIONS_JS=FAIL:MISSING_FILE:$LOCAL_JS_ASSET"
  exit 19
fi
# Use stable ASCII markers; bundling may encode Arabic literals as Unicode escapes.
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'amt-quick-actions-track' 'data-amt-quick-actions-layout' 'static-grid' 'amt-quick-action-label' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 20
  fi
done
if grep -Fq "data-amt-quick-actions-loop" "$LOCAL_JS_ASSET" || grep -Fq "amt-quick-action-clone" "$LOCAL_JS_ASSET"; then echo "BUILT_QUICK_ACTIONS_JS=FAIL:LEGACY_MOTION_PRESENT"; exit 20; fi
echo "BUILT_QUICK_ACTIONS_STATIC=PASS"
for marker in 'nds-warehouse-workspace' 'nds-warehouse-dashboard' 'nds-warehouse-kpi-grid' 'nds-warehouse-movement-chart' 'nds-warehouse-distribution-chart' 'nds-warehouse-shortage-table' 'data-warehouse-dashboard-version' 'data-warehouse-nav-links' 'data-nds-ui-direction' 'Warehouse Dashboard' 'Current Stock Value' 'Stock Ledger Entry' 'frappe.client.get_list'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_WAREHOUSE_WORKSPACE_JS=FAIL:MISSING_MARKER:$marker"
    exit 28
  fi
done
echo "BUILT_WAREHOUSE_WORKSPACE_JS=PASS"
# Verify stable Accounts Dashboard UI/data-fetch markers. KPI values and invoice IDs are live DB data and must not be hard-coded in the bundle.
for marker in 'amt-accounts-workspace' 'nds-accounts-dashboard' 'nds-accounts-kpi-grid' 'nds-accounts-kpi-indicator' 'nds-accounts-invoice-table' 'Accounts Dashboard' 'Net Profit (Month)' 'Expenses by Account' 'Revenue vs. Expenses' 'Unpaid Invoices' 'frappe.client.get_list'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_ACCOUNTS_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 46
  fi
done
echo "BUILT_ACCOUNTS_DASHBOARD_JS=PASS"
if ! grep -Fq 'nds-sales-workspace-redesign' "$LOCAL_JS_ASSET"; then
  echo "BUILT_SALES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-sales-workspace-redesign"
  exit 36
fi
echo "BUILT_SALES_WORKSPACE_JS=PASS"
for marker in 'nds-sales-dashboard' 'nds-sales-revenue-chart' 'nds-sales-channels-chart' 'nds-sales-invoices' 'nds-sales-workspace-sections' 'nds-sales-section-card' 'workspace_map' 'data-sales-direction' 'sales-rtl-direction-v3' 'data-sales-direction-fix'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_SALES_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 44
  fi
done
echo "BUILT_SALES_DASHBOARD_JS=PASS"
for marker in 'Monthly Sales' 'Latest Sales Invoices' 'workspace_map' 'frappe.client.get_list' 'reports-1' 'reports-2' 'reports-3' 'Sales by Channel' 'Unavailable' 'Sales NDS ERP' 'ndsSalesOriginalText' 'Home' 'Items & Pricing' 'Work' 'Settings' 'Reports'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_SALES_LIVE_BILINGUAL=FAIL:MISSING_MARKER:$marker"
    exit 54
  fi
done
SALES_SOURCE_JS="$ROOT/apps/amir_theme_v16/amir_theme_v16/src/js/core/sales_dashboard.js"
if grep -Fq 'data-sales-period' "$SALES_SOURCE_JS" || grep -Fq 'Nexterp v16' "$SALES_SOURCE_JS"; then
  echo "SALES_TOP_METADATA=FAIL:SOURCE"
  exit 55
fi
echo "SALES_TOP_METADATA_SOURCE=PASS"
echo "BUILT_SALES_LIVE_BILINGUAL=PASS"

if ! grep -Fq 'nds-purchase-workspace-redesign' "$LOCAL_JS_ASSET"; then
  echo "BUILT_PURCHASE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-purchase-workspace-redesign"
  exit 40
fi
echo "BUILT_PURCHASE_WORKSPACE_JS=PASS"
for marker in 'nds-purchase-dashboard' 'nds-purchase-kpi-grid' 'nds-purchase-month-columns' 'nds-purchase-orders-table' 'Purchase Invoice' 'Purchase Receipt' 'data-purchase-direction' 'data-nds-ui-direction'; do
  if ! grep -Fq "$marker" "$LOCAL_JS_ASSET"; then
    echo "BUILT_PURCHASE_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 55
  fi
done
echo "BUILT_PURCHASE_DASHBOARD_JS=PASS"
PURCHASE_SOURCE_JS="$ROOT/apps/amir_theme_v16/amir_theme_v16/src/js/core/purchases_dashboard.js"
if grep -Fq 'data-purchase-period' "$PURCHASE_SOURCE_JS" || grep -Fq 'لوحة المشتريات' "$PURCHASE_SOURCE_JS" || grep -Fq 'Nexterp v16' "$PURCHASE_SOURCE_JS"; then
  echo "PURCHASE_DASHBOARD_TOP_METADATA=FAIL:SOURCE"
  exit 56
fi
echo "PURCHASE_DASHBOARD_TOP_METADATA_SOURCE=PASS"
if ! grep -Fq 'nds-master-files-workspace' "$LOCAL_JS_ASSET"; then
  echo "BUILT_MASTER_FILES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-master-files-workspace"
  exit 60
fi
echo "BUILT_MASTER_FILES_WORKSPACE_JS=PASS"
SERVED_JS="$(mktemp)"
trap 'rm -f "$LOCAL_CSS" "$SERVED_CSS" "$SERVED_JS"' EXIT
JS_READY=0
for _ in $(seq 1 90); do
  if curl --connect-timeout 2 --max-time 5 -fsS "$JS_ASSET_URL" -o "$SERVED_JS"; then
    JS_READY=1
    break
  fi
  sleep 1
done
if [ "$JS_READY" -ne 1 ]; then
  echo "SERVED_QUICK_ACTIONS_JS=FAIL:HTTP_UNAVAILABLE"
  exit 21
fi
for marker in 'amt-quick-actions-title' 'amt-quick-actions-grid' 'amt-quick-actions-track' 'data-amt-quick-actions-layout' 'static-grid' 'amt-quick-action-label' 'Sales Invoice'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_QUICK_ACTIONS_JS=FAIL:MISSING_MARKER:$marker"
    exit 22
  fi
done
if grep -Fq "data-amt-quick-actions-loop" "$SERVED_JS" || grep -Fq "amt-quick-action-clone" "$SERVED_JS"; then echo "SERVED_QUICK_ACTIONS_JS=FAIL:LEGACY_MOTION_PRESENT"; exit 22; fi
echo "SERVED_QUICK_ACTIONS_STATIC=PASS"
for marker in 'nds-warehouse-workspace' 'nds-warehouse-dashboard' 'nds-warehouse-kpi-grid' 'nds-warehouse-movement-chart' 'nds-warehouse-distribution-chart' 'nds-warehouse-shortage-table' 'data-warehouse-dashboard-version' 'data-warehouse-nav-links' 'data-nds-ui-direction' 'Warehouse Dashboard' 'Current Stock Value' 'Stock Ledger Entry' 'frappe.client.get_list'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_WAREHOUSE_WORKSPACE_JS=FAIL:MISSING_MARKER:$marker"
    exit 29
  fi
done
echo "SERVED_WAREHOUSE_WORKSPACE_JS=PASS"
for marker in 'amt-accounts-workspace' 'nds-accounts-dashboard' 'nds-accounts-kpi-grid' 'nds-accounts-kpi-indicator' 'nds-accounts-invoice-table' 'Accounts Dashboard' 'Net Profit (Month)' 'Expenses by Account' 'Revenue vs. Expenses' 'Unpaid Invoices' 'frappe.client.get_list'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_ACCOUNTS_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 47
  fi
done
echo "SERVED_ACCOUNTS_DASHBOARD_JS=PASS"
# Backward-compatible marker for the original Workspace scope gate. The same
# served bundle above must also contain the redesigned dashboard module.
echo "SERVED_ACCOUNTS_WORKSPACE_JS=PASS"
if ! grep -Fq 'nds-sales-workspace-redesign' "$SERVED_JS"; then
  echo "SERVED_SALES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-sales-workspace-redesign"
  exit 37
fi
echo "SERVED_SALES_WORKSPACE_JS=PASS"
for marker in 'nds-sales-dashboard' 'nds-sales-revenue-chart' 'nds-sales-channels-chart' 'nds-sales-invoices' 'nds-sales-workspace-sections' 'nds-sales-section-card' 'workspace_map' 'data-sales-direction' 'sales-rtl-direction-v3' 'data-sales-direction-fix'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_SALES_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 45
  fi
done
echo "SERVED_SALES_DASHBOARD_JS=PASS"
for marker in 'Monthly Sales' 'Latest Sales Invoices' 'workspace_map' 'frappe.client.get_list' 'reports-1' 'reports-2' 'reports-3' 'Sales by Channel' 'Unavailable' 'Sales NDS ERP' 'ndsSalesOriginalText' 'Home' 'Items & Pricing' 'Work' 'Settings' 'Reports'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_SALES_LIVE_BILINGUAL=FAIL:MISSING_MARKER:$marker"
    exit 56
  fi
done
# The shared bundle includes multiple modules; top-metadata cleanup is checked
# against the sales feature source above. Verify served bytes by bundle SHA and markers.
echo "SERVED_SALES_LIVE_BILINGUAL=PASS"

if ! grep -Fq 'nds-purchase-workspace-redesign' "$SERVED_JS"; then
  echo "SERVED_PURCHASE_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-purchase-workspace-redesign"
  exit 41
fi
echo "SERVED_PURCHASE_WORKSPACE_JS=PASS"
for marker in 'nds-purchase-dashboard' 'nds-purchase-kpi-grid' 'nds-purchase-month-columns' 'nds-purchase-orders-table' 'Purchase Invoice' 'Purchase Receipt' 'data-purchase-direction' 'data-nds-ui-direction'; do
  if ! grep -Fq "$marker" "$SERVED_JS"; then
    echo "SERVED_PURCHASE_DASHBOARD_JS=FAIL:MISSING_MARKER:$marker"
    exit 55
  fi
done
echo "SERVED_PURCHASE_DASHBOARD_JS=PASS"
# The served bundle is checked by SHA-256 below; metadata cleanup is guarded at feature-source level.
if ! grep -Fq 'nds-master-files-workspace' "$SERVED_JS"; then
  echo "SERVED_MASTER_FILES_WORKSPACE_JS=FAIL:MISSING_MARKER:nds-master-files-workspace"
  exit 61
fi
echo "SERVED_MASTER_FILES_WORKSPACE_JS=PASS"
if [ "$(sha256sum "$LOCAL_JS_ASSET" | awk '{print $1}')" != "$(sha256sum "$SERVED_JS" | awk '{print $1}')" ]; then
  echo "SERVED_QUICK_ACTIONS_JS=FAIL:HASH_MISMATCH"
  exit 23
fi
echo "BUILT_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS=PASS"
echo "SERVED_QUICK_ACTIONS_JS_MATCH=PASS"
echo "HEADER_RUNTIME_VERIFICATION=PASS"
echo "QUICK_ACTIONS_STATIC_RUNTIME_ASSETS=PASS"
echo "QUICK_ACTIONS_RUNTIME_ASSETS=PASS"
echo "WAREHOUSE_WORKSPACE_RUNTIME_ASSETS=PASS"
echo "DB_WRITE=NO"
echo "MIGRATION=NO"
echo "CORE_MODIFICATION=NO"
