import frappe
from frappe import _
import re


def set_pos_invoice_naming(doc, method=None):
	"""
	Set naming series for POS Invoice based on:
	- Aggregator Series Prefix (if custom_nds_order_type == 'Aggregator' and aggregator_series_prefix is set)
	- Invoice Series Prefix (otherwise)
	Only applies when POS Profile has custom_use_invoice_series_prefix enabled.
	"""
	if doc.doctype != "POS Invoice":
		return
	
	# Skip amended documents
	if doc.amended_from:
		return
	
	# Guard: return early if custom fields don't exist (unmigrated site)
	if not frappe.get_meta("POS Profile").has_field("custom_use_invoice_series_prefix"):
		return
	
	# Get POS Profile to check opt-in flag
	if not doc.pos_profile:
		return
	
	try:
		profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
		
		# Check opt-in flag (defaults to off if column doesn't exist)
		if not profile.get("custom_use_invoice_series_prefix"):
			return
		
		restaurant_name = profile.get("custom_restaurant")
		if not restaurant_name:
			return
		
		restaurant = frappe.get_cached_doc("NDS Restaurant", restaurant_name)
		
		# Determine which prefix to use
		prefix = None
		
		# Check if this is an aggregator order
		if (doc.get("custom_nds_order_type") == "Aggregator" and 
			restaurant.get("aggregator_series_prefix")):
			prefix = restaurant.aggregator_series_prefix
		elif restaurant.get("invoice_series_prefix"):
			prefix = restaurant.invoice_series_prefix
		
		if prefix:
			# Sanitize prefix: strip whitespace, reject invalid characters
			prefix = prefix.strip()
			if not prefix or '.' in prefix or not re.match(r'^[A-Za-z0-9-]+$', prefix):
				frappe.log_error(
					f"Invalid invoice series prefix: {prefix}",
					"POS Invoice Naming"
				)
				return
			
			# Only override if naming_series is empty or the standard ERPNext POS default
			standard_pos_series = ("ACC-PINV-", "ACC-PSINV-")
			if not doc.naming_series or any(
				doc.naming_series.startswith(prefix) for prefix in standard_pos_series
			):
				doc.naming_series = f"{prefix}-.YY.-.#####"
	
	except Exception as e:
		frappe.log_error(
			f"Error setting POS Invoice naming series: {str(e)}",
			"POS Invoice Naming"
		)


def set_sales_invoice_naming(doc, method=None):
	"""
	Set naming series for Sales Invoice created by POS Invoice Merge Log
	when restaurant_prefix is enabled.
	Only applies when POS Profile has custom_use_invoice_series_prefix enabled.
	"""
	if doc.doctype != "Sales Invoice":
		return
	
	# Skip amended documents
	if doc.amended_from:
		return
	
	# Check if this is a consolidated invoice from POS Closing
	if not doc.get("is_consolidated"):
		return
	
	# Guard: return early if custom fields don't exist (unmigrated site)
	pos_profile_meta = frappe.get_meta("POS Profile")
	if not pos_profile_meta.has_field("custom_use_invoice_series_prefix"):
		return
	
	# Handle pos_profile being blank when merging by Customer Group
	pos_profile_name = doc.get("pos_profile")
	if not pos_profile_name:
		# Only filter on columns that exist
		filters = {"company": doc.company}
		if pos_profile_meta.has_field("custom_use_invoice_series_prefix"):
			filters["custom_use_invoice_series_prefix"] = 1
		if pos_profile_meta.has_field("custom_restaurant_prefix"):
			filters["custom_restaurant_prefix"] = 1
		else:
			# If custom_restaurant_prefix doesn't exist, can't proceed
			return
		
		# Try to find a POS Profile from the company with both flags enabled
		pos_profile_name = frappe.db.get_value("POS Profile", filters, "name")
		if not pos_profile_name:
			return
	
	try:
		profile = frappe.get_cached_doc("POS Profile", pos_profile_name)
		
		# Check opt-in flag (return if off or doesn't exist)
		if not profile.get("custom_use_invoice_series_prefix"):
			return
		
		# Check if restaurant prefix is enabled (return if off or doesn't exist)
		if not profile.get("custom_restaurant_prefix"):
			return
		
		restaurant_name = profile.get("custom_restaurant")
		if not restaurant_name:
			return
		
		restaurant = frappe.get_cached_doc("NDS Restaurant", restaurant_name)
		
		# Create a slug from restaurant name (sanitize properly)
		restaurant_slug = restaurant.name.lower()
		# Replace invalid characters with hyphens
		restaurant_slug = re.sub(r'[^a-z0-9-]+', '-', restaurant_slug)
		# Remove leading/trailing hyphens and collapse multiple hyphens
		restaurant_slug = re.sub(r'-+', '-', restaurant_slug).strip('-')
		
		if not restaurant_slug:
			return
		
		# Only override if naming_series is empty or the standard default
		if not doc.naming_series or doc.naming_series.startswith("ACC-SINV-"):
			doc.naming_series = f"{restaurant_slug}-SINV-.YY.-.#####"
	
	except Exception as e:
		frappe.log_error(
			f"Error setting Sales Invoice naming series: {str(e)}",
			"Sales Invoice Naming"
		)
