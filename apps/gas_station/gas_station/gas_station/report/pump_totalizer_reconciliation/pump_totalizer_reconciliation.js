frappe.query_reports["Pump Totalizer Reconciliation"] = {
	filters: [
		{fieldname:"station",label:"Station",fieldtype:"Link",options:"Gas Station",reqd:1},
		{fieldname:"from_date",label:"From",fieldtype:"Date",default:frappe.datetime.add_days(frappe.datetime.get_today(),-7),reqd:1},
		{fieldname:"to_date",label:"To",fieldtype:"Date",default:frappe.datetime.get_today(),reqd:1}
	]
};
