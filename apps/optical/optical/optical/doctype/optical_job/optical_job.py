import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

from optical.utils.workflow import STAGES, next_stage

IN_PRODUCTION = STAGES[1:7]  # Prescription Verification .. Quality Control


def _flags():
    return frappe.get_cached_doc("Optical Settings").as_dict()


class OpticalJob(Document):
    def validate(self):
        if self.is_new():
            self._log(self.status)
        if self.date_sent and self.actual_return and getdate(self.actual_return) < getdate(self.date_sent):
            frappe.throw(_("Actual Return cannot be before Date Sent"))

    def _log(self, stage):
        self.append("stage_log", {"stage": stage, "changed_on": now_datetime(), "changed_by": frappe.session.user})

    def _is_external(self):
        return bool(self.laboratory) and frappe.db.get_value("Optical Laboratory", self.laboratory, "lab_type") == "External"

    @frappe.whitelist()
    def advance_stage(self, to_stage=None):
        self.check_permission("write")
        if self.status in ("Delivered", "Cancelled"):
            frappe.throw(_("A {0} job cannot be advanced").format(_(self.status)))
        target = to_stage or next_stage(self.status, _flags())
        if not target or target not in STAGES:
            frappe.throw(_("There is no next stage"))
        order = frappe.get_doc("Optical Order", self.optical_order)
        self._before_stage(target, order)
        self.status = target
        self._log(target)
        self.save()
        self._after_stage(target, order)
        return target

    def _before_stage(self, target, order):
        if self.status == "Laboratory" and target != "Laboratory" and not self.actual_return:
            self.actual_return = nowdate()
        if target == "Laboratory":
            if self._is_external() and not self.laboratory:
                frappe.throw(_("Select the laboratory first"))
            if not self.date_sent:
                self.date_sent = nowdate()
            if not self.expected_return and self.laboratory:
                days = cint(frappe.db.get_value("Optical Laboratory", self.laboratory, "default_turnaround_days"))
                if days:
                    self.expected_return = add_days(self.date_sent, days)
        if target == "Ready" and _flags().get("enable_quality_control") and not frappe.db.exists(
            "Optical QC", {"optical_job": self.name, "result": "Pass"}
        ):
            frappe.throw(_("A passed quality control is required before the job can be Ready"))
        if target == "Delivered":
            order.validate_delivery()

    def _after_stage(self, target, order):
        if target in IN_PRODUCTION:
            order.db_set("status", "In Production")
        elif target in ("Ready", "Notified"):
            order.db_set("status", "Ready")
        elif target == "Delivered":
            order.db_set("status", "Delivered")
            order.create_warranties()

    @frappe.whitelist()
    def make_purchase_order(self):
        self.check_permission("write")
        if self.purchase_order:
            frappe.throw(_("Purchase Order {0} already exists").format(self.purchase_order))
        if not self._is_external():
            frappe.throw(_("Purchase orders are only for external laboratories"))
        supplier = frappe.db.get_value("Optical Laboratory", self.laboratory, "supplier")
        item = frappe.db.get_single_value("Optical Settings", "lab_service_item")
        if not supplier or not item:
            frappe.throw(_("Set the laboratory supplier and the Laboratory Service Item in Optical Settings"))
        company = frappe.db.get_value("Optical Order", self.optical_order, "company")
        schedule = self.expected_return or add_days(nowdate(), 3)
        po = frappe.get_doc({
            "doctype": "Purchase Order", "supplier": supplier, "company": company, "schedule_date": schedule,
            "items": [{
                "item_code": item, "qty": 1, "rate": self.lab_cost or 0, "schedule_date": schedule,
                "description": _("Laboratory work for optical job {0}").format(self.name),
            }],
        })
        po.insert()
        self.db_set("purchase_order", po.name)
        return po.name
