frappe.ui.form.on("Employee Professional License", {
	setup(frm) {
		frm.set_query("license_type", () => ({ filters: { disabled: 0 } }));
	},

	onload(frm) {
		if (
			!frappe.user.has_role("HR Manager") &&
			!frappe.user.has_role("System Manager") &&
			!frm.doc.employee
		) {
			frappe.call("hrms.api.get_current_employee_info").then((r) => {
				if (r.message?.name) frm.set_value("employee", r.message.name);
			});
		}
	},

	refresh(frm) {
		const is_hr_manager =
			frappe.user.has_role("HR Manager") || frappe.user.has_role("System Manager");
		if (!is_hr_manager) frm.set_df_property("employee", "read_only", 1);

		if (!frm.is_new() && ["Draft", "Changes Requested"].includes(frm.doc.verification_status)) {
			frm.add_custom_button(__("Submit for Review"), () => {
				frm.call("submit_for_review").then(() => frm.reload_doc());
			});
		}

		if (is_hr_manager && frm.doc.verification_status === "Pending Review") {
			frm.add_custom_button(__("Verify"), () => {
				frm.call("verify_license").then(() => frm.reload_doc());
			});
			frm.add_custom_button(__("Request Changes"), () => {
				frappe.prompt(
					[
						{
							fieldname: "comment",
							fieldtype: "Small Text",
							label: __("Changes Requested"),
							reqd: 1,
						},
					],
					(values) => {
						frm.call("request_changes", { comment: values.comment }).then(() => frm.reload_doc());
					},
					__("Request Changes"),
					__("Send"),
				);
			});
		}
	},
});
