app_name = "amir_theme_v16"
app_title = "Amir Theme v16"
app_publisher = "Eng. Amir Mansi"
app_description = "Professional bilingual (AR/EN) ERP theme for ERPNext v16 — dual sidebar with workspace rail, RTL-aware layout, navy/gold palette, and a branded login page."
app_email = "amirahmd12300@gmail.com"
app_license = "MIT"
frappe_version = ">=16.0.0 <17.0.0"
categories = ["Customization", "UI/UX"]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "amir_theme_v16",
# 		"logo": "/assets/amir_theme_v16/logo.png",
# 		"title": "Amir Theme",
# 		"route": "/amir_theme_v16",
# 		"has_permission": "amir_theme_v16.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# Bundled (not static paths) so esbuild emits an auto-flipped RTL variant for Arabic.
app_include_css = ["amir_theme.bundle.css", "/assets/amir_theme_v16/css/translation_mode.css", "/assets/amir_theme_v16/css/logo-transparent.css"]
app_include_js = ["amir_theme.bundle.js", "/assets/amir_theme_v16/js/translation_mode.js"]

# include js, css files in header of web template
# Branded login page. Injected around Frappe's own login form rather than
# replacing www/login.py, so upstream auth/security fixes still apply.
web_include_css = ["login_brand.bundle.css", "/assets/amir_theme_v16/css/logo-transparent.css"]
web_include_js = "login_brand.bundle.js"

# Adds the current user's last_login to bootinfo so the desk status bar can
# render it without an extra request. See boot.py for the scope rationale.
extend_bootinfo = "amir_theme_v16.boot.extend_bootinfo"

# Inlines the login-page branding into <head> so the stock Frappe login card is
# never painted and never has to be fetched over HTTP first. See website.py for
# the render order this works around.
update_website_context = "amir_theme_v16.website.update_website_context"


# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "amir_theme_v16/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "amir_theme_v16/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "amir_theme_v16.utils.jinja_methods",
# 	"filters": "amir_theme_v16.utils.jinja_filters"
# }

# Installation
# ------------

# Provisions the Permission Manager checkboxes for the Smart Submit Action
# buttons (see api/smart_action_permissions.py) — idempotent, one-time
# backfill per doctype on first run, no-op on every run after that.
after_install = "amir_theme_v16.install.after_install"
after_migrate = "amir_theme_v16.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "amir_theme_v16.uninstall.before_uninstall"
# after_uninstall = "amir_theme_v16.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "amir_theme_v16.utils.before_app_install"
# after_app_install = "amir_theme_v16.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "amir_theme_v16.utils.before_app_uninstall"
# after_app_uninstall = "amir_theme_v16.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "amir_theme_v16.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"amir_theme_v16.tasks.all"
# 	],
# 	"daily": [
# 		"amir_theme_v16.tasks.daily"
# 	],
# 	"hourly": [
# 		"amir_theme_v16.tasks.hourly"
# 	],
# 	"weekly": [
# 		"amir_theme_v16.tasks.weekly"
# 	],
# 	"monthly": [
# 		"amir_theme_v16.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "amir_theme_v16.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "amir_theme_v16.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "amir_theme_v16.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "amir_theme_v16.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["amir_theme_v16.utils.before_request"]
# after_request = ["amir_theme_v16.utils.after_request"]

# Job Events
# ----------
# before_job = ["amir_theme_v16.utils.before_job"]
# after_job = ["amir_theme_v16.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"amir_theme_v16.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# --- NDS ERP Accounts Workspace UI Scope ---
if "app_include_js" not in globals() or app_include_js is None:
    app_include_js = []

if isinstance(app_include_js, str):
    app_include_js = [app_include_js]
elif isinstance(app_include_js, tuple):
    app_include_js = list(app_include_js)

if '/assets/amir_theme_v16/js/ndserp_accounts_workspace_scope.js' not in app_include_js:
    app_include_js.append('/assets/amir_theme_v16/js/ndserp_accounts_workspace_scope.js')
# --- End NDS ERP Accounts Workspace UI Scope ---

# NDS ROOT LOGIN UNIFICATION
# Always use the canonical Desk login screen for the site root.
try:
    website_redirects
except NameError:
    website_redirects = []

website_redirects += [
    {
        "source": "/",
        "target": "/login?redirect-to=%2Fdesk",
        "redirect_http_status": 302,
    }
]

