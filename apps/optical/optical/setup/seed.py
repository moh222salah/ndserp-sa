"""Demo data for the Optical Retail app (Saudi market, Arabic names).

Run on a site that has finished the ERPNext setup wizard:

    bench --site <site> backup
    bench --site <site> execute optical.setup.seed.run

Idempotent: re-running skips records that already exist. Every demo order carries the note in
SEED_TAG so it can be recognised. There is no automatic removal, so use a test site or restore a backup.
"""
import random

import frappe
from frappe.utils import add_days, nowdate

SEED_TAG = "بيانات تجريبية"

MALE = ["محمد", "عبدالله", "فهد", "سلطان", "خالد", "سعود", "تركي", "ناصر", "بندر", "عبدالرحمن",
        "فيصل", "ماجد", "نايف", "يزيد"]
FEMALE = ["نورة", "سارة", "منيرة", "هند", "ريم", "لطيفة", "العنود", "الجوهرة", "مها", "وفاء"]
FATHERS = ["عبدالعزيز", "سعد", "فهد", "محمد", "ناصر", "سلمان", "إبراهيم", "مشعل", "عبدالله", "صالح"]
FAMILIES = ["العتيبي", "القحطاني", "الدوسري", "الغامدي", "الشهري", "الزهراني", "المطيري", "الحربي",
            "السبيعي", "العنزي", "الشمري", "البقمي", "الخالدي", "العسيري", "اليامي", "الرشيدي"]

BRANDS = ["Ray-Ban", "Oakley", "Police", "Carrera", "Silhouette", "Guess"]

# (code, brand, model, frame_type, material, shape, gender, color, size, lens_w, bridge, temple, cost, price)
FRAMES = [
    ("FR-001", "Ray-Ban", "Classic 01", "Full Rim", "أسيتات", "مربع", "Unisex", "أسود", "52-18", 52, 18, 145, 260, 520),
    ("FR-002", "Ray-Ban", "Classic 02", "Full Rim", "معدن", "دائري", "Unisex", "ذهبي", "49-21", 49, 21, 140, 300, 590),
    ("FR-003", "Oakley", "Sport 10", "Full Rim", "O-Matter", "مستطيل", "Men", "رمادي", "55-17", 55, 17, 138, 340, 690),
    ("FR-004", "Oakley", "Sport 12", "Semi Rimless", "O-Matter", "مستطيل", "Men", "أسود", "53-18", 53, 18, 135, 360, 720),
    ("FR-005", "Police", "Urban 05", "Full Rim", "معدن", "أفياتور", "Men", "فضي", "57-16", 57, 16, 140, 280, 560),
    ("FR-006", "Police", "Urban 08", "Full Rim", "أسيتات", "مربع", "Men", "بني", "54-19", 54, 19, 145, 250, 480),
    ("FR-007", "Carrera", "Edge 21", "Full Rim", "معدن", "أفياتور", "Unisex", "أزرق", "56-17", 56, 17, 140, 270, 540),
    ("FR-008", "Silhouette", "Air 33", "Rimless", "تيتانيوم", "بيضاوي", "Women", "وردي", "50-18", 50, 18, 135, 520, 1050),
    ("FR-009", "Silhouette", "Air 35", "Rimless", "تيتانيوم", "مستطيل", "Unisex", "رمادي", "52-17", 52, 17, 135, 540, 1090),
    ("FR-010", "Guess", "Chic 07", "Full Rim", "أسيتات", "عين القطة", "Women", "أحمر", "51-17", 51, 17, 140, 190, 390),
    ("FR-011", "Guess", "Chic 09", "Full Rim", "أسيتات", "بيضاوي", "Women", "بني", "52-16", 52, 16, 140, 200, 410),
    ("FR-012", "Ray-Ban", "Kids 03", "Full Rim", "بلاستيك", "دائري", "Kids", "أزرق", "46-16", 46, 16, 125, 150, 300),
]

