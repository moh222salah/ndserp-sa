"""Idempotent post-install provisioning for the Contracting app.

Creates the role set, applies the permission matrix (as additive Custom
DocPerms, so a re-run is safe), and sets up workflows that drive the existing
`status` Select field on the core transactional DocTypes.

Everything checks-before-create, so this can also be re-run from a patch or
`bench execute contracting.setup.install.after_install`.
"""
import frappe
from frappe.permissions import add_permission, update_permission_property

MODULES = [
	"Contracting Setup", "Contracting Tender", "Contracting Commercial",
	"Contracting Execution", "Contracting Procurement",
	"Contracting Subcontract", "Contracting Cost",
]

ROLES = [
	"Contracting Administrator", "Contracts Manager", "Estimation Engineer",
	"Commercial Manager", "Quantity Surveyor", "Project Manager",
	"Site Engineer", "Procurement Officer", "Subcontracts Manager",
	"Cost Controller", "Planning Engineer", "Accounts User (Contracting)",
	"Document Controller", "Contracting User", "Contracting Reviewer",
	"Contracting Auditor",
]

FULL = dict(read=1, write=1, create=1, delete=1, submit=1, cancel=1,
			report=1, export=1, print=1, email=1, share=1)
RW = dict(read=1, write=1, create=1, report=1, export=1, print=1, share=1)
RO = dict(read=1, report=1, export=1, print=1)

# role -> list of (module or "*", profile)
MATRIX = {
	"Contracting Administrator": [("*", FULL)],
	"Contracts Manager": [
		("Contracting Commercial", FULL), ("Contracting Tender", RW),
		("Contracting Execution", RW), ("Contracting Subcontract", RW),
		("Contracting Procurement", RO), ("Contracting Cost", RO),
		("Contracting Setup", RO)],
	"Estimation Engineer": [
		("Contracting Tender", FULL), ("Contracting Commercial", RO),
		("Contracting Setup", RO)],
	"Commercial Manager": [
		("Contracting Commercial", FULL), ("Contracting Tender", RW),
		("Contracting Subcontract", RW), ("Contracting Cost", RW),
		("Contracting Execution", RO), ("Contracting Setup", RO)],
	"Quantity Surveyor": [
		("Contracting Commercial", RW), ("Contracting Execution", RW),
		("Contracting Subcontract", RW), ("Contracting Setup", RO)],
	"Project Manager": [
		("Contracting Execution", FULL), ("Contracting Commercial", RO),
		("Contracting Procurement", RO), ("Contracting Subcontract", RO),
		("Contracting Cost", RO)],
	"Site Engineer": [
		("Contracting Execution", RW), ("Contracting Commercial", RO),
		("Contracting Setup", RO)],
	"Procurement Officer": [
		("Contracting Procurement", FULL), ("Contracting Commercial", RO),
		("Contracting Execution", RO), ("Contracting Setup", RO)],
	"Subcontracts Manager": [
		("Contracting Subcontract", FULL), ("Contracting Commercial", RO),
		("Contracting Execution", RO), ("Contracting Setup", RO)],
	"Cost Controller": [
		("Contracting Cost", FULL), ("Contracting Commercial", RO),
		("Contracting Execution", RO), ("Contracting Subcontract", RO),
		("Contracting Procurement", RO)],
	"Planning Engineer": [
		("Contracting Execution", RW), ("Contracting Cost", RW),
		("Contracting Commercial", RO), ("Contracting Setup", RO)],
	"Accounts User (Contracting)": [
		("Contracting Commercial", RO), ("Contracting Subcontract", RO),
		("Contracting Cost", RO)],
	"Document Controller": [("*", RO)],
	"Contracting User": [
		("Contracting Setup", RO), ("Contracting Commercial", RO),
		("Contracting Execution", RO)],
	"Contracting Reviewer": [
		("Contracting Commercial", RW), ("Contracting Tender", RW),
		("Contracting Subcontract", RW)],
	"Contracting Auditor": [("*", RO)],
}

