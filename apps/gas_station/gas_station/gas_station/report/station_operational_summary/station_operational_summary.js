frappe.query_reports["Station Operational Summary"] = {
	filters: [
		{fieldname:"station",label:"Station",fieldtype:"Link",options:"Gas Station"},
		{fieldname:"from_date",label:"From",fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-7)},
		{fieldname:"to_date",label:"To",fieldtype:"Date",default:frappe.datetime.get_today()}
	]
};