# (code, name, lens_type, material, index, coating, price_per_lens)
LENSES = [
    ("LN-SV-150", "عدسة أحادية 1.50", "Single Vision", "CR-39", "1.50", "", 120),
    ("LN-SV-156", "عدسة أحادية 1.56 بلو كت", "Single Vision", "CR-39", "1.56", "Blue Cut", 220),
    ("LN-SV-167", "عدسة أحادية 1.67 رقيقة", "Single Vision", "High Index", "1.67", "مضادة للانعكاس", 480),
    ("LN-CP-156", "عدسة كمبيوتر 1.56", "Computer", "CR-39", "1.56", "Blue Cut", 260),
    ("LN-PR-160", "عدسة متعددة البؤر 1.60", "Progressive", "High Index", "1.60", "مضادة للانعكاس", 780),
    ("LN-PR-167", "عدسة متعددة البؤر 1.67", "Progressive", "High Index", "1.67", "مضادة للانعكاس", 980),
    ("LN-PH-156", "عدسة متغيرة اللون 1.56", "Single Vision", "CR-39", "1.56", "Photochromic", 340),
]

COATINGS = [
    ("CT-AR", "معالجة مضادة للانعكاس", 90),
    ("CT-BC", "معالجة حجب الضوء الأزرق", 110),
    ("CT-SC", "طبقة مقاومة للخدش", 60),
]

# (code, name, cost, price, qty)
CONTACT_LENSES = [
    ("CL-D30", "عدسات لاصقة يومية (30 قطعة)", 70, 140, 24),
    ("CL-M06", "عدسات لاصقة شهرية (6 قطع)", 85, 170, 24),
    ("CL-CO06", "عدسات لاصقة ملونة شهرية", 60, 130, 24),
]
ACCESSORIES = [
    ("AC-CASE", "علبة نظارة", 6, 20, 60),
    ("AC-CLOTH", "قطعة تنظيف ميكروفايبر", 2, 10, 80),
    ("AC-SOL", "سائل تنظيف العدسات 60 مل", 8, 25, 40),
]

INSURERS = [
    ("بوبا العربية", [("بوبا - الفئة الذهبية", 90, 1500, 0), ("بوبا - الفئة الفضية", 80, 800, 50)]),
    ("التعاونية للتأمين", [("التعاونية - VIP", 100, 2000, 0), ("التعاونية - الفئة أ", 80, 900, 40)]),
    ("ميدغلف للتأمين", [("ميدغلف - الفئة ب", 70, 600, 50)]),
]

LABS = [
    ("المعمل الداخلي - الرياض", "Internal", None, 1),
    ("معمل الأفق للعدسات", "External", "معمل الأفق للعدسات", 3),
    ("معمل نظرة الدقيقة", "External", "معمل نظرة الدقيقة", 2),
]

QC_CHECKS = ["التحقق من الإطار", "التحقق من العدسة", "التحقق من وصفة النظر", "القياسات", "الفحص البصري"]


# --------------------------------------------------------------------------- helpers
def _context():
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        frappe.throw("Complete the ERPNext setup wizard (create a Company) before seeding demo data.")
    warehouses = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, pluck="name", limit=1)
    if not warehouses:
        frappe.throw("The company has no warehouse.")
    cost_center = frappe.get_cached_value("Company", company, "cost_center")
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
    currency = frappe.db.get_value("Price List", price_list, "currency") or frappe.get_cached_value(
        "Company", company, "default_currency")
    return frappe._dict(company=company, warehouse=warehouses[0], cost_center=cost_center,
                        price_list=price_list, currency=currency)


def _group(name):
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
                        "parent_item_group": "All Item Groups", "is_group": 0}).insert(ignore_permissions=True)
    return name


def _brand(name):
    if not frappe.db.exists("Brand", name):
        frappe.get_doc({"doctype": "Brand", "brand": name}).insert(ignore_permissions=True)


def _item(ctx, code, name, group, optical_type, price, stock, cost=0, **extra):
    if not frappe.db.exists("Item", code):
        doc = {"doctype": "Item", "item_code": code, "item_name": name, "item_group": group, "stock_uom": "Nos",
               "is_stock_item": 1 if stock else 0, "optical_item_type": optical_type, "standard_rate": price,
               "valuation_rate": cost if stock else 0, "include_item_in_manufacturing": 0}
        doc.update(extra)
        frappe.get_doc(doc).insert(ignore_permissions=True)
    if not frappe.db.exists("Item Price", {"item_code": code, "price_list": ctx.price_list}):
        frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": ctx.price_list,
                        "price_list_rate": price, "currency": ctx.currency, "selling": 1}).insert(ignore_permissions=True)