# workflow specs: doctype -> (states[(state, allow_edit_role)], transitions[(from, action, to, allowed_role)])
WORKFLOWS = {
	"Construction Contract": (
		[("Draft", "Contracts Manager"), ("Review", "Commercial Manager"),
		 ("Approved", "Contracting Administrator"), ("Active", "Contracts Manager"),
		 ("Suspended", "Contracts Manager"), ("Completed", "Project Manager"),
		 ("Closed", "Contracting Administrator")],
		[("Draft", "Submit for Review", "Review", "Contracts Manager"),
		 ("Review", "Approve", "Approved", "Commercial Manager"),
		 ("Review", "Return to Draft", "Draft", "Commercial Manager"),
		 ("Approved", "Activate", "Active", "Contracts Manager"),
		 ("Active", "Suspend", "Suspended", "Contracts Manager"),
		 ("Suspended", "Resume", "Active", "Contracts Manager"),
		 ("Active", "Complete", "Completed", "Project Manager"),
		 ("Completed", "Close", "Closed", "Contracting Administrator")]),
	"Contract Variation": (
		[("Draft", "Quantity Surveyor"), ("Review", "Commercial Manager"),
		 ("Approved", "Commercial Manager"), ("Rejected", "Commercial Manager"),
		 ("Cancelled", "Contracts Manager")],
		[("Draft", "Submit for Review", "Review", "Quantity Surveyor"),
		 ("Review", "Approve", "Approved", "Commercial Manager"),
		 ("Review", "Reject", "Rejected", "Commercial Manager"),
		 ("Draft", "Cancel", "Cancelled", "Contracts Manager")]),
	"Tender": (
		[("Draft", "Estimation Engineer"), ("Preparing", "Estimation Engineer"),
		 ("Review", "Commercial Manager"), ("Approved", "Commercial Manager"),
		 ("Submitted", "Contracts Manager"), ("Awarded", "Contracts Manager"),
		 ("Lost", "Contracts Manager"), ("Closed", "Contracting Administrator")],
		[("Draft", "Start Preparation", "Preparing", "Estimation Engineer"),
		 ("Preparing", "Submit for Review", "Review", "Estimation Engineer"),
		 ("Review", "Approve", "Approved", "Commercial Manager"),
		 ("Approved", "Submit to Client", "Submitted", "Contracts Manager"),
		 ("Submitted", "Mark Awarded", "Awarded", "Contracts Manager"),
		 ("Submitted", "Mark Lost", "Lost", "Contracts Manager"),
		 ("Awarded", "Close", "Closed", "Contracting Administrator")]),
	"Subcontract": (
		[("Draft", "Subcontracts Manager"), ("Review", "Commercial Manager"),
		 ("Approved", "Commercial Manager"), ("Active", "Subcontracts Manager"),
		 ("Suspended", "Subcontracts Manager"), ("Completed", "Project Manager"),
		 ("Closed", "Contracting Administrator")],
		[("Draft", "Submit for Review", "Review", "Subcontracts Manager"),
		 ("Review", "Approve", "Approved", "Commercial Manager"),
		 ("Approved", "Activate", "Active", "Subcontracts Manager"),
		 ("Active", "Complete", "Completed", "Project Manager"),
		 ("Completed", "Close", "Closed", "Contracting Administrator")]),
}


def after_install():
	create_roles()
	apply_permissions()
	setup_workflows()
	setup_workspace()
	setup_project_fields()
	setup_cost_dimension_fields()
	frappe.db.commit()


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Role", "role_name": role,
				"desk_access": 1, "two_factor_auth": 0,
			}).insert(ignore_permissions=True)


def _our_doctypes(module=None):
	filters = {"istable": 0}
	filters["module"] = module if module else ["in", MODULES]
	return frappe.get_all("DocType", filters=filters, pluck="name")


def apply_permissions():
	for role, entries in MATRIX.items():
		for module, profile in entries:
			doctypes = _our_doctypes(None if module == "*" else module)
			for dt in doctypes:
				try:
					add_permission(dt, role, 0)
					for ptype, val in profile.items():
						update_permission_property(dt, role, 0, ptype, val, validate=False)
				except Exception:
					frappe.log_error(f"perm {role}->{dt}", "Contracting install")


