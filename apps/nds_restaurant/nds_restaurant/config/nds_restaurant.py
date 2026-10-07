from frappe import _


def get_data():
	return [
		{
			"label": _("Setup"),
			"items": [
				{"type": "doctype", "name": "NDS Restaurant", "label": _("Restaurant")},
				{"type": "doctype", "name": "NDS Room", "label": _("Room")},
				{"type": "doctype", "name": "NDS Table", "label": _("Table")},
				{"type": "doctype", "name": "NDS Menu Course", "label": _("Menu Course")},
				{"type": "doctype", "name": "NDS Menu", "label": _("Menu")},
				{"type": "doctype", "name": "NDS Production Unit", "label": _("Production Unit")},
				{"type": "doctype", "name": "NDS Recipe", "label": _("Recipe")},
				{"type": "doctype", "name": "NDS Report Settings", "label": _("Report Settings")},
			],
		},
		{
			"label": _("Operations"),
			"items": [
				{"type": "doctype", "name": "NDS KOT", "label": _("KOT")},
				{"type": "doctype", "name": "Sub POS Closing", "label": _("Sub POS Closing")},
				{"type": "report", "name": "NDS Daily P and L", "label": _("Daily P&L"), "is_query_report": True},
			],
		},
	]
