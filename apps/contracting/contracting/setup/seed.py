"""Seed data for the Contracting app — Saudi construction projects.

Run:  bench --site <site> execute contracting.setup.seed.run
Idempotent: re-running skips what already exists.

Covers every app table: masters (CSI Code, Cost Code, Deduction Type,
Construction Settings), Project (contract baseline), Tender (+BOQ +indirect),
Project Budget (+Budget BOQ Items), Budget Per Cost Code, WBS (+Allocation),
Executed Quantity, Operation Measurement, Client IPC, Subcontract (+BOQ +Mapping
+Variation +IPC), Contract Variation/Claim/EOT/Amendment, Material Requirement,
Procurement Plan, Final Account, Contract Closeout, and (best-effort) a Journal
Entry carrying construction cost dimensions for the Budget-vs-Actual reports.
"""
import frappe
from frappe.utils import today, add_days, add_months


# --------------------------------------------------------------------------- helpers
def _exists(dt, filters):
	return frappe.db.exists(dt, filters)


def _goc(dt, filters, values):
	name = _exists(dt, filters)
	if name:
		return name
	doc = frappe.get_doc(dict(doctype=dt, **values))
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return doc.name


def _status(dt, name, status):
	frappe.db.set_value(dt, name, "status", status, update_modified=False)


def _first(dt, filters=None):
	return frappe.db.get_value(dt, filters or {}, "name")


# --------------------------------------------------------------------------- masters
def ensure_masters():
	company = frappe.defaults.get_global_default("company") or _first("Company")
	if not company:
		company = frappe.get_doc({"doctype": "Company", "company_name": "NDS Contracting SA",
			"abbr": "NDS", "default_currency": "SAR", "country": "Saudi Arabia"}).insert(
			ignore_permissions=True).name
	currency = frappe.db.get_value("Company", company, "default_currency") or "SAR"
	if frappe.db.exists("Currency", "SAR"):
		currency = "SAR"

	cust_group = _first("Customer Group", {"is_group": 0}) or "All Customer Groups"
	territory = _first("Territory", {"is_group": 0}) or "All Territories"
	supp_group = _first("Supplier Group", {"is_group": 0}) or "All Supplier Groups"
	item_group = _first("Item Group", {"is_group": 0}) or "All Item Groups"

	customers = {}
	for cn in ["Kingdom Holding Company", "Jeddah Development Co.",
			   "Eastern Province Industries", "Makkah Hospitality Group"]:
		customers[cn] = _goc("Customer", {"customer_name": cn},
			{"customer_name": cn, "customer_group": cust_group, "territory": territory})

	suppliers = {}
	for sn in ["Al-Rajhi Concrete Works", "Saudi Steel Fixing Est.",
			   "Gulf MEP Contractors", "Najd Finishing Co."]:
		suppliers[sn] = _goc("Supplier", {"supplier_name": sn},
			{"supplier_name": sn, "supplier_group": supp_group})

	# construction settings (single)
	cs = frappe.get_single("Construction Settings")
	cs.company = company
	cs.enable_cost_code = 1
	cs.enable_wbs = 1
	cs.enable_boq_item = 1
	cs.flags.ignore_mandatory = True
	cs.save(ignore_permissions=True)

	# deduction types
	for code, name_, cls in [("RET", "Retention", "Retention"),
							 ("ADV", "Advance Recovery", "Advance"),
							 ("VAT", "Output VAT", "Tax")]:
		_goc("Deduction Type", {"code": code},
			{"company": company, "code": code, "deduction_name": name_, "deduction_class": cls})

	# CSI Code tree
	csi = [("03", "Concrete", None, 1), ("03.30", "Cast-in-Place Concrete", "03", 1),
		   ("03.30.10", "Structural Concrete", "03.30", 0),
		   ("04", "Masonry", None, 1), ("04.20", "Unit Masonry", "04", 0),
		   ("31", "Earthwork", None, 1), ("31.20", "Earth Moving", "31", 0),
		   ("09", "Finishes", None, 0)]
	for code, name_, parent, grp in csi:
		_goc("CSI Code", {"code": code}, {"code": code, "csi_name": name_,
			"is_group": grp, "parent_csi_code": parent})

	# Cost Code tree
	cc = [("01", "Direct Cost", None, 1), ("01.01", "Material", "01", 0),
		  ("01.02", "Labour", "01", 0), ("01.03", "Equipment", "01", 0),
		  ("01.04", "Subcontract", "01", 0),
		  ("02", "Indirect Cost", None, 1), ("02.01", "Site Overhead", "02", 0),
		  ("02.02", "General Overhead", "02", 0)]
	for code, name_, parent, grp in cc:
		_goc("Cost Code", {"code": code}, {"company": company, "code": code,
			"cost_code_name": name_, "is_group": grp, "parent_cost_code": parent})

	# items (for optional material usage / procurement)
	items = {}
	for ic, nm in [("RMC-C35", "Ready Mix Concrete C35"), ("REBAR-B500", "Reinforcement Steel B500"),
				   ("CEMENT-OPC", "Portland Cement OPC")]:
		items[ic] = _goc("Item", {"item_code": ic},
			{"item_code": ic, "item_name": nm, "item_group": item_group, "stock_uom": "Nos",
			 "is_stock_item": 0})

	return dict(company=company, currency=currency, customers=customers,
				suppliers=suppliers, items=items)