def _receive_stock(ctx, rows):
    rows = [r for r in rows if not frappe.db.get_value("Bin", {"item_code": r[0], "warehouse": ctx.warehouse}, "actual_qty")]
    if not rows:
        return 0
    try:
        se = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
            "company": ctx.company, "to_warehouse": ctx.warehouse,
            "items": [{"item_code": c, "qty": q, "basic_rate": r, "t_warehouse": ctx.warehouse} for c, q, r in rows],
        })
        se.insert(ignore_permissions=True)
        se.submit()
        return len(rows)
    except Exception:
        frappe.log_error(title="Optical seed: opening stock failed")
        print("WARNING: opening stock was skipped (see Error Log). Usually the company lacks a Stock Adjustment account.")
        return 0


def _names(rng, count):
    out, seen = [], set()
    while len(out) < count:
        female = len(out) % 5 in (1, 3)  # roughly 40% women
        first = rng.choice(FEMALE if female else MALE)
        father = rng.choice(FATHERS)
        family = rng.choice(FAMILIES)
        name = f"{first} {'بنت' if female else 'بن'} {father} {family}"
        if name not in seen:
            seen.add(name)
            out.append((name, female))
    return out


def _mobile(rng):
    return "05" + rng.choice("034568") + "".join(rng.choice("0123456789") for _ in range(7))


def _customer(name, mobile, territory, group):
    existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
    if existing:
        return existing
    cust = frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Individual",
                           "customer_group": group, "territory": territory, "language": "ar"})
    cust.insert(ignore_permissions=True)
    frappe.get_doc({"doctype": "Contact", "first_name": name,
                    "phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}],
                    "links": [{"link_doctype": "Customer", "link_name": cust.name}]}).insert(ignore_permissions=True)
    return cust.name


def _eye(rng, presbyope):
    sph = round(rng.randint(-24, 12) * 0.25, 2)
    cyl = 0 if rng.random() < 0.4 else -round(rng.randint(1, 10) * 0.25, 2)
    axis = rng.randint(1, 180) if cyl else 0
    add = round(rng.randint(4, 12) * 0.25, 2) if presbyope else 0
    return sph, cyl, axis, add


def _rx_values(rng, presbyope, shift=0.0):
    od = _eye(rng, presbyope)
    os_ = list(_eye(rng, presbyope))
    os_[0] = round(od[0] + rng.choice([-0.5, -0.25, 0, 0.25, 0.5]), 2)
    if presbyope:
        os_[3] = od[3]
    vals = {}
    pd_od, pd_os = rng.choice([28.5, 29, 29.5, 30, 30.5, 31, 31.5, 32]), rng.choice([28.5, 29, 29.5, 30, 30.5, 31, 31.5, 32])
    for side, (s, c, a, ad), pd in (("od", od, pd_od), ("os", tuple(os_), pd_os)):
        vals.update({f"{side}_sph": round(s + shift, 2), f"{side}_cyl": c, f"{side}_axis": a,
                     f"{side}_add": ad, f"{side}_pd": pd, f"{side}_va_distance": "6/6", f"{side}_va_near": "N6"})
    vals["binocular_pd"] = pd_od + pd_os
    return vals


def _make_rx(customer, date, values):
    exam = frappe.get_doc({"doctype": "Eye Examination", "customer": customer, "exam_date": date, **values})
    exam.insert(ignore_permissions=True)
    rx = frappe.get_doc({"doctype": "Optical Prescription", "customer": customer, "prescription_date": date,
                         "eye_examination": exam.name, "status": "Current", **values})
    rx.insert(ignore_permissions=True)
    return rx.name


def _rate(code):
    return frappe.db.get_value("Item", code, "standard_rate") or 0


