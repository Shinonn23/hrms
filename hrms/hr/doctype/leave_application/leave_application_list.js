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
	has_indicator_for_cancelled: true,
	// A refused request ends cancelled (no Status field in v16); show it as Rejected, not Cancelled.
	get_indicator(doc) {
		if (doc.docstatus === 2 && doc.rejected) {
			return [__("Rejected"), "red", "rejected,=,1"];
		}
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
	},
};
