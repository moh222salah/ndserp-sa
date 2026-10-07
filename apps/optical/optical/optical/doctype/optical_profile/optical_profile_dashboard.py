from frappe import _


def get_data():
    return {
        "fieldname": "customer",
        "transactions": [
            {"label": _("Optical"), "items": ["Eye Examination", "Optical Prescription", "Optical Order"]},
            {"label": _("After Sales"), "items": ["Optical Warranty", "Optical Warranty Claim", "Optical Remake"]},
        ],
    }
