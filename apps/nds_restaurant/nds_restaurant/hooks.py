from . import __version__ as app_version

app_name = "nds_restaurant"
app_title = "NDS Restaurant"
app_publisher = "NDS"
app_description = "Restaurant POS System built on ERPNext/Frappe"
app_email = "support@nds.local"
app_license = "MIT"
app_logo_url = "/assets/nds_restaurant/Images/nds-logo.svg"
app_icon_title = "NDS Restaurant"

required_apps = ["erpnext", "hrms"]

add_to_apps_screen = [
	{
		"name": "nds_restaurant",
		"logo": "/assets/nds_restaurant/Images/nds-logo.svg",
		"title": "NDS Restaurant",
		"route": "/desk/restaurant",
		"has_permission": "nds_restaurant.permission.check_app_permission",
	}
]

app_include_js = [
	"/assets/nds_restaurant/js/pos_print.js",
]

web_include_js = []

page_renderer = ["nds_restaurant.pos_route.POSNextPage"]

website_route_rules = [
	{"from_route": "/restaurant-pos/<path:app_path>", "to_route": "restaurant-pos"},
	{"from_route": "/kotdisplay/<path:app_path>", "to_route": "kotdisplay"},
]

fixtures = [
	{
		"dt": "Role",
		"filters": [["name", "in", ["NDS Manager", "NDS Cashier", "NDS Captain"]]],
	},
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "NDS Restaurant"]],
	},
]

doc_events = {
	"POS Invoice": {
		"before_naming": "nds_restaurant.api.naming.set_pos_invoice_naming",
		"on_submit": "nds_restaurant.api.recipe.on_pos_invoice_submit",
		"on_cancel": "nds_restaurant.api.recipe.on_pos_invoice_cancel",
		"on_update": "nds_restaurant.api.kot.on_pos_invoice_update",
		"on_trash": "nds_restaurant.api.kot.on_pos_invoice_trash",
	},
	"Sales Invoice": {
		"before_naming": "nds_restaurant.api.naming.set_sales_invoice_naming",
	},
	"POS Opening Entry": {
		"validate": "nds_restaurant.api.multi_cashier.validate_pos_opening",
	},
	"POS Closing Entry": {
		"validate": "nds_restaurant.api.multi_cashier.validate_pos_closing",
	},
	"Item": {
		"validate": "nds_restaurant.api.items.validate_item_links",
	},
}

scheduler_events = {
	"hourly": [
		"nds_restaurant.api.kot.check_kot_delays",
	],
}

after_install = "nds_restaurant.install.after_install"
after_migrate = "nds_restaurant.install.after_migrate"
