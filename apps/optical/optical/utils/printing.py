"""Helpers exposed to Jinja print formats (see hooks.jinja). Business logic lives here,
not inside the templates."""
import frappe
from frappe import _
from frappe.utils import flt

RTL_LANGS = {"ar", "he", "fa", "ur"}


def is_rtl():
    return (frappe.local.lang or "en").split("-")[0] in RTL_LANGS


def _fmt(key, value):
    if value in (None, ""):
        return ""
    if key != "sph" and not value:
        return ""
    if key in ("sph", "cyl", "add", "prism"):
        return f"{flt(value):+.2f}" if key in ("sph", "cyl", "add") else f"{flt(value):.2f}"
    if key == "axis":
        return str(int(value)) if value else ""
    if key == "pd":
        return f"{flt(value):.1f}"
    return str(value)


def _rx_for(doc):
    """Return (rx_like_dict, order_or_none) for a prescription, exam, order or job."""
    order = None
    if doc.doctype == "Optical Job":
        order = frappe.get_doc("Optical Order", doc.optical_order)
    elif doc.doctype == "Optical Order":
        order = doc
    if order is None:
        return doc.as_dict(), None
    src = {}
    if order.prescription:
        src = frappe.get_doc("Optical Prescription", order.prescription).as_dict()
    for k in ("pd", "prism", "base"):
        for s in ("od", "os"):
            v = order.get(f"{s}_{k}")
            if v not in (None, "", 0, 0.0):
                src[f"{s}_{k}"] = v
    return src, order


def eye_rows(doc):
    src, _order = _rx_for(doc)
    defs = [
        ("sph", _("SPH")), ("cyl", _("CYL")), ("axis", _("AXIS")), ("add", _("ADD")),
        ("pd", _("PD")), ("prism", _("Prism")), ("base", _("Base")),
        ("va_distance", _("Distance Vision")), ("va_near", _("Near Vision")),
    ]
    return [
        {"label": label, "od": _fmt(k, src.get(f"od_{k}")), "os": _fmt(k, src.get(f"os_{k}"))}
        for k, label in defs
    ]


def _advanced(order):
    pairs, singles = [], []
    for key, label in (("fitting_height", _("Fitting Height")), ("seg_height", _("Seg Height"))):
        od, os_ = order.get(f"od_{key}"), order.get(f"os_{key}")
        if od or os_:
            pairs.append({"label": label, "od": flt(od) or "", "os": flt(os_) or ""})
    for key, label in (
        ("binocular_pd", _("Binocular PD")), ("near_pd", _("Near PD")),
        ("pantoscopic_tilt", _("Pantoscopic Tilt")), ("wrap_angle", _("Wrap Angle")),
        ("vertex_distance", _("Vertex Distance")),
    ):
        if order.get(key):
            singles.append({"label": label, "value": flt(order.get(key))})
    return {"pairs": pairs, "singles": singles}


def _items_by_role(order):
    out = {}
    for row in order.items:
        out.setdefault(row.item_role, []).append(row)
    return out


def lab_sheet_data(job):
    order = frappe.get_doc("Optical Order", job.optical_order)
    qc = frappe.get_all(
        "Optical QC",
        filters={"optical_job": job.name},
        fields=["name", "result", "inspector", "qc_date", "rejection_reason"],
        order_by="creation desc",
        limit=1,
    )
    return {
        "order": order,
        "rows": eye_rows(job),
        "roles": _items_by_role(order),
        "advanced": _advanced(order),
        "qc": qc[0] if qc else None,
    }


def invoice_optical_data(invoice):
    order_name = invoice.get("optical_order")
    if not order_name:
        return None
    order = frappe.get_doc("Optical Order", order_name)
    return {"order": order, "rows": eye_rows(order), "advanced": _advanced(order)}