def _ensure_workflow_state(state):
	if not frappe.db.exists("Workflow State", state):
		frappe.get_doc({
			"doctype": "Workflow State", "workflow_state_name": state,
			"style": _style_for(state),
		}).insert(ignore_permissions=True)


def _ensure_action(action):
	if not frappe.db.exists("Workflow Action Master", action):
		frappe.get_doc({
			"doctype": "Workflow Action Master", "workflow_action_name": action,
		}).insert(ignore_permissions=True)


def _style_for(state):
	s = state.lower()
	if any(k in s for k in ("approved", "active", "awarded", "completed")):
		return "Success"
	if any(k in s for k in ("reject", "lost", "cancel", "suspend")):
		return "Danger"
	if any(k in s for k in ("review", "preparing", "submitted")):
		return "Warning"
	if "closed" in s:
		return "Inverse"
	return "Primary"


def setup_workflows():
	for doctype, (states, transitions) in WORKFLOWS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		wf_name = f"{doctype} Workflow"
		if frappe.db.exists("Workflow", wf_name):
			continue
		for state, _role in states:
			_ensure_workflow_state(state)
		for _f, action, _t, _r in transitions:
			_ensure_action(action)

		wf = frappe.get_doc({
			"doctype": "Workflow",
			"workflow_name": wf_name,
			"document_type": doctype,
			"workflow_state_field": "status",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [{
				"state": s, "doc_status": "0", "allow_edit": r,
			} for s, r in states],
			"transitions": [{
				"state": f_, "action": a, "next_state": t, "allowed": r,
				"allow_self_approval": 1,
			} for f_, a, t, r in transitions],
		})
		wf.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Workspace (sidebar menu) — created programmatically so it always appears,
# regardless of app-workspace file sync. Re-runnable:
#   bench --site <site> execute contracting.setup.install.setup_workspace
# ---------------------------------------------------------------------------
import json as _json

_CARDS = [
	("Commercial", [
		("Contract Variation", "Contract Variation"),
		("Contract Claim", "Contract Claim"),
		("Extension of Time", "Extension of Time"),
		("Contract Amendment", "Contract Amendment"),
		("Final Account", "Final Account"),
		("Contract Closeout", "Contract Closeout"),
	]),
	("Tender", [
		("Tender", "Tender"),
		("Tender BOQ Item", "Tender BOQ Item"),
	]),
	("Execution", [
		("WBS", "WBS"), ("WBS Allocation", "WBS Allocation"),
		("Executed Quantity", "Executed Quantity"),
		("Operation Measurement", "Operation Measurement"),
	]),
	("Procurement & Subcontract", [
		("Material Requirement", "Construction Material Requirement"),
		("Procurement Plan", "Procurement Plan"),
		("Subcontract", "Subcontract"),
		("Subcontract BOQ Item", "Subcontract BOQ Item"),
		("Subcontract BOQ Mapping", "Subcontract BOQ Mapping"),
		("Subcontract Variation", "Subcontract Variation"),
	]),
	("IPC", [
		("Client IPC", "Client IPC"), ("Subcontract IPC", "Subcontract IPC"),
	]),
	("Budget", [
		("Project Budget", "Project Budget"),
		("Budget BOQ Item", "Budget BOQ Item"),
		("Budget Per Cost Code", "Budget Per Cost Code"),
	]),
	("Setup", [
		("Construction Settings", "Construction Settings"),
		("CSI Code", "CSI Code"),
		("Cost Code", "Cost Code"),
		("Deduction Type", "Deduction Type"),
	]),
]
_REPORTS = ("Reports", [
	("Contract BOQ Status", "Contract BOQ Status"),
	("Client IPC Register", "Client IPC Register"),
	("Subcontract IPC Register", "Subcontract IPC Register"),
	("Variation Register", "Variation Register"),
	("Cost Code Budget vs Actual", "Cost Code Budget vs Actual"),
	("BOQ Budget vs Actual", "BOQ Budget vs Actual"),
	("Cost Control Summary", "Cost Control Summary"),
])
_SHORTCUTS = [
	("Project Budget", "Project Budget", "Blue"),
	("Client IPC", "Client IPC", "Green"),
	("Operation Measurement", "Operation Measurement", "Orange"),
	("Executed Quantity", "Executed Quantity", "Purple"),
]


