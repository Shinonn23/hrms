// Thailand localization of the Employee form: the signature is made in a popup (Sign / Re-sign), not drawn in the form.

frappe.ui.form.on("Employee", {
	refresh(frm) {
		const signed = Boolean(frm.doc.signature);
		frm.set_df_property("sign_button", "label", signed ? __("Re-sign") : __("Sign"));
		// a new Employee has nothing to sign for yet, and a signature needs the right to change the form
		frm.toggle_display("sign_button", !frm.is_new() && frm.perm[0] && frm.perm[0].write);
	},

	sign_button(frm) {
		const dialog = new frappe.ui.Dialog({
			title: frm.doc.signature ? __("Re-sign") : __("Sign"),
			fields: [
				{
					fieldname: "signature",
					fieldtype: "Signature",
					label: __("Signature"),
					reqd: 1,
				},
			],
			primary_action_label: __("Save Signature"),
			primary_action(values) {
				dialog.hide();
				frm.set_value("signature", values.signature).then(() => frm.save());
			},
		});
		dialog.show();
	},
});
