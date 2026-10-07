import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate

from optical.utils.optics import validate_doc
from optical.utils.printing import eye_rows
from optical.utils.profile import ensure_profile


class OpticalPrescription(Document):
    def validate(self):
        ensure_profile(self.customer)
        validate_doc(self)
        if not self.expiry_date and self.prescription_date:
            days = frappe.db.get_single_value("Optical Settings", "default_prescription_validity_days")
            if days:
                self.expiry_date = add_days(self.prescription_date, int(days))
        if self.expiry_date and getdate(self.expiry_date) < getdate(self.prescription_date):
            frappe.throw(_("Expiry Date cannot be before Prescription Date"))
        if self.is_new() and not self.previous_prescription:
            self.previous_prescription = self._latest_previous()

    def _latest_previous(self):
        rows = frappe.get_all(
            "Optical Prescription",
            filters={"customer": self.customer, "name": ["!=", self.name or ""]},
            order_by="prescription_date desc, creation desc",
            limit=1,
            pluck="name",
        )
        return rows[0] if rows else None

    def on_update(self):
        if self.status == "Current":
            for other in frappe.get_all(
                "Optical Prescription",
                filters={"customer": self.customer, "status": "Current", "name": ["!=", self.name]},
                pluck="name",
            ):
                frappe.db.set_value("Optical Prescription", other, "status", "Superseded")
            frappe.db.set_value("Optical Profile", self.customer, "last_prescription", self.name)
        if self.eye_examination:
            frappe.db.set_value("Eye Examination", self.eye_examination, "prescription", self.name)


@frappe.whitelist()
def compare_with_previous(name, other=None):
    current = frappe.get_doc("Optical Prescription", name)
    frappe.has_permission("Optical Prescription", "read", doc=current, throw=True)
    other = other or current.previous_prescription
    if not other:
        return None
    previous = frappe.get_doc("Optical Prescription", other)
    frappe.has_permission("Optical Prescription", "read", doc=previous, throw=True)
    rows = []
    for cur, prev in zip(eye_rows(current), eye_rows(previous)):
        rows.append({
            "label": cur["label"],
            "cur_od": cur["od"], "cur_os": cur["os"],
            "prev_od": prev["od"], "prev_os": prev["os"],
        })
    return {"current": current.name, "previous": previous.name,
            "current_date": str(current.prescription_date), "previous_date": str(previous.prescription_date),
            "rows": rows}