def setup_workspace():
	name = "Contracting"
	# Only reference targets that actually exist, so a missing DocType or
	# Report can never make the workspace page fail to render.
	links = []
	surviving_cards = []
	for card_label, items in _CARDS:
		existing = [(lbl, lt) for (lbl, lt) in items
					if frappe.db.exists("DocType", lt)]
		if not existing:
			continue
		surviving_cards.append(card_label)
		links.append({"type": "Card Break", "label": card_label, "link_count": len(existing)})
		for lbl, link_to in existing:
			links.append({"type": "Link", "label": lbl, "link_to": link_to,
				"link_type": "DocType", "onboard": 0})
	rlabel, ritems = _REPORTS
	existing_reports = [(lbl, lt) for (lbl, lt) in ritems
						if frappe.db.exists("Report", lt)]
	if existing_reports:
		surviving_cards.append(rlabel)
		links.append({"type": "Card Break", "label": rlabel, "link_count": len(existing_reports)})
		for lbl, link_to in existing_reports:
			links.append({"type": "Link", "label": lbl, "link_to": link_to,
				"link_type": "Report", "is_query_report": 1, "onboard": 0})

	surviving_shortcuts = [(l, t, c) for (l, t, c) in _SHORTCUTS
						   if frappe.db.exists("DocType", t)]
	shortcuts = [{"type": "DocType", "label": l, "link_to": t, "color": c, "doc_view": "List"}
				 for (l, t, c) in surviving_shortcuts]

	content = [{"id": "hdr1", "type": "header",
				"data": {"text": '<span class="h4"><b>Contracting</b></span>', "col": 12}}]
	for i, (l, _t, _c) in enumerate(surviving_shortcuts):
		content.append({"id": f"sc{i}", "type": "shortcut", "data": {"shortcut_name": l, "col": 3}})
	content.append({"id": "sp1", "type": "spacer", "data": {"col": 12}})
	for i, card_label in enumerate(surviving_cards):
		content.append({"id": f"cd{i}", "type": "card", "data": {"card_name": card_label, "col": 4}})

	if frappe.db.exists("Workspace", name):
		ws = frappe.get_doc("Workspace", name)
		ws.set("links", [])
		ws.set("shortcuts", [])
	else:
		ws = frappe.new_doc("Workspace")
		ws.name = name

	ws.title = name
	ws.label = name
	ws.module = "Contracting Setup"
	ws.public = 1
	ws.is_hidden = 0
	ws.icon = "project"
	ws.sequence_id = 1.0
	ws.content = _json.dumps(content)
	for l in links:
		ws.append("links", l)
	for s in shortcuts:
		ws.append("shortcuts", s)
	ws.save(ignore_permissions=True)
	frappe.db.commit()
	return name


