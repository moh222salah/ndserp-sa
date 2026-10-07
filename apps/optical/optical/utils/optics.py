"""Optical value validation. `check_eye_values` is pure; `validate_doc` throws in Frappe."""

# field -> (min, max, step or None)
LIMITS = {
    "sph": (-30.0, 30.0, 0.25),
    "cyl": (-15.0, 15.0, 0.25),
    "axis": (1, 180, None),
    "add": (0.0, 6.0, 0.25),
    "pd": (20.0, 45.0, None),
    "prism": (0.0, 20.0, None),
}
SINGLE_LIMITS = {"binocular_pd": (40.0, 80.0), "near_pd": (20.0, 80.0)}
EYE_KEYS = ["sph", "cyl", "axis", "add", "pd", "prism", "base", "va_distance", "va_near"]
EYE_FIELDS = [f"{s}_{k}" for s in ("od", "os") for k in EYE_KEYS]


def _blank(v):
    return v is None or v == ""


def check_eye_values(values):
    """Return a list of (code, fieldname, value, low, high). Zero counts as 'not entered'
    for axis/add/pd/prism (Frappe stores empty numerics as 0)."""
    errors = []
    for side in ("od", "os"):
        for key, (lo, hi, step) in LIMITS.items():
            name = f"{side}_{key}"
            v = values.get(name)
            if _blank(v):
                continue
            v = float(v)
            if v == 0 and key not in ("sph", "cyl"):
                continue
            if not (lo <= v <= hi):
                errors.append(("range", name, v, lo, hi))
            elif step and abs(round(v / step) * step - v) > 1e-6:
                errors.append(("step", name, v, step, None))
        cyl = values.get(f"{side}_cyl")
        axis = values.get(f"{side}_axis")
        if not _blank(cyl) and float(cyl) != 0 and (_blank(axis) or float(axis) == 0):
            errors.append(("axis_required", f"{side}_axis", axis, None, None))
    for name, (lo, hi) in SINGLE_LIMITS.items():
        v = values.get(name)
        if not _blank(v) and float(v) != 0 and not (lo <= float(v) <= hi):
            errors.append(("range", name, float(v), lo, hi))
    return errors


def validate_doc(doc):
    import frappe
    from frappe import _

    meta = frappe.get_meta(doc.doctype)
    values = {f: doc.get(f) for f in EYE_FIELDS + list(SINGLE_LIMITS)}
    for code, field, value, lo, hi in check_eye_values(values):
        label = _(meta.get_label(field))
        side = _("Right Eye (OD)") if field.startswith("od_") else _("Left Eye (OS)")
        if code == "range":
            frappe.throw(_("{0}: {1} must be between {2} and {3}").format(side, label, lo, hi))
        elif code == "step":
            frappe.throw(_("{0}: {1} must be in steps of {2}").format(side, label, lo))
        elif code == "axis_required":
            frappe.throw(_("{0}: Axis is required when cylinder is entered").format(side))
