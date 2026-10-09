app_name = "ndserp"
app_title = "NDS ERP"
app_publisher = "NDS"
app_description = (
	"Arabic-first ERPNext localisation layer: Arabic workspaces, language switcher and shared customisations."
)
app_email = "mahahassanshadid@gmail.com"
app_license = "mit"

# ndserp customises ERPNext documents and ships NDS POS + HR workspaces, so
# ERPNext, Frappe HR (hrms) and POS Next must be present before install.
required_apps = ["erpnext", "hrms", "pos_next"]

# ------------------------------------------------------------------------------
# Assets
# ------------------------------------------------------------------------------
# `*.bundle.js` files under public/js are discovered automatically by the
# esbuild-based builder in Frappe v15 - no build.json is needed.
app_include_js = ["language_switcher.bundle.js", "workspace_context.bundle.js"]

# ------------------------------------------------------------------------------
# Installation
# ------------------------------------------------------------------------------
after_install = "ndserp.install.after_install"
after_migrate = "ndserp.install.after_migrate"
before_uninstall = "ndserp.install.before_uninstall"

# ------------------------------------------------------------------------------
# Workspace scoping (see ndserp/setup/workspace_scope.py)
# ------------------------------------------------------------------------------
# Adds `bootinfo.ndserp_workspace_doctypes`, consumed by
# workspace_context.bundle.js to keep the sidebar/breadcrumb on an Ndserp
# workspace when a DocType link inside it belongs to a different module.
boot_session = "ndserp.setup.workspace_scope.extend_bootinfo"

# `patch_workspace_permission()` is also called at import time
# (ndserp/__init__.py), but under a preloaded gunicorn master each worker
# lazily loads site apps on its own first request, and that one-shot call is
# guarded by a bare `except Exception: pass` (no site/db context is
# guaranteed at import time). A worker that hits a transient failure there
# would otherwise run unpatched - silently showing every foreign workspace to
# Ndserp-scoped users - for its entire process lifetime. Re-running it here on
# every request is a cheap no-op once patched (single attribute check), and
# makes that failure mode self-heal within one request instead of persisting.
before_request = [
	"ndserp.setup.workspace_scope.patch_workspace_permission",
	"ndserp.setup.custom_report_policy.patch_custom_report_section",
]

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------
# Rules for this list - keep them, they are what keeps the app safe to install
# on any site:
#
#   1. Never export a doctype without filters. `{"dt": "Client Script"}` exports
#      the client scripts of *every* installed app into this repo.
#   2. Never export records owned by another app (module = Accounts, Regional,
#      Selling, ...). Re-importing them overwrites the original app's copy on
#      every `bench migrate`.
#   3. Never export `is_system_generated` records - those are created by
#      framework/app code and are recreated automatically.
#
# To ship something new with the app, set its **Module = Ndserp** in the UI,
# then run `bench --site <site> export-fixtures --app ndserp`.

# Doctypes whose Customize Form output (Property Setter) belongs to ndserp.
# Property setters modify *standard* fields - hiding rounded totals, in_words,
# tax_id and so on - which is exactly this app's job. Add a doctype here when
# you start customising it.
CUSTOMISED_DOCTYPES = [
	"Sales Invoice",
	"Purchase Order",
]

# Custom fields are matched by name, never by doctype.
#
# Other apps add their own fields to the same doctypes - pos_next adds
# `posa_pos_opening_shift`, `posa_is_printed` and `pos_applied_one_time_rules`
# to Sales Invoice, and Frappe itself adds `ta_amend_archived`. A `dt`-based
# filter would drag all of them into this repo and make ndserp fight the app
# that actually owns them on every migrate.
#
# When you add a custom field of your own, put its `name` (doctype-fieldname)
# here and re-run export-fixtures.
NDSERP_CUSTOM_FIELDS: list[str] = [
	# "Sales Invoice-ndserp_example_field",
]

# Site-owned roles (not shipped by Frappe/ERPNext/HRMS). Matched by name.
# Re-export from ndserpsa after adding a role: `bench --site ndserpsa.nds-sa.com export-fixtures --app ndserp`
NDSERP_ROLES: list[str] = [
	"HR NDS",
	"NDS Module Manager",
	"POSNext",
	"role & permissions",
	"الاصول NDS ERP",
	"المبيعات NDS ERP",
	"المشتريات NDS ERP",
	"الملفات الرئيسية NDS ERP",
	"حسابات NDS ERP",
	"مخازن NDS ERP",
	"نقاط البيع NDS ERP",
]

