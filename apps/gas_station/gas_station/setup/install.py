import frappe

GAS_STATION_ROLES = [
    "Gas Station Administrator",
    "Gas Station Integration Manager",
    "Station Manager",
    "Station Operator",
    "Gas Station Viewer",
]

DEFAULT_ALERT_RULES = [
    {"rule_name": "Tank Critical Low", "equipment_type": "Tank",
     "parameter": "fill_percentage", "operator": "<", "threshold": 10,
     "severity": "Critical", "alert_type": "Tank Critical Low",
     "message_template": "{equipment} critically low at {value}% (< {threshold}%)"},
    {"rule_name": "Tank Low", "equipment_type": "Tank",
     "parameter": "fill_percentage", "operator": "<", "threshold": 20,
     "severity": "Warning", "alert_type": "Tank Low",
     "message_template": "{equipment} low at {value}% (< {threshold}%)"},
    {"rule_name": "High Water Level", "equipment_type": "Tank",
     "parameter": "water_level", "operator": ">", "threshold": 25,
     "severity": "Critical", "alert_type": "High Water Level",
     "message_template": "{equipment} water level {value}mm (> {threshold}mm)"},
    {"rule_name": "High Temperature", "equipment_type": "Tank",
     "parameter": "temperature", "operator": ">", "threshold": 40,
     "severity": "Warning", "alert_type": "High Temperature",
     "message_template": "{equipment} temperature {value}°C (> {threshold}°C)"},
]


def after_install():
    create_roles()
    ensure_settings()
    create_default_alert_rules()
    setup_workspace()
    frappe.db.commit()


def after_migrate():
    """Idempotent — runs on every `bench migrate`."""
    from gas_station.gas_station.integration.idempotency import ensure_unique_indexes
    try:
        ensure_unique_indexes()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "gas_station after_migrate indexes")
    ensure_settings()
    create_default_alert_rules()
    setup_workspace()
    frappe.db.commit()


def create_roles():
    for role_name in GAS_STATION_ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.insert(ignore_permissions=True)


def ensure_settings():
    if not frappe.db.exists("Gas Station Settings", "Gas Station Settings"):
        try:
            doc = frappe.get_single("Gas Station Settings")
            doc.demo_mode = 1
            doc.save(ignore_permissions=True)
        except Exception:
            pass


def create_default_alert_rules():
    for rule in DEFAULT_ALERT_RULES:
        if not frappe.db.exists("Alert Rule", rule["rule_name"]):
            try:
                frappe.get_doc({"doctype": "Alert Rule", "enabled": 1, **rule}) \
                    .insert(ignore_permissions=True)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "gas_station alert rule seed")


def setup_workspace():
    """Create the Gas Station workspace. Wrapped so a workspace-schema mismatch
    on any given Frappe build can never break install/migrate."""
    try:
        _build_workspace()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "gas_station workspace setup")


def _build_workspace():
    import json
    name = "Gas Station"
    if frappe.db.exists("Workspace", name):
        return

    cards = [
        ("Monitoring", [("Gas Station Dashboard", "Gas Station Dashboard", "gas_station_dashboard")]),
        ("Configuration", [
            ("Gas Station", "DocType", "Gas Station"),
            ("PTS Controller", "DocType", "PTS Controller"),
            ("Gas Station Pump", "DocType", "Gas Station Pump"),
            ("Gas Station Tank", "DocType", "Gas Station Tank"),
            ("Gas Station Probe", "DocType", "Gas Station Probe"),
            ("Alert Rule", "DocType", "Alert Rule"),
            ("Gas Station Settings", "DocType", "Gas Station Settings"),
        ]),
        ("Operations", [
            ("PTS Pump Transaction", "DocType", "PTS Pump Transaction"),
            ("Tank Measurement", "DocType", "Tank Measurement"),
            ("Tank Delivery", "DocType", "Tank Delivery"),
            ("Station Alert", "DocType", "Station Alert"),
            ("Pump State", "DocType", "Pump State"),
            ("Tank State", "DocType", "Tank State"),
        ]),
        ("Integration & Simulator", [
            ("Integration Event", "DocType", "Integration Event"),
            ("Controller Connection State", "DocType", "Controller Connection State"),
            ("Mock PTS Controller", "DocType", "Mock PTS Controller"),
        ]),
        ("Reconciliation", [
            ("Reconciliation Run", "DocType", "Reconciliation Run"),
        ]),
    ]
    reports = [
        "Pump Performance", "Fuel Dispensing", "Tank Level History",
        "PTS Transaction Report", "PTS vs ERPNext Reconciliation",
        "Station Alerts Report", "Integration Events Report",
        "Station Operational Summary",
    ]

    ws = frappe.new_doc("Workspace")
    ws.name = name
    ws.title = name
    ws.label = name
    ws.module = "Gas Station"
    ws.public = 1
    ws.icon = "gas-pump" if False else "tool"
    content = []

    # shortcuts
    ws.append("shortcuts", {"label": "Dashboard", "type": "Page",
                            "link_to": "gas_station_dashboard", "color": "Blue"})
    ws.append("shortcuts", {"label": "Transactions", "type": "DocType",
                            "link_to": "PTS Pump Transaction"})
    ws.append("shortcuts", {"label": "Alerts", "type": "DocType",
                            "link_to": "Station Alert", "color": "Red"})
    ws.append("shortcuts", {"label": "Simulator", "type": "DocType",
                            "link_to": "Mock PTS Controller", "color": "Green"})
    content.append({"type": "header", "data": {"text": "Gas Station", "col": 12}})
    content.append({"type": "shortcut", "data": {"shortcut_name": "Dashboard", "col": 3}})
    content.append({"type": "shortcut", "data": {"shortcut_name": "Transactions", "col": 3}})
    content.append({"type": "shortcut", "data": {"shortcut_name": "Alerts", "col": 3}})
    content.append({"type": "shortcut", "data": {"shortcut_name": "Simulator", "col": 3}})

    for card_label, items in cards:
        ws.append("links", {"label": card_label, "type": "Card Break",
                            "link_count": len(items)})
        for label, ltype, target in items:
            row = {"label": label, "type": "Link", "link_to": target,
                   "link_type": ltype, "onboard": 0, "is_query_report": 0}
            ws.append("links", row)
        content.append({"type": "card", "data": {"card_name": card_label, "col": 4}})

    ws.append("links", {"label": "Reports", "type": "Card Break",
                        "link_count": len(reports)})
    for rep in reports:
        ws.append("links", {"label": rep, "type": "Link", "link_to": rep,
                            "link_type": "Report", "is_query_report": 1})
    content.append({"type": "card", "data": {"card_name": "Reports", "col": 4}})

    ws.content = json.dumps(content)
    ws.insert(ignore_permissions=True)
