frappe.query_reports["Employee Professional License"] = {
	filters: [
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "license_type",
			label: __("License Type"),
			fieldtype: "Link",
			options: "Employee Professional License Type",
		},
		{
			fieldname: "verification_status",
			label: __("Verification Status"),
			fieldtype: "Select",
			options: "\nDraft\nPending Review\nVerified\nChanges Requested",
		},
		{
			fieldname: "validity_status",
			label: __("Validity Status"),
			fieldtype: "Select",
			options: "\nActive\nExpiring Soon\nExpired\nNo Expiry",
		},
	],
};
