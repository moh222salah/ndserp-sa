app_name = "contracting"
app_title = "Contracting"
app_publisher = "Ahmed"
app_description = "Enterprise Construction / Contracting solution built on ERPNext v16"
app_email = ""
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ---------------------------------------------------------------------------
# Fixtures (roles, workflows, property setters, custom fields, naming series)
# are added in the roles/workflow phase. Kept empty here so a clean install
# does not fail on not-yet-created records.
# ---------------------------------------------------------------------------
fixtures = []

# ---------------------------------------------------------------------------
# Document events — ERPNext source adapters are wired in the Cost phase.
# Left empty in Phase 1 (nothing here depends on unconfirmed legacy formulas).
# ---------------------------------------------------------------------------
doc_events = {}

# scheduler_events = {}

# ---------------------------------------------------------------------------
# Installation hooks
# ---------------------------------------------------------------------------
after_install = "contracting.setup.install.after_install"
after_migrate = "contracting.setup.install.after_install"

# ---------------------------------------------------------------------------
# Client scripts
# ---------------------------------------------------------------------------
app_include_js = ["/assets/contracting/js/cost_dimensions.js"]

doctype_js = {
	"Purchase Invoice": "public/js/pi.js",
	"Stock Entry": "public/js/se.js",
	"Journal Entry": "public/js/je.js",
	"Expense Claim": "public/js/expense.js",
	"Salary Slip": "public/js/salary.js",
	"Subcontract IPC": "public/js/sipc.js",
	"Tender": "public/js/tender.js",
}
