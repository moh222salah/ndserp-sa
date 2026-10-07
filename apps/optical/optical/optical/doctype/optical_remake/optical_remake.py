import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OpticalRemake(Document):
    def validate(self):
        status = frappe.db.get_value("Optical Order", self.original_order, "status")
        if status in ("Draft", "Cancelled"):
            frappe.throw(_("A remake requires a confirmed optical order"))
        for row in self.replacement_items:
            row.amount = flt(row.qty) * flt(row.rate)

    def on_update(self):
        if self.status == "Approved" and not self.new_job:
            self._create_job()

    def _create_job(self):
        job = frappe.get_doc({
            "doctype": "Optical Job", "optical_order": self.original_order, "laboratory": self.laboratory,
            "is_remake": 1, "optical_remake": self.name, "priority": "Urgent",
        })
        job.insert(ignore_permissions=True)
        self.db_set({"new_job": job.name, "status": "In Progress"})
