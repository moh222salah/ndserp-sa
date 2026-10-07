import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, nowdate

from optical.utils.insurance import split_amounts
from optical.utils.profile import ensure_profile

LENS_ROLES = ("Right Lens", "Left Lens")


class OpticalOrder(Document):
    # ------------------------------------------------------------ validation
    def validate(self):
        self.set_defaults()
        ensure_profile(self.customer)
        self.validate_prescription()
        self.validate_items()
        self.validate_locked_fields()
        self.copy_rx_measurements()
        self.calculate_totals()
        self.calculate_insurance()
        self.set_payment_snapshot()

    def on_trash(self):
        if self.status != "Draft":
            frappe.throw(_("Only Draft orders can be deleted. Cancel the order instead."))

    def set_defaults(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
                "Global Defaults", "default_company"
            )
        if self.company and not self.cost_center:
            self.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
        if not self.warehouse:
            self.warehouse = frappe.defaults.get_user_default("Warehouse") or frappe.db.get_single_value(
                "Stock Settings", "default_warehouse"
            )
        settings = frappe.get_cached_doc("Optical Settings")
        if not self.expected_delivery:
            self.expected_delivery = add_days(self.order_date or nowdate(), cint(settings.default_delivery_days) or 3)
        if not self.laboratory and settings.default_laboratory:
            self.laboratory = settings.default_laboratory

    def validate_prescription(self):
        if self.prescription:
            rx_customer = frappe.db.get_value("Optical Prescription", self.prescription, "customer")
            if rx_customer != self.customer:
                frappe.throw(_("Prescription {0} does not belong to customer {1}").format(self.prescription, self.customer))

    def validate_items(self):
        for row in self.items:
            if flt(row.qty) <= 0:
                frappe.throw(_("Row {0}: Quantity must be greater than zero").format(row.idx))
            if flt(row.rate) < 0:
                frappe.throw(_("Row {0}: Rate cannot be negative").format(row.idx))

    def _items_signature(self):
        return [(r.item_code, flt(r.qty), flt(r.rate), r.item_role) for r in self.items]

    def validate_locked_fields(self):
        before = self.get_doc_before_save()
        if not before or before.status == "Draft":
            return
        locked = ("customer", "discount_percent", "discount_amount", "insurance_plan", "prescription")
        changed = [f for f in locked if before.get(f) != self.get(f)]
        before_sig = [(r.item_code, flt(r.qty), flt(r.rate), r.item_role) for r in before.items]
        if changed or before_sig != self._items_signature():
            frappe.throw(_("Items, pricing, customer and insurance cannot be changed after the order is confirmed."))

    def copy_rx_measurements(self):
        if not self.prescription:
            return
        rx = frappe.db.get_value(
            "Optical Prescription", self.prescription,
            ["od_pd", "os_pd", "od_prism", "os_prism", "od_base", "os_base", "binocular_pd", "near_pd"],
            as_dict=True,
        )
        for key, value in (rx or {}).items():
            if value and not self.get(key):
                self.set(key, value)

    # ------------------------------------------------------------ totals
    def calculate_totals(self):
        gross = 0.0
        for row in self.items:
            row.amount = flt(row.qty) * flt(row.rate)
            gross += row.amount
        self.gross_total = gross
        if flt(self.discount_percent):
            self.discount_amount = gross * flt(self.discount_percent) / 100.0
        if flt(self.discount_amount) > gross:
            frappe.throw(_("Discount cannot exceed the gross total"))
        self.net_total = gross - flt(self.discount_amount)

    def calculate_insurance(self):
        if not self.insurance_plan:
            self.insurance_amount = 0
            self.customer_amount = self.net_total
            self.insurance_approved = 0
            return
        plan = frappe.db.get_value(
            "Insurance Plan", self.insurance_plan,
            ["coverage_percent", "max_coverage", "deductible", "is_active", "insurance_company"], as_dict=True,
        )
        if not plan.is_active:
            frappe.throw(_("Insurance Plan {0} is not active").format(self.insurance_plan))
        self.insurance_company = plan.insurance_company
        self.insurance_amount, self.customer_amount = split_amounts(
            self.net_total, plan.coverage_percent, plan.max_coverage, plan.deductible
        )
        if self.insurance_approved and not self.insurance_approval_no:
            frappe.throw(_("Approval Number is required when insurance is approved"))

    # ------------------------------------------------------------ payments
    def _payment_snapshot(self):
        inv = self.sales_invoice and frappe.db.get_value(
            "Sales Invoice", self.sales_invoice, ["docstatus", "grand_total", "outstanding_amount"], as_dict=True
        )
        if inv and inv.docstatus == 1:
            return flt(inv.grand_total) - flt(inv.outstanding_amount), flt(inv.outstanding_amount)
        return 0.0, flt(self.customer_amount)

    def set_payment_snapshot(self):
        self.paid_amount, self.outstanding_amount = self._payment_snapshot()
        self.payment_status = self._payment_status()

    def _payment_status(self):
        if flt(self.paid_amount) <= 0:
            return "Unpaid"
        return "Paid" if flt(self.outstanding_amount) < 0.005 else "Partly Paid"

    def sync_payments(self):
        """Called from Sales Invoice / Payment Entry events."""
        paid, outstanding = self._payment_snapshot()
        self.paid_amount, self.outstanding_amount = paid, outstanding
        self.db_set({"paid_amount": paid, "outstanding_amount": outstanding, "payment_status": self._payment_status()})
        if self.insurer_invoice and self.insurance_claim:
            inv = frappe.db.get_value(
                "Sales Invoice", self.insurer_invoice, ["docstatus", "grand_total", "outstanding_amount"], as_dict=True
            )
            if inv and inv.docstatus == 1:
                update = {"status": "Submitted"}
                if flt(inv.outstanding_amount) < 0.005:
                    update = {"status": "Settled", "settled_amount": inv.grand_total, "settlement_date": nowdate()}
                frappe.db.set_value("Insurance Claim", self.insurance_claim, update)

    # ------------------------------------------------------------ actions
    @frappe.whitelist()
    def confirm_order(self):
        self.check_permission("write")
        if self.status != "Draft":
            frappe.throw(_("Only Draft orders can be confirmed"))
        if not self.items:
            frappe.throw(_("Add at least one item"))
        if any(r.item_role in LENS_ROLES for r in self.items) and not self.prescription:
            frappe.throw(_("A prescription is required for orders that include lenses"))
        self.status = "Confirmed"
        self.save()
        self._create_job()
        self._create_claim()
        return self.name

    def _create_job(self):
        if self.optical_job:
            return
        job = frappe.get_doc({
            "doctype": "Optical Job", "optical_order": self.name, "laboratory": self.laboratory, "priority": "Normal",
        })
        job.insert(ignore_permissions=True)
        self.db_set("optical_job", job.name)

    def _create_claim(self):
        if flt(self.insurance_amount) <= 0 or self.insurance_claim:
            return
        claim = frappe.get_doc({
            "doctype": "Insurance Claim", "optical_order": self.name, "claim_amount": self.insurance_amount,
            "approval_no": self.insurance_approval_no,
            "status": "Approved" if self.insurance_approved else "Pending",
        })
        claim.insert(ignore_permissions=True)
        self.db_set("insurance_claim", claim.name)

    @frappe.whitelist()
    def cancel_order(self):
        self.check_permission("write")
        if self.status in ("Delivered", "Cancelled"):
            frappe.throw(_("A {0} order cannot be cancelled").format(_(self.status)))
        for field in ("sales_invoice", "insurer_invoice"):
            inv = self.get(field)
            if inv and frappe.db.get_value("Sales Invoice", inv, "docstatus") == 1:
                frappe.throw(_("Cancel Sales Invoice {0} first").format(inv))
        self.db_set("status", "Cancelled")
        if self.optical_job:
            frappe.db.set_value("Optical Job", self.optical_job, "status", "Cancelled")
        if self.insurance_claim:
            frappe.db.set_value("Insurance Claim", self.insurance_claim, "status", "Rejected")

    def _require_confirmed(self):
        if self.status in ("Draft", "Cancelled"):
            frappe.throw(_("Confirm the order first"))

    @frappe.whitelist()
    def make_sales_invoice(self):
        self._require_confirmed()
        if self.sales_invoice and frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus") != 2:
            frappe.throw(_("Customer invoice {0} already exists").format(self.sales_invoice))
        if self.insurance_plan and frappe.db.get_value("Insurance Plan", self.insurance_plan, "requires_approval")                 and not self.insurance_approved:
            frappe.throw(_("Insurance approval is required before invoicing"))
        si = frappe.new_doc("Sales Invoice")
        si.customer = self.customer
        si.company = self.company
        si.cost_center = self.cost_center
        si.update_stock = 1
        si.set_warehouse = self.warehouse
        si.optical_order = self.name
        for row in self.items:
            line = {
                "item_code": row.item_code, "qty": row.qty, "rate": row.rate,
                "warehouse": self.warehouse, "cost_center": self.cost_center,
                "description": row.spec_details or None,
            }
            if row.batch_no:
                line.update({"batch_no": row.batch_no, "use_serial_batch_fields": 1})
            si.append("items", line)
        reduction = flt(self.gross_total) - flt(self.customer_amount)
        if reduction > 0:
            si.apply_discount_on = "Net Total"
            si.discount_amount = reduction
        si.run_method("set_missing_values")
        si.run_method("calculate_taxes_and_totals")
        si.insert()
        self.db_set("sales_invoice", si.name)
        return si.name

    @frappe.whitelist()
    def make_insurer_invoice(self):
        self._require_confirmed()
        if flt(self.insurance_amount) <= 0:
            frappe.throw(_("This order has no insurance portion"))
        if self.insurance_plan and frappe.db.get_value("Insurance Plan", self.insurance_plan, "requires_approval")                 and not self.insurance_approved:
            frappe.throw(_("Insurance approval is required before invoicing the insurer"))
        if self.insurer_invoice and frappe.db.get_value("Sales Invoice", self.insurer_invoice, "docstatus") != 2:
            frappe.throw(_("Insurer invoice {0} already exists").format(self.insurer_invoice))
        item = frappe.db.get_single_value("Optical Settings", "insurance_service_item")
        insurer_customer = frappe.db.get_value("Insurance Company", self.insurance_company, "customer")
        if not item or not insurer_customer:
            frappe.throw(_("Set the Insurance Service Item in Optical Settings and make sure the insurance company has a customer"))
        si = frappe.new_doc("Sales Invoice")
        si.customer = insurer_customer
        si.company = self.company
        si.cost_center = self.cost_center
        si.optical_order = self.name
        si.append("items", {
            "item_code": item, "qty": 1, "rate": self.insurance_amount, "cost_center": self.cost_center,
            "description": _("Insurance coverage for optical order {0} ({1})").format(self.name, self.customer_name),
        })
        si.run_method("set_missing_values")
        si.run_method("calculate_taxes_and_totals")
        si.insert()
        self.db_set("insurer_invoice", si.name)
        if self.insurance_claim:
            frappe.db.set_value("Insurance Claim", self.insurance_claim, {"insurer_invoice": si.name, "status": "Submitted"})
        return si.name

    def validate_delivery(self):
        """Called by the Optical Job before it moves to Delivered."""
        self.sync_payments()
        inv = self.sales_invoice and frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus")
        if inv != 1:
            frappe.throw(_("Submit the customer invoice before delivery"))
        allow = frappe.db.get_single_value("Optical Settings", "allow_delivery_with_balance")
        if not allow and flt(self.outstanding_amount) >= 0.005:
            frappe.throw(_("Customer has an outstanding balance of {0}").format(frappe.format_value(self.outstanding_amount, {"fieldtype": "Currency"})))

    def create_warranties(self):
        days = cint(frappe.db.get_single_value("Optical Settings", "default_warranty_days"))
        if not days:
            return
        start = nowdate()
        for row in self.items:
            if row.item_role in ("Frame", "Right Lens", "Left Lens") and not frappe.db.exists(
                "Optical Warranty", {"optical_order": self.name, "item_code": row.item_code, "item_role": row.item_role}
            ):
                frappe.get_doc({
                    "doctype": "Optical Warranty", "optical_order": self.name, "customer": self.customer,
                    "item_code": row.item_code, "item_role": row.item_role, "warranty_type": "Manufacturing Defect",
                    "start_date": start, "end_date": add_days(start, days), "status": "Active",
                }).insert(ignore_permissions=True)
