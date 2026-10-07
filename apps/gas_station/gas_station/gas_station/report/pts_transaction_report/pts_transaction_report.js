frappe.query_reports["PTS Transaction Report"] = {
	filters: [
		{fieldname:"station",label:"Station",fieldtype:"Link",options:"Gas Station"},
		{fieldname:"from_date",label:"From",fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-7)},
		{fieldname:"to_date",label:"To",fieldtype:"Date",default:frappe.datetime.get_today()},
		{fieldname:"processing_status",label:"Processing Status",fieldtype:"Select",options:["","Received","Processing","Processed","Failed","Duplicate","Ignored"].join("\n")}
	]
};
