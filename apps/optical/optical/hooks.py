app_name = "optical"
app_title = "Optical Retail"
app_publisher = "Ahmed"
app_description = "Optical Retail ERP for ERPNext"
app_email = "dev@example.com"
app_license = "mit"

required_apps = ["frappe/erpnext"]

after_install = "optical.setup.install.after_install"
after_migrate = "optical.setup.install.after_migrate"

doctype_js = {"Customer": "public/js/customer.js"}

jinja = {
    "methods": [
        "optical.utils.printing.is_rtl",
        "optical.utils.printing.eye_rows",
        "optical.utils.printing.lab_sheet_data",
        "optical.utils.printing.invoice_optical_data",
    ]
}

doc_events = {
    "Sales Invoice": {
        "on_submit": "optical.events.sales_invoice.on_submit",
        "on_cancel": "optical.events.sales_invoice.on_cancel",
    },
    "Payment Entry": {
        "on_submit": "optical.events.payment.sync_orders",
        "on_cancel": "optical.events.payment.sync_orders",
    },
}

scheduler_events = {"daily": ["optical.tasks.expire_warranties"]}