# --------------------------------------------------------------------------- project chain
PROJECTS = [
	{"name": "Riyadh Tower", "customer": "Kingdom Holding Company", "value": 185000000,
	 "boq": [("31.20.01", "Site Excavation", "m³", 18000, 55, 72, "31.20"),
			 ("03.30.01", "Reinforced Concrete - Foundations", "m³", 9500, 1250, 1600, "03.30.10"),
			 ("03.30.02", "Reinforced Concrete - Structure", "m³", 14000, 1350, 1720, "03.30.10"),
			 ("04.20.01", "Block Work", "m²", 42000, 85, 115, "04.20"),
			 ("09.00.01", "Internal Finishes", "m²", 55000, 220, 290, "09")]},
	{"name": "Jeddah Corniche Mall", "customer": "Jeddah Development Co.", "value": 240000000,
	 "boq": [("31.20.01", "Bulk Earthworks", "m³", 32000, 48, 63, "31.20"),
			 ("03.30.01", "RC Raft Foundation", "m³", 12500, 1300, 1650, "03.30.10"),
			 ("03.30.02", "RC Columns & Slabs", "m³", 21000, 1400, 1800, "03.30.10"),
			 ("04.20.01", "Facade Block Work", "m²", 60000, 95, 128, "04.20"),
			 ("09.00.01", "Mall Finishes Package", "m²", 90000, 310, 410, "09")]},
	{"name": "Dammam Industrial Warehouse", "customer": "Eastern Province Industries", "value": 68000000,
	 "boq": [("31.20.01", "Site Grading", "m³", 25000, 40, 52, "31.20"),
			 ("03.30.01", "Ground Slab RC", "m³", 7000, 1150, 1480, "03.30.10"),
			 ("03.30.02", "Precast Columns Erection", "m³", 3200, 1600, 2050, "03.30.10"),
			 ("09.00.01", "Steel Cladding & Roofing", "m²", 38000, 180, 240, "09")]},
	{"name": "Makkah Grand Hotel", "customer": "Makkah Hospitality Group", "value": 320000000,
	 "boq": [("31.20.01", "Rock Excavation", "m³", 15000, 95, 120, "31.20"),
			 ("03.30.01", "RC Substructure", "m³", 16000, 1320, 1680, "03.30.10"),
			 ("03.30.02", "RC Superstructure", "m³", 28000, 1450, 1860, "03.30.10"),
			 ("04.20.01", "Partition Block Work", "m²", 72000, 90, 122, "04.20"),
			 ("09.00.01", "Luxury Finishes", "m²", 110000, 480, 640, "09")]},
]


