import frappe
from frappe import _
from frappe.model.document import Document


class Tender(Document):
    def validate(self):
        if self.submission_date and self.tender_date and self.submission_date < self.tender_date:
            frappe.throw(_("Submission Date cannot be before Tender Date."))
        self.total_indirect_cost = sum((r.amount or 0) for r in self.indirect_costs)
        self._roll_boq()

    def _roll_boq(self):
        if self.is_new():
            return
        row = frappe.db.sql("""select coalesce(sum(cost_amount),0), coalesce(sum(selling_amount),0)
            from `tabTender BOQ Item` where tender=%s and ifnull(is_group,0)=0""", self.name)[0]
        self.total_direct_cost = row[0] or 0
        self.total_estimated_cost = (self.total_direct_cost or 0) + (self.total_indirect_cost or 0)
        self.tender_price = row[1] or 0
        self.planned_profit = (self.tender_price or 0) - (self.total_estimated_cost or 0)
        self.planned_margin = ((self.planned_profit/self.tender_price)*100) if self.tender_price else 0

    @frappe.whitelist()
    def create_budget_from_tender(self, project):
        """On award: create a Project Budget + Budget BOQ Items from this Tender."""
        if not project:
            frappe.throw(_("Select the awarded Project first."))
        budget = frappe.get_doc({"doctype":"Project Budget","project":project,
            "company":self.company,"currency":self.currency,"source_tender":self.name,
            "status":"Draft"}).insert(ignore_permissions=True)
        for b in frappe.get_all("Tender BOQ Item", filters={"tender":self.name},
                fields=["boq_no","description","quantity","unit","csi_code",
                        "pricing_mode","cost_rate","selling_rate"]):
            frappe.get_doc({"doctype":"Budget BOQ Item","budget":budget.name,
                "boq_no":b.boq_no,"description":b.description or b.boq_no,"quantity":b.quantity,
                "unit":b.unit,"csi_code":b.csi_code,"pricing_mode":b.pricing_mode or "Direct Cost",
                "cost_rate":b.cost_rate,"selling_rate":b.selling_rate}).insert(ignore_permissions=True)
        return budget.name


def update_tender_totals(tender):
    if not tender or not frappe.db.exists("Tender", tender):
        return
    row = frappe.db.sql("""select coalesce(sum(cost_amount),0), coalesce(sum(selling_amount),0)
        from `tabTender BOQ Item` where tender=%s and ifnull(is_group,0)=0""", tender)[0]
    direct, price = row[0] or 0, row[1] or 0
    indirect = frappe.db.get_value("Tender", tender, "total_indirect_cost") or 0
    est = direct + indirect; profit = price - est
    frappe.db.set_value("Tender", tender, {"total_direct_cost":direct,
        "total_estimated_cost":est,"tender_price":price,"planned_profit":profit,
        "planned_margin":(profit/price*100) if price else 0}, update_modified=False)
