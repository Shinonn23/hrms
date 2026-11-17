frappe.listview_settings["Leave Application"] = {
	add_fields: [
		"leave_type",
		"employee",
		"employee_name",
		"total_leave_days",
		"from_date",
		"to_date",
		"rejected",
	],
	// A refused request ends cancelled (no Status field in v16); show it as Rejected, not Cancelled.
	get_indicator(doc) {
		if (doc.docstatus === 2 && doc.rejected) {
			return [__("Rejected"), "red", "rejected,=,1"];
		}
	},
};