def seed_project(spec, ctx):
	company, currency = ctx["company"], ctx["currency"]
	pname = spec["name"]
	customer = ctx["customers"][spec["customer"]]

	# ERPNext Project (construction root)
	project = _exists("Project", {"project_name": pname})
	if not project:
		p = frappe.get_doc({"doctype": "Project", "project_name": pname, "company": company,
			"customer": customer, "status": "Open", "expected_start_date": today(),
			"expected_end_date": add_months(today(), 18)})
		p.flags.ignore_mandatory = True
		p.insert(ignore_permissions=True)
		project = p.name
	# contract baseline custom fields
	frappe.db.set_value("Project", project, {
		"contract_no": "CT-" + pname.split()[0].upper(),
		"contract_type": "Unit Rate", "contract_date": today(),
		"contract_currency": currency, "contract_exchange_rate": 1,
		"original_contract_value": spec["value"], "current_contract_value": spec["value"],
		"original_start_date": today(), "original_end_date": add_months(today(), 18),
	}, update_modified=False)

	# guard: if already seeded (budget exists) skip transactional part
	if _exists("Project Budget", {"project": project}):
		return project

	# ---- Tender
	tender = frappe.get_doc({"doctype": "Tender", "company": company, "title": pname + " Tender",
		"customer": customer, "currency": currency, "tender_date": today(),
		"markup_percent": 28, "status": "Draft"})
	tender.append("indirect_costs", {"cost_type": "Site Overhead", "description": "Site establishment",
		"amount": spec["value"] * 0.04})
	tender.append("indirect_costs", {"cost_type": "General Overhead", "description": "HO allocation",
		"amount": spec["value"] * 0.03})
	tender.flags.ignore_mandatory = True
	tender.insert(ignore_permissions=True)
	for i, (bno, desc, unit, qty, cr, sr, csi) in enumerate(spec["boq"], 1):
		frappe.get_doc({"doctype": "Tender BOQ Item", "tender": tender.name, "boq_no": bno,
			"description": desc, "quantity": qty, "unit": unit, "csi_code": csi,
			"pricing_mode": "Direct Cost", "cost_rate": cr, "selling_rate": sr}).insert(ignore_permissions=True)
	_status("Tender", tender.name, "Awarded")

	# ---- Project Budget + Budget BOQ Items
	budget = frappe.get_doc({"doctype": "Project Budget", "project": project, "company": company,
		"currency": currency, "source_tender": tender.name, "budget_date": today(), "status": "Draft"})
	budget.flags.ignore_mandatory = True
	budget.insert(ignore_permissions=True)
	boq_names = []
	for bno, desc, unit, qty, cr, sr, csi in spec["boq"]:
		b = frappe.get_doc({"doctype": "Budget BOQ Item", "budget": budget.name, "boq_no": bno,
			"description": desc, "quantity": qty, "unit": unit, "csi_code": csi,
			"pricing_mode": "Direct Cost", "cost_rate": cr, "selling_rate": sr})
		b.insert(ignore_permissions=True)
		boq_names.append((b.name, bno, desc, unit, qty, cr, sr))
	_status("Project Budget", budget.name, "Approved")

	# ---- Budget Per Cost Code
	bpcc = frappe.get_doc({"doctype": "Budget Per Cost Code", "project": project,
		"description": "Financial cost-code budget", "status": "Draft"})
	for code, amt in [("01.01", spec["value"] * 0.35), ("01.02", spec["value"] * 0.18),
					  ("01.03", spec["value"] * 0.07), ("01.04", spec["value"] * 0.22),
					  ("02.01", spec["value"] * 0.05)]:
		if frappe.db.exists("Cost Code", code):
			bpcc.append("items", {"cost_code": code, "budget_amount": amt})
	bpcc.insert(ignore_permissions=True)
	_status("Budget Per Cost Code", bpcc.name, "Approved")

	# ---- WBS tree
	wbs_root = _goc("WBS", {"project": project, "wbs_code": "01"},
		{"project": project, "wbs_code": "01", "wbs_name": "Site Preparation", "is_group": 0})
	wbs_found = _goc("WBS", {"project": project, "wbs_code": "02"},
		{"project": project, "wbs_code": "02", "wbs_name": "Foundations", "is_group": 1})
	wbs_exc = _goc("WBS", {"project": project, "wbs_code": "02.01"},
		{"project": project, "wbs_code": "02.01", "wbs_name": "Excavation",
		 "parent_wbs": wbs_found, "is_group": 0})
	wbs_conc = _goc("WBS", {"project": project, "wbs_code": "02.02"},
		{"project": project, "wbs_code": "02.02", "wbs_name": "Concrete",
		 "parent_wbs": wbs_found, "is_group": 0})
	wbs_struct = _goc("WBS", {"project": project, "wbs_code": "03"},
		{"project": project, "wbs_code": "03", "wbs_name": "Structure", "is_group": 0})

	# ---- WBS Allocation + Executed Quantity + per-BOQ actuals
	for idx, (bname, bno, desc, unit, qty, cr, sr) in enumerate(boq_names):
		wbs = wbs_exc if "Excav" in desc or "Earth" in desc or "Grad" in desc else (
			wbs_conc if "Concrete" in desc or "RC" in desc or "Slab" in desc else wbs_struct)
		frappe.get_doc({"doctype": "WBS Allocation", "project": project, "wbs": wbs,
			"boq_item": bname, "planned_qty": qty, "unit": unit,
			"planned_amount": qty * cr}).insert(ignore_permissions=True)
		eq = frappe.get_doc({"doctype": "Executed Quantity", "project": project, "date": today(),
			"wbs": wbs, "boq_item": bname, "quantity": round(qty * 0.6, 2), "unit": unit,
			"reference": "Survey " + bno, "status": "Draft"})
		eq.insert(ignore_permissions=True)
		_status("Executed Quantity", eq.name, "Approved")

	# ---- Operation Measurement (period)
	om = frappe.get_doc({"doctype": "Operation Measurement", "project": project, "date": today(),
		"from_date": add_days(today(), -30), "to_date": today(), "status": "Draft"})
	for bname, bno, desc, unit, qty, cr, sr in boq_names:
		om.append("items", {"boq_item": bname, "unit": unit, "unit_price": sr,
			"qty": round(qty * 0.5, 2)})
	om.insert(ignore_permissions=True)
	_status("Operation Measurement", om.name, "Approved")

	# ---- Client IPC
	ipc = frappe.get_doc({"doctype": "Client IPC", "project": project,
		"customer": customer, "date": today(), "from_date": add_days(today(), -30),
		"to_date": today(), "currency": currency, "exchange_rate": 1,
		"advance_recovery_percent": 10, "retention_percent": 10,
		"output_tax_percent": 15, "status": "Draft"})
	for bname, bno, desc, unit, qty, cr, sr in boq_names:
		ipc.append("items", {"boq_item": bname, "unit": unit, "unit_price": sr,
			"current_qty": round(qty * 0.5, 2)})
	ipc.flags.ignore_mandatory = True
	ipc.insert(ignore_permissions=True)
	_status("Client IPC", ipc.name, "Approved")

	# ---- Subcontract chain
	supplier = list(ctx["suppliers"].values())[hash(pname) % len(ctx["suppliers"])]
	sc = frappe.get_doc({"doctype": "Subcontract", "company": company, "project": project,
		"supplier": supplier, "contract_date": today(), "start_date": today(),
		"end_date": add_months(today(), 12), "currency": currency, "exchange_rate": 1,
		"original_value": spec["value"] * 0.22, "status": "Draft",
		"description": "Concrete works subcontract"})
	sc.flags.ignore_mandatory = True
	sc.insert(ignore_permissions=True)
	_status("Subcontract", sc.name, "Active")
	sub_boq = []
	for i, (bname, bno, desc, unit, qty, cr, sr) in enumerate(boq_names[:2], 1):
		sb = frappe.get_doc({"doctype": "Subcontract BOQ Item", "subcontract": sc.name,
			"line_no": i, "boq_code": bno, "description": desc, "unit": unit,
			"qty": qty, "rate": round(cr * 0.9, 2), "client_boq_item": bname}).insert(ignore_permissions=True)
		sub_boq.append(sb.name)
		frappe.get_doc({"doctype": "Subcontract BOQ Mapping", "subcontract": sc.name,
			"client_boq_item": bname, "subcontract_boq_item": sb.name,
			"allocation_qty": qty, "allocation_percent": 100}).insert(ignore_permissions=True)
	# subcontract variation
	sv = frappe.get_doc({"doctype": "Subcontract Variation", "subcontract": sc.name,
		"date": today(), "variation_type": "Addition", "reason": "Additional concrete works",
		"status": "Draft"})
	sv.append("items", {"subcontract_boq_item": sub_boq[0], "change_type": "Quantity Change",
		"variation_qty": 500, "variation_rate": 1150})
	sv.insert(ignore_permissions=True)
	_status("Subcontract Variation", sv.name, "Approved")
	# subcontract IPC
	sipc = frappe.get_doc({"doctype": "Subcontract IPC", "subcontract": sc.name, "project": project,
		"supplier": supplier, "date": today(), "from_date": add_days(today(), -30),
		"to_date": today(), "currency": currency, "exchange_rate": 1,
		"retention_percent": 10, "status": "Draft", "ct_cost_code": "01.04"})
	for sbname in sub_boq:
		r = frappe.db.get_value("Subcontract BOQ Item", sbname, ["qty", "rate"], as_dict=True)
		sipc.append("items", {"subcontract_boq_item": sbname, "unit": "m³",
			"unit_price": r.rate, "current_qty": round((r.qty or 0) * 0.4, 2)})
	sipc.flags.ignore_mandatory = True
	sipc.insert(ignore_permissions=True)
	_status("Subcontract IPC", sipc.name, "Approved")

	# ---- Commercial changes
	var = frappe.get_doc({"doctype": "Contract Variation", "project": project, "date": today(),
		"variation_type": "Addition", "reason": "Client-requested scope addition", "status": "Draft"})
	var.append("items", {"change_type": "Quantity Change", "boq_item": boq_names[0][0],
		"variation_qty": 1000, "variation_rate": spec["boq"][0][5]})
	var.insert(ignore_permissions=True)
	_status("Contract Variation", var.name, "Approved")

	claim = frappe.get_doc({"doctype": "Contract Claim", "project": project,
		"claim_type": "Prolongation", "submission_date": today(),
		"description": "Delay due to late site handover", "status": "Draft"})
	claim.append("items", {"basis": "Extended preliminaries", "claimed_amount": spec["value"] * 0.02,
		"assessed_amount": spec["value"] * 0.015, "approved_amount": spec["value"] * 0.012})
	claim.insert(ignore_permissions=True)
	_status("Contract Claim", claim.name, "Approved")

	eot = frappe.get_doc({"doctype": "Extension of Time", "project": project, "request_date": today(),
		"from_date": today(), "requested_days": 60, "approved_days": 45,
		"reason": "Unforeseen ground conditions", "status": "Draft"})
	eot.insert(ignore_permissions=True)
	_status("Extension of Time", eot.name, "Approved")

	amd = frappe.get_doc({"doctype": "Contract Amendment", "project": project, "date": today(),
		"reason": "Formalize approved variations & EOT", "effective_date": today(),
		"status": "Draft", "reference": var.name})
	amd.append("items", {"affected_term": "Completion Date", "before_value": "18 months",
		"after_value": "19.5 months", "approved_impact": 0})
	amd.insert(ignore_permissions=True)
	_status("Contract Amendment", amd.name, "Approved")

	# ---- Procurement
	mr = frappe.get_doc({"doctype": "Construction Material Requirement", "company": company,
		"project": project, "required_date": add_days(today(), 14), "priority": "High",
		"status": "Draft"})
	for ic in list(ctx["items"].values())[:2]:
		mr.append("items", {"item_code": ic, "wbs": wbs_conc, "boq_item": boq_names[1][0],
			"required_qty": 500, "unit": "m³", "required_date": add_days(today(), 14)})
	mr.insert(ignore_permissions=True)
	_status("Construction Material Requirement", mr.name, "Approved")

	pp = frappe.get_doc({"doctype": "Procurement Plan", "company": company, "project": project,
		"plan_date": today(), "status": "Draft"})
	for ic in list(ctx["items"].values())[:2]:
		pp.append("items", {"item_code": ic, "boq_item": boq_names[1][0], "wbs": wbs_conc,
			"unit": "m³", "required_qty": 500, "planned_qty": 500, "received_qty": 200})
	pp.insert(ignore_permissions=True)
	_status("Procurement Plan", pp.name, "Active")

	# ---- recompute project current value from approved variations
	try:
		from contracting.services.variation_engine import recompute_project
		recompute_project(project)
	except Exception:
		pass

	# ---- Final Account + Closeout
	fa = frappe.get_doc({"doctype": "Final Account", "project": project, "date": today(),
		"currency": currency, "status": "Draft"})
	fa.flags.ignore_mandatory = True
	fa.insert(ignore_permissions=True)
	_status("Final Account", fa.name, "Review")

	clo = frappe.get_doc({"doctype": "Contract Closeout", "project": project, "date": today(),
		"status": "Draft"})
	clo.insert(ignore_permissions=True)  # default checklist auto-populated

	# ---- best-effort actual cost (Journal Entry carrying cost dimensions)
	_seed_actual_cost(project, company, boq_names)

	return project