# Role profiles synced from ndserpsa (includes standard-named bundles plus NDS packs).
# Single-module ``* Manager NDS`` / ``* User NDS`` packs are the day-to-day profiles.
# ``Small Next`` / ``MID Next`` remain owner multi-module packs only.
NDSERP_ROLE_PROFILES: list[str] = [
	"Accounts",
	"Accounts Manager NDS",
	"Accounts User NDS",
	"Assets Manager NDS",
	"Assets User NDS",
	"HR Manager NDS",
	"HR User NDS",
	"Inventory",
	"Manufacturing",
	"MID Next",
	"POS Manager NDS",
	"POS User NDS",
	"Purchase",
	"Purchase Manager NDS",
	"Purchase User NDS",
	"Sales",
	"Sales Manager NDS",
	"Sales User NDS",
	"Small Next",
	"Stock Manager NDS",
	"Stock User NDS",
]

# Custom DocPerm rows that grant module managers limited User create rights.
NDSERP_CUSTOM_DOCPERM_ROLES: list[str] = [
	"NDS Module Manager",
]

fixtures = [
	# Roles first so Role Profile child rows resolve on import.
	{"dt": "Role", "filters": [["name", "in", NDSERP_ROLES]]},
	{"dt": "Role Profile", "filters": [["name", "in", NDSERP_ROLE_PROFILES]]},
	{
		"dt": "Custom DocPerm",
		"filters": [["role", "in", NDSERP_CUSTOM_DOCPERM_ROLES]],
	},
	# Arabic Ndserp workspaces (incl. POS when pos_next is present). Single source of truth.
	{"dt": "Workspace", "filters": [["module", "=", "Ndserp"]]},
	# Customize Form output for the doctypes above.
	{"dt": "Property Setter", "filters": [["doc_type", "in", CUSTOMISED_DOCTYPES]]},
	# Scripts, print formats and reports are only exported when they are
	# explicitly assigned to the Ndserp module.
	{"dt": "Client Script", "filters": [["module", "=", "Ndserp"]]},
	{"dt": "Server Script", "filters": [["module", "=", "Ndserp"]]},
	{"dt": "Print Format", "filters": [["module", "=", "Ndserp"]]},
	{"dt": "Report", "filters": [["module", "=", "Ndserp"]]},
]

if NDSERP_CUSTOM_FIELDS:
	# Only registered when the whitelist is non-empty: an empty `in ()` filter
	# is not valid SQL.
	fixtures.append({"dt": "Custom Field", "filters": [["name", "in", NDSERP_CUSTOM_FIELDS]]})

# ------------------------------------------------------------------------------
# Document events
# ------------------------------------------------------------------------------
# Module managers (NDS Module Manager) may create Users only with their
# module's ``* User NDS`` Role Profile — see setup/user_provisioning.py.
doc_events = {
	"User": {
		"validate": "ndserp.setup.user_provisioning.validate_user",
	},
	"Report": {
		"validate": "ndserp.setup.custom_report_policy.reject_nonstandard_report",
	},
}

# Module managers only list/open Users in their module packs (plus themselves),
# and only see their module's Role Profiles in the link picker.
permission_query_conditions = {
	"User": "ndserp.setup.user_provisioning.get_permission_query_conditions",
	"Role Profile": "ndserp.setup.user_provisioning.get_role_profile_permission_query_conditions",
}

has_permission = {
	"User": "ndserp.setup.user_provisioning.has_permission",
	"Role Profile": "ndserp.setup.user_provisioning.role_profile_has_permission",
}

# Desk JS: filter Role Profiles on User form for module managers.
doctype_js = {
	"User": "public/js/user.js",
}

jinja = {
	"methods": [
		"ndserp.jinja.get_ndserp_zatca_phase_1_qr",
		"ndserp.jinja.get_arabic_amount_in_words",
	],
}

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# BEGIN NDSERP PAYMENT ENTRY EXPENSES EXTENSION
_ndserp_extend_doctype_class = globals().get("extend_doctype_class", {})

if not isinstance(_ndserp_extend_doctype_class, dict):
    raise TypeError("extend_doctype_class must be a dict")

_ndserp_payment_entry_extensions = _ndserp_extend_doctype_class.get(
    "Payment Entry", []
)

if isinstance(_ndserp_payment_entry_extensions, str):
    _ndserp_payment_entry_extensions = [
        _ndserp_payment_entry_extensions
    ]
else:
    _ndserp_payment_entry_extensions = list(
        _ndserp_payment_entry_extensions or []
    )

if (
    "ndserp.overrides.payment_entry_expenses.PaymentEntryExpensesMixin"
    not in _ndserp_payment_entry_extensions
):
    _ndserp_payment_entry_extensions.append(
        "ndserp.overrides.payment_entry_expenses.PaymentEntryExpensesMixin"
    )

_ndserp_extend_doctype_class["Payment Entry"] = (
    _ndserp_payment_entry_extensions
)

extend_doctype_class = _ndserp_extend_doctype_class
# END NDSERP PAYMENT ENTRY EXPENSES EXTENSION