# ---------------------------------------------------------------------------
# Project custom fields — ERPNext Project is the single construction root.
# Added idempotently; re-runnable via
#   bench --site <site> execute contracting.setup.install.setup_project_fields
# ---------------------------------------------------------------------------
def setup_project_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	fields = {
		"Project": [
			{"fieldname": "contracting_sb", "label": "Contracting — Main Contract",
			 "fieldtype": "Section Break", "insert_after": "company", "collapsible": 1},
			{"fieldname": "contract_no", "label": "Contract No", "fieldtype": "Data",
			 "insert_after": "contracting_sb"},
			{"fieldname": "contract_type", "label": "Contract Type", "fieldtype": "Select",
			 "options": "\nLump Sum\nUnit Rate\nCost Plus\nMixed\nOther", "insert_after": "contract_no"},
			{"fieldname": "contract_date", "label": "Contract Date", "fieldtype": "Date",
			 "insert_after": "contract_type"},
			{"fieldname": "awarded_tender", "label": "Awarded Tender", "fieldtype": "Link",
			 "options": "Tender", "insert_after": "contract_date"},
			{"fieldname": "contracting_cb1", "fieldtype": "Column Break", "insert_after": "awarded_tender"},
			{"fieldname": "contract_currency", "label": "Contract Currency", "fieldtype": "Link",
			 "options": "Currency", "insert_after": "contracting_cb1"},
			{"fieldname": "contract_exchange_rate", "label": "Exchange Rate", "fieldtype": "Float",
			 "default": "1", "insert_after": "contract_currency"},
			{"fieldname": "original_start_date", "label": "Original Start Date", "fieldtype": "Date",
			 "insert_after": "contract_exchange_rate"},
			{"fieldname": "original_end_date", "label": "Original End Date", "fieldtype": "Date",
			 "insert_after": "original_start_date"},
			# contract value baseline
			{"fieldname": "contracting_value_sb", "label": "Contract Value",
			 "fieldtype": "Section Break", "insert_after": "original_end_date", "collapsible": 1},
			{"fieldname": "original_contract_value", "label": "Original Contract Value",
			 "fieldtype": "Currency", "insert_after": "contracting_value_sb",
			 "description": "Immutable baseline. Approved variations add to the current value."},
			{"fieldname": "current_contract_value", "label": "Current Contract Value",
			 "fieldtype": "Currency", "read_only": 1, "insert_after": "original_contract_value"},
			# construction account defaults (moved off Item Work)
			{"fieldname": "contracting_acc_sb", "label": "Construction Default Accounts",
			 "fieldtype": "Section Break", "insert_after": "current_contract_value", "collapsible": 1},
			{"fieldname": "default_cost_account", "label": "Default Cost Account", "fieldtype": "Link",
			 "options": "Account", "insert_after": "contracting_acc_sb"},
			{"fieldname": "contracting_acc_cb", "fieldtype": "Column Break", "insert_after": "default_cost_account"},
			{"fieldname": "default_revenue_account", "label": "Default Revenue Account", "fieldtype": "Link",
			 "options": "Account", "insert_after": "contracting_acc_cb"},
		]
	}
	create_custom_fields(fields, ignore_validate=True)
	frappe.db.commit()


# ---------------------------------------------------------------------------
# Phase 6 — construction cost dimensions on ERPNext source documents.
# Added as Custom Fields (upgrade-safe), re-runnable via
#   bench --site <site> execute contracting.setup.install.setup_cost_dimension_fields
# ---------------------------------------------------------------------------
def setup_cost_dimension_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	def dims(insert_after, with_project=False):
		base = [{"fieldname": "ct_cost_dim_sb", "label": "Construction Cost Dimensions",
				 "fieldtype": "Section Break", "insert_after": insert_after, "collapsible": 1}]
		after = "ct_cost_dim_sb"
		if with_project:
			base.append({"fieldname": "project", "label": "Project", "fieldtype": "Link",
						 "options": "Project", "insert_after": after}); after = "project"
		base += [
			{"fieldname": "ct_cost_code", "label": "Cost Code", "fieldtype": "Link",
			 "options": "Cost Code", "insert_after": after},
			{"fieldname": "ct_wbs", "label": "WBS", "fieldtype": "Link",
			 "options": "WBS", "insert_after": "ct_cost_code"},
			{"fieldname": "ct_boq_item", "label": "BOQ Item", "fieldtype": "Link",
			 "options": "Budget BOQ Item", "insert_after": "ct_wbs",
			 "description": "From the Project's approved Budget BOQ."},
		]
		return base

	fields = {
		"Purchase Invoice Item": dims("cost_center"),
		"Stock Entry Detail": dims("cost_center"),
		"Journal Entry Account": dims("cost_center"),
		"Expense Claim": dims("cost_center"),
		"Salary Slip": dims("company", with_project=True),
	}
	create_custom_fields(fields, ignore_validate=True)
	frappe.db.commit()
