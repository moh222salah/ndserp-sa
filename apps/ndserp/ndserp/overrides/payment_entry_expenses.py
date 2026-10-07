from contextlib import contextmanager

import frappe
from frappe import _


class PaymentEntryExpensesMixin:
    EXPENSE_PAYMENT_TYPE = "Expenses"
    CORE_PAYMENT_TYPE = "Internal Transfer"
    SOURCE_ACCOUNT_TYPES = ("Bank", "Cash")

    def _is_expense_payment(self):
        return self.get("payment_type") == self.EXPENSE_PAYMENT_TYPE

    def validate_payment_type(self):
        if self._is_expense_payment():
            return

        return super().validate_payment_type()

    def _prepare_expense_payment(self):
        if not self.get("company"):
            frappe.throw(
                _("Company is required for an Expenses Payment Entry.")
            )

        paid_from = self.get("paid_from")
        paid_to = self.get("paid_to")

        if not paid_from:
            frappe.throw(
                _("Account Paid From is required when Payment Type is Expenses.")
            )

        if not paid_to:
            frappe.throw(
                _("Account Paid To is required when Payment Type is Expenses.")
            )

        source = frappe.db.get_value(
            "Account",
            paid_from,
            [
                "name",
                "company",
                "root_type",
                "is_group",
                "account_type",
                "account_currency",
            ],
            as_dict=True,
        )

        if not source:
            frappe.throw(
                _("Account Paid From {0} does not exist.").format(paid_from)
            )

        if source.company != self.company:
            frappe.throw(
                _("Account Paid From must belong to the same Company.")
            )

        if source.is_group:
            frappe.throw(
                _("Account Paid From must be a leaf account.")
            )

        if source.account_type not in self.SOURCE_ACCOUNT_TYPES:
            frappe.throw(
                _(
                    "Account Paid From must be a Bank or Cash account "
                    "when Payment Type is Expenses."
                )
            )

        expense = frappe.db.get_value(
            "Account",
            paid_to,
            [
                "name",
                "company",
                "root_type",
                "is_group",
                "account_currency",
            ],
            as_dict=True,
        )

        if not expense:
            frappe.throw(
                _("Account Paid To {0} does not exist.").format(paid_to)
            )

        if expense.company != self.company:
            frappe.throw(
                _("Account Paid To must belong to the same Company.")
            )

        if expense.is_group:
            frappe.throw(
                _("Account Paid To must be a leaf account.")
            )

        if expense.root_type != "Expense":
            frappe.throw(
                _("Account Paid To must have Root Type = Expense.")
            )

        if paid_from == paid_to:
            frappe.throw(
                _("Account Paid From and Account Paid To must be different.")
            )

        if self.get("party_type") or self.get("party"):
            frappe.throw(
                _(
                    "Party Type and Party must be empty "
                    "when Payment Type is Expenses."
                )
            )

        if self.get("references"):
            frappe.throw(
                _(
                    "Payment references are not supported "
                    "when Payment Type is Expenses."
                )
            )

        if self.get("deductions"):
            frappe.throw(
                _(
                    "Payment deductions are not supported "
                    "when Payment Type is Expenses."
                )
            )

        if not self.get("paid_amount") or self.get("paid_amount") <= 0:
            frappe.throw(
                _("A positive payment amount is required when Payment Type is Expenses.")
            )

        # Expenses uses one visible amount while ERPNext Internal Transfer
        # semantics require both paid_amount and received_amount for the GL map.
        self.received_amount = frappe.utils.flt(self.get("paid_amount"))

        self.paid_to_account_currency = expense.account_currency

        # Legacy fields are retained only as hidden mirrors for compatibility.
        # They are never used as the accounting source of truth.
        if self.meta.has_field("custom_expense_account"):
            self.custom_expense_account = expense.name

        if self.meta.has_field("custom_expense_party_type"):
            self.custom_expense_party_type = "المصروفات"

        return source, expense

    @contextmanager
    def _expense_core_context(self):
        if not self._is_expense_payment():
            yield
            return

        self._prepare_expense_payment()

        snapshot = {
            "payment_type": self.get("payment_type"),
            "title": self.get("title"),
            "remarks": self.get("remarks"),
        }

        # Reuse ERPNext's native Internal Transfer accounting path.
        self.payment_type = self.CORE_PAYMENT_TYPE

        self.party_type = None
        self.party = None
        self.references = []
        self.deductions = []
        self.total_allocated_amount = 0

        if self.meta.has_field("party_name"):
            self.party_name = None

        try:
            yield
        finally:
            self.payment_type = snapshot["payment_type"]
            self.title = snapshot["title"]
            self.remarks = snapshot["remarks"]

            # Never restore party/reference state after native
            # Internal Transfer semantics have cleared it.
            self.party_type = None
            self.party = None
            self.references = []
            self.deductions = []
            self.total_allocated_amount = 0

            if self.meta.has_field("party_name"):
                self.party_name = None

            if self.meta.has_field("custom_expense_party_type"):
                self.custom_expense_party_type = "المصروفات"

            if (
                self.meta.has_field("custom_expense_account")
                and self.get("paid_to")
            ):
                self.custom_expense_account = self.paid_to

    def validate(self):
        with self._expense_core_context():
            return super().validate()

    def build_gl_map(self):
        with self._expense_core_context():
            return super().build_gl_map()

    def make_gl_entries(self, *args, **kwargs):
        with self._expense_core_context():
            return super().make_gl_entries(*args, **kwargs)

    def on_submit(self):
        with self._expense_core_context():
            return super().on_submit()

    def on_cancel(self):
        with self._expense_core_context():
            return super().on_cancel()