def _order(ctx, customer, rx, days, frame, lens, coating, lab, plan, approved, discount, extra, progressive, rng):
    items = [{"item_code": frame, "item_role": "Frame", "qty": 1, "rate": _rate(frame)},
             {"item_code": lens, "item_role": "Right Lens", "qty": 1, "rate": _rate(lens)},
             {"item_code": lens, "item_role": "Left Lens", "qty": 1, "rate": _rate(lens)}]
    if coating:
        items.append({"item_code": coating, "item_role": "Coating", "qty": 1, "rate": _rate(coating)})
    if extra:
        items.append({"item_code": extra, "item_role": "Accessory", "qty": 1, "rate": _rate(extra)})
    doc = {"doctype": "Optical Order", "customer": customer, "prescription": rx, "company": ctx.company,
           "cost_center": ctx.cost_center, "warehouse": ctx.warehouse, "laboratory": lab,
           "order_date": add_days(nowdate(), -days), "discount_percent": discount, "notes": SEED_TAG,
           "insurance_plan": plan, "items": items}
    if plan and approved:
        doc.update({"insurance_approved": 1, "insurance_approval_no": f"APR-2026-{rng.randint(10000, 99999)}"})
    if progressive:
        doc.update({"od_fitting_height": rng.randint(16, 20), "os_fitting_height": rng.randint(16, 20)})
    order = frappe.get_doc(doc)
    order.insert(ignore_permissions=True)
    return order


def _advance(job_name, steps):
    job = frappe.get_doc("Optical Job", job_name)
    for _ in range(steps):
        job.advance_stage()
        job.reload()
    return job


