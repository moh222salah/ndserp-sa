import frappe
from frappe import _
from frappe.model.document import Document
from contracting.contracting_tender.doctype.tender.tender import update_tender_totals


class TenderBOQItem(Document):
    def validate(self):
        if self.parent_tender_boq_item == self.name:
            frappe.throw(_("A BOQ Item cannot be its own parent."))
        if (self.quantity or 0) <= 0:
            frappe.throw(_("Quantity must be greater than zero."))
        self._compute()

    def _compute(self):
        direct = 0.0
        for t in (self.materials, self.labour, self.equipment, self.subcontracts):
            for r in t:
                r.amount = (r.quantity or 0) * (r.rate or 0); direct += r.amount or 0
        for r in self.expenses:
            direct += r.amount or 0
        self.direct_cost = direct
        if self.pricing_mode == "Detailed Breakdown":
            self.cost_amount = direct
            self.cost_rate = (direct / self.quantity) if self.quantity else 0
        else:
            self.cost_amount = (self.quantity or 0) * (self.cost_rate or 0)
        markup = frappe.db.get_value("Tender", self.tender, "markup_percent") or 0
        self.calculated_selling_rate = (self.cost_rate or 0) * (1 + markup/100.0)
        if self.pricing_mode != "Direct Selling Rate" and not self.selling_rate:
            self.selling_rate = self.calculated_selling_rate
        self.selling_amount = (self.quantity or 0) * (self.selling_rate or 0)
        self.planned_profit = (self.selling_amount or 0) - (self.cost_amount or 0)
        self.planned_margin = ((self.planned_profit/self.selling_amount)*100) if self.selling_amount else 0

    def on_update(self):
        update_tender_totals(self.tender)

    def on_trash(self):
        update_tender_totals(self.tender)
