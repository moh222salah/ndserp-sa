import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

from optical.utils.optics import validate_doc
from optical.utils.profile import ensure_profile


class EyeExamination(Document):
    def validate(self):
        ensure_profile(self.customer)
        validate_doc(self)

    def on_update(self):
        current = frappe.db.get_value("Optical Profile", self.customer, "last_examination")
        if not current or str(current) <= str(self.exam_date):
            frappe.db.set_value("Optical Profile", self.customer, "last_examination", self.exam_date)


@frappe.whitelist()
def make_prescription(source_name, target_doc=None):
    return get_mapped_doc(
        "Eye Examination",
        source_name,
        {"Eye Examination": {
            "doctype": "Optical Prescription",
            "field_map": {"name": "eye_examination", "exam_date": "prescription_date"},
        }},
        target_doc,
    )
