# Copyright (c) 2026, NDS and contributors
# License: MIT

import os

import frappe
from frappe.website.page_renderers.template_page import TemplatePage


class POSNextPage(TemplatePage):
	"""Serve POS Next at /pos even if a stray nds_restaurant/www/pos.html exists.

	nds_restaurant is installed after pos_next, so any pos.html in its www folder
	would otherwise shadow POS Next. The restaurant POS lives at /restaurant-pos.
	"""

	def set_template_path(self):
		if self.path != "pos" or "pos_next" not in frappe.get_installed_apps():
			return

		app_path = frappe.get_app_path("pos_next")
		file_path = os.path.join(app_path, "www", "pos.html")
		if not os.path.isfile(file_path):
			return

		self.app = "pos_next"
		self.app_path = app_path
		self.file_dir = "www"
		self.basename = os.path.splitext(file_path)[0]
		self.template_path = os.path.relpath(file_path, app_path)
		self.basepath = os.path.dirname(file_path)
		self.filename = "pos.html"
		self.name = "pos"

	def set_page_properties(self):
		super().set_page_properties()
		# The Jinja loader resolves bare "www/pos.html" by app order; prefix the app.
		self.context.template = f"{self.app}/{self.template_path}"