# --------------------------------------------------------------------------- main
def run():
    rng = random.Random(2026)
    ctx = _context()
    counts = {}

    # Catalogue
    frames_g, lenses_g = _group("Frames"), _group("Optical Lenses")
    cl_g, acc_g = _group("Contact Lenses"), _group("Optical Accessories")
    services_g = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"
    for b in BRANDS:
        _brand(b)
    for code, brand, model, ftype, mat, shape, gender, color, size, lw, bridge, temple, cost, price in FRAMES:
        _item(ctx, code, f"{brand} {model} - {color}", frames_g, "Frame", price, True, cost, brand=brand,
              optical_model=model, frame_type=ftype, frame_material=mat, frame_shape=shape, frame_gender=gender,
              frame_color=color, frame_size=size, lens_width=lw, bridge_width=bridge, temple_length=temple)
    for code, name, ltype, mat, index, coating, price in LENSES:
        _item(ctx, code, name, lenses_g, "Lens", price, False, lens_type=ltype, lens_material=mat, lens_index=index,
              lens_coating=coating)
    for code, name, price in COATINGS:
        _item(ctx, code, name, services_g, "Service", price, False)
    for code, name, cost, price, _qty in CONTACT_LENSES:
        _item(ctx, code, name, cl_g, "Contact Lens", price, True, cost)
    for code, name, cost, price, _qty in ACCESSORIES:
        _item(ctx, code, name, acc_g, "Accessory", price, True, cost)
    stock_rows = [(f[0], 8, f[12]) for f in FRAMES] + [(c[0], c[4], c[2]) for c in CONTACT_LENSES] \
        + [(a[0], a[4], a[2]) for a in ACCESSORIES]
    counts["stock lines received"] = _receive_stock(ctx, stock_rows)

    # Insurance
    plans = []
    for company_name, plan_rows in INSURERS:
        if not frappe.db.exists("Insurance Company", company_name):
            frappe.get_doc({"doctype": "Insurance Company", "company_name": company_name}).insert(ignore_permissions=True)
        for plan_name, pct, max_cov, deductible in plan_rows:
            name = f"{company_name}-{plan_name}"
            if not frappe.db.exists("Insurance Plan", name):
                frappe.get_doc({"doctype": "Insurance Plan", "insurance_company": company_name, "plan_name": plan_name,
                                "coverage_percent": pct, "max_coverage": max_cov, "deductible": deductible,
                                "requires_approval": 1}).insert(ignore_permissions=True)
            plans.append(name)

    # Laboratories
    labs = []
    for lab_name, lab_type, supplier, days in LABS:
        if supplier and not frappe.db.exists("Supplier", supplier):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier, "supplier_group": "All Supplier Groups",
                            "supplier_type": "Company"}).insert(ignore_permissions=True)
        if not frappe.db.exists("Optical Laboratory", lab_name):
            frappe.get_doc({"doctype": "Optical Laboratory", "lab_name": lab_name, "lab_type": lab_type,
                            "supplier": supplier, "default_turnaround_days": days}).insert(ignore_permissions=True)
        labs.append(lab_name)
    if not frappe.db.get_single_value("Optical Settings", "default_laboratory"):
        frappe.db.set_single_value("Optical Settings", "default_laboratory", labs[0])

    # Customers
    territory = "Saudi Arabia" if frappe.db.exists("Territory", "Saudi Arabia") else (
        frappe.db.get_single_value("Selling Settings", "territory") or "All Territories")
    group = "Individual" if frappe.db.exists("Customer Group", "Individual") else (
        frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups")
    people = _names(rng, 24)
    customers = []
    for name, female in people:
        customers.append((_customer(name, _mobile(rng), territory, group), female))
    counts["customers"] = len(customers)

    # Prescriptions: first 16 customers; every 5th has an older prescription too (history / compare)
    rx_of, presbyope = {}, {}
    for i, (cust, female) in enumerate(customers[:16]):
        if frappe.db.exists("Optical Prescription", {"customer": cust}):
            rx_of[i] = frappe.db.get_value("Optical Prescription", {"customer": cust, "status": "Current"}, "name") \
                or frappe.db.get_value("Optical Prescription", {"customer": cust}, "name")
            presbyope[i] = i % 3 == 0
            continue
        presbyope[i] = i % 3 == 0
        values = _rx_values(rng, presbyope[i])
        if i % 5 == 0:
            older = dict(values)
            for side in ("od", "os"):
                older[f"{side}_sph"] = round(values[f"{side}_sph"] + 0.5, 2)
            _make_rx(cust, add_days(nowdate(), -rng.randint(400, 600)), older)
        rx_of[i] = _make_rx(cust, add_days(nowdate(), -rng.randint(1, 60)), values)
    counts["prescriptions"] = frappe.db.count("Optical Prescription")

    # Orders
    plan_a, plan_b, plan_c = plans[0], plans[2], plans[4]
    scenarios = [  # customer idx, days ago, stage, plan, approved, discount %
        (0, 1, "draft", None, False, 0), (1, 2, "draft", plans[1], False, 0), (2, 0, "draft", None, False, 10),
        (3, 5, "confirm", None, False, 0), (4, 4, "confirm", plan_a, True, 0), (5, 6, "confirm", None, False, 5),
        (6, 7, "lab", plan_b, True, 0), (7, 9, "lab_external", None, False, 0),
        (8, 10, "ready", plan_c, True, 0), (9, 3, "confirm", plan_a, False, 0),
    ]
    frames = [f[0] for f in FRAMES]
    single_lenses = [l[0] for l in LENSES if l[2] != "Progressive"]
    prog_lenses = [l[0] for l in LENSES if l[2] == "Progressive"]
    created = 0
    for idx, days, stage, plan, approved, disc in scenarios:
        cust = customers[idx][0]
        if frappe.db.exists("Optical Order", {"customer": cust, "notes": SEED_TAG}):
            continue
        prog = presbyope.get(idx, False)
        lens = rng.choice(prog_lenses if prog else single_lenses)
        lab = labs[1] if stage == "lab_external" else labs[0]
        order = _order(ctx, cust, rx_of[idx], days, rng.choice(frames), lens,
                       rng.choice(COATINGS)[0] if rng.random() < 0.6 else None, lab, plan, approved, disc,
                       rng.choice([a[0] for a in ACCESSORIES]) if rng.random() < 0.5 else None, prog, rng)
        created += 1
        if stage == "draft":
            continue
        order.confirm_order()
        order.reload()
        if plan and approved and order.insurance_claim:
            claim = frappe.get_doc("Insurance Claim", order.insurance_claim)
            claim.status, claim.approval_no = "Approved", order.insurance_approval_no
            claim.save(ignore_permissions=True)
        if stage in ("lab", "lab_external"):
            _advance(order.optical_job, 4)  # -> Laboratory
        elif stage == "ready":
            _advance(order.optical_job, 6)  # -> Quality Control
            frappe.get_doc({"doctype": "Optical QC", "optical_job": order.optical_job, "result": "Pass",
                            "checks": [{"check_item": c, "passed": 1} for c in QC_CHECKS]}).insert(ignore_permissions=True)
    counts["orders created this run"] = created

    frappe.db.commit()
    print("Optical demo data ready:", counts)
    return counts