def _seed_actual_cost(project, company, boq_names):
	"""Create a couple of submitted Journal Entries with construction dimensions,
	so the Budget-vs-Actual reports show data. Skipped if accounts are unavailable."""
	try:
		expense = frappe.db.get_value("Account",
			{"company": company, "root_type": "Expense", "is_group": 0}, "name")
		credit = frappe.db.get_value("Account",
			{"company": company, "root_type": "Liability", "is_group": 0}, "name") or \
			frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name")
		if not (expense and credit):
			return
		for (bname, bno, desc, unit, qty, cr, sr), code in zip(boq_names[:2], ["01.01", "01.04"]):
			amt = round(qty * cr * 0.3, 2)
			je = frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Journal Entry",
				"company": company, "posting_date": today(),
				"user_remark": "Seed actual cost " + desc})
			je.append("accounts", {"account": expense, "debit_in_account_currency": amt, "debit": amt,
				"project": project, "ct_cost_code": code, "ct_boq_item": bname})
			je.append("accounts", {"account": credit, "credit_in_account_currency": amt, "credit": amt})
			je.flags.ignore_mandatory = True
			je.insert(ignore_permissions=True)
			je.submit()
	except Exception:
		frappe.db.rollback()


# --------------------------------------------------------------------------- entry point
def run():
	ctx = ensure_masters()
	created = []
	for spec in PROJECTS:
		try:
			created.append(seed_project(spec, ctx))
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Contracting seed: " + spec["name"])
	frappe.db.commit()
	print("Seeded projects:", ", ".join(created))
	return created
