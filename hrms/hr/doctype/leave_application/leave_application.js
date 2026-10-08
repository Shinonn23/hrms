// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Leave Application", {
	setup: function (frm) {
		frm.set_query("employee", erpnext.queries.employee);
	},

	onload: function (frm) {
		// Ignore cancellation of doctype on cancel all.
		frm.ignore_doctypes_on_cancel_all = ["Leave Ledger Entry"];

		if (!frm.doc.posting_date) {
			frm.set_value("posting_date", frappe.datetime.get_today());
		}
	},

	onload_post_render(frm) {
		frm.trigger("half_day_datepicker");
	},

	validate: function (frm) {
		if (frm.doc.from_date === frm.doc.to_date && cint(frm.doc.half_day)) {
			frm.doc.half_day_date = frm.doc.from_date;
		} else if (frm.doc.half_day === 0) {
			frm.doc.half_day_date = "";
			frm.doc.half_day_period = "";
			frm.doc.half_day_2 = 0;
			frm.doc.half_day_date_2 = "";
			frm.doc.half_day_period_2 = "";
		}
		if (!cint(frm.doc.half_day_2)) {
			frm.doc.half_day_date_2 = "";
			frm.doc.half_day_period_2 = "";
		}
		frm.toggle_reqd(
			"half_day_date",
			cint(frm.doc.half_day) && frm.doc.from_date !== frm.doc.to_date,
		);
		frm.toggle_reqd("half_day_period", cint(frm.doc.half_day));
		frm.toggle_reqd("half_day_date_2", cint(frm.doc.half_day_2));
		frm.toggle_reqd("half_day_period_2", cint(frm.doc.half_day_2));
	},

	make_dashboard: function (frm) {
		let leave_details;
		let lwps;

		if (frm.doc.employee) {
			frappe.call({
				method: "hrms.hr.doctype.leave_application.leave_application.get_leave_details",
				async: false,
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date || frm.doc.posting_date,
					leave_application: frm.is_new() ? null : frm.doc.name,
				},
				callback: function (r) {
					if (!r.exc && r.message["leave_allocation"]) {
						leave_details = r.message["leave_allocation"];
					}
					lwps = r.message["lwps"];
				},
			});

			$("div").remove(".form-dashboard-section.custom");

			frm.dashboard.add_section(
				frappe.render_template("leave_application_dashboard", {
					data: leave_details,
				}),
				__("Allocated Leaves"),
			);
			frm.dashboard.show();

			let allowed_leave_types = Object.keys(leave_details);
			// lwps should be allowed for selection as they don't have any allocation
			allowed_leave_types = allowed_leave_types.concat(lwps);

			frm.set_query("leave_type", function () {
				return {
					filters: [["leave_type_name", "in", allowed_leave_types]],
				};
			});
		}
	},

	refresh: function (frm) {
		hrms.leave_utils.add_view_ledger_button(frm);
		if (frm.is_new()) {
			frm.trigger("calculate_total_days");
		}

		frm.set_intro("");
		if (frm.doc.__islocal && !in_list(frappe.user_roles, "Employee")) {
			frm.set_intro(__("Fill the form and save it"));
		} else if (
			frm.perm[0] &&
			frm.perm[0].submit &&
			!frm.is_dirty() &&
			!frm.is_new() &&
			!frappe.model.has_workflow(frm.doctype) &&
			frm.doc.docstatus === 0
		) {
			frm.set_intro(__("Submit this Leave Application to confirm."));
		}

		frm.trigger("set_employee");
		if (frm.doc.docstatus === 0) {
			frm.trigger("make_dashboard");
		}
	},

	async set_employee(frm) {
		if (frm.doc.employee) return;

		const employee = await hrms.get_current_employee(frm);
		if (employee) {
			frm.set_value("employee", employee);
		}
	},

	employee: function (frm) {
		frm.trigger("make_dashboard");
		frm.trigger("get_leave_balance");
		frm.trigger("calculate_total_days");
	},

	leave_type: function (frm) {
		frm.trigger("get_leave_balance");
		frm.trigger("calculate_total_days");
	},

	half_day: function (frm) {
		if (frm.doc.half_day) {
			if (frm.doc.from_date == frm.doc.to_date) {
				frm.set_value("half_day_date", frm.doc.from_date);
			} else {
				frm.trigger("half_day_datepicker");
			}
		} else {
			frm.set_value("half_day_date", "");
			frm.set_value("half_day_period", "");
			frm.set_value("half_day_2", 0);
		}
		frm.trigger("calculate_total_days");
	},

	half_day_2(frm) {
		if (frm.doc.half_day_2 && !frm.doc.half_day_date_2) {
			const firstDate = frm.doc.half_day_date;
			const defaultDate =
				firstDate && frm.doc.to_date !== firstDate
					? frm.doc.to_date
					: firstDate && frm.doc.from_date !== firstDate
						? frm.doc.from_date
						: "";
			frm.set_value("half_day_date_2", defaultDate || "");
		}
		if (!frm.doc.half_day_2) {
			frm.set_value("half_day_date_2", "");
			frm.set_value("half_day_period_2", "");
		}
		frm.trigger("half_day_datepicker");
		frm.trigger("calculate_total_days");
	},

	from_date: function (frm) {
		frm.events.validate_from_to_date(frm, "from_date");
		frm.trigger("make_dashboard");
		frm.trigger("half_day_datepicker");
		frm.trigger("calculate_total_days");
	},

	to_date: function (frm) {
		frm.events.validate_from_to_date(frm, "to_date");
		frm.trigger("make_dashboard");
		frm.trigger("half_day_datepicker");
		frm.trigger("calculate_total_days");
	},

	half_day_date(frm) {
		if (frm.doc.half_day_date && frm.doc.half_day_date === frm.doc.half_day_date_2) {
			frm.set_value("half_day_date_2", "");
		}
		if (frm.doc.half_day_2 && !frm.doc.half_day_date_2 && frm.doc.half_day_date) {
			const defaultDate =
				frm.doc.to_date !== frm.doc.half_day_date
					? frm.doc.to_date
					: frm.doc.from_date !== frm.doc.half_day_date
						? frm.doc.from_date
						: "";
			frm.set_value("half_day_date_2", defaultDate || "");
		}
		frm.trigger("half_day_datepicker");
		frm.trigger("calculate_total_days");
	},

	half_day_date_2(frm) {
		if (frm.doc.half_day_date_2 && frm.doc.half_day_date_2 === frm.doc.half_day_date) {
			frm.set_value("half_day_date_2", "");
			frappe.show_alert({
				message: __("The two half days must be on different dates."),
				indicator: "orange",
			});
		}
		frm.trigger("half_day_datepicker");
		frm.trigger("calculate_total_days");
	},

	validate_from_to_date: function (frm, updated_field) {
		if (!frm.doc.from_date || !frm.doc.to_date) return;

		const from_date = Date.parse(frm.doc.from_date);
		const to_date = Date.parse(frm.doc.to_date);

		if (to_date < from_date) {
			const other_field = updated_field === "from_date" ? "to_date" : "from_date";

			frm.set_value(other_field, frm.doc[updated_field]);
			frappe.show_alert({
				message: __("Changing '{0}' to {1}.", [
					__(frm.fields_dict[other_field].df.label),
					frappe.datetime.str_to_user(frm.doc[updated_field]),
				]),
				indicator: "blue",
			});
		}
	},

	half_day_datepicker: function (frm) {
		if (!frm.doc.from_date || !frm.doc.to_date) return;
		if (frm.doc.half_day_date && frm.doc.half_day_date === frm.doc.half_day_date_2) {
			frm.set_value({ half_day_date_2: "", half_day_period_2: "" });
			return;
		}
		const minDate = frappe.datetime.str_to_obj(frm.doc.from_date);
		const maxDate = frappe.datetime.str_to_obj(frm.doc.to_date);
		const firstDate = frm.doc.half_day_date
			? moment(frappe.datetime.str_to_obj(frm.doc.half_day_date)).format("YYYY-MM-DD")
			: null;
		const secondDate = frm.doc.half_day_date_2
			? moment(frappe.datetime.str_to_obj(frm.doc.half_day_date_2)).format("YYYY-MM-DD")
			: null;
		for (const fieldname of ["half_day_date", "half_day_date_2"]) {
			const field = frm.fields_dict[fieldname];
			if (!field) continue;
			const disabledDate = fieldname === "half_day_date" ? secondDate : firstDate;
			field.df.min_date = minDate;
			field.df.max_date = maxDate;
			field.df.disabled_dates = disabledDate ? [disabledDate] : [];
			field.datepicker?.update({
				minDate,
				maxDate,
				onRenderCell: (date, cellType) => {
					if (
						cellType === "day" &&
						disabledDate &&
						moment(date).format("YYYY-MM-DD") === disabledDate
					) {
						return { disabled: true, classes: "disabled" };
					}
				},
			});
		}
	},

	get_leave_balance: function (frm) {
		if (
			frm.doc.docstatus === 0 &&
			frm.doc.employee &&
			frm.doc.leave_type &&
			frm.doc.from_date &&
			frm.doc.to_date
		) {
			return frappe.call({
				method: "hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date,
					to_date: frm.doc.to_date,
					leave_type: frm.doc.leave_type,
					consider_all_leaves_in_the_allocation_period: 1,
					leave_application: frm.is_new() ? null : frm.doc.name,
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frm.set_value("leave_balance", r.message);
					} else {
						frm.set_value("leave_balance", "0");
					}
				},
			});
		}
	},

	calculate_total_days: function (frm) {
		const request_id = (frm._leave_days_request_id || 0) + 1;
		frm._leave_days_request_id = request_id;

		if (frm.doc.from_date && frm.doc.to_date && frm.doc.employee && frm.doc.leave_type) {
			// server call is done to include holidays in leave days calculations
			const args = {
				employee: frm.doc.employee,
				leave_type: frm.doc.leave_type,
				from_date: frm.doc.from_date,
				to_date: frm.doc.to_date,
				half_day: frm.doc.half_day,
				half_day_date: frm.doc.half_day_date,
				half_day_2: frm.doc.half_day_2,
				half_day_date_2: frm.doc.half_day_date_2,
				leave_application: frm.is_new() ? null : frm.doc.name,
			};
			return frappe.call({
				method: "hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days",
				args,
				callback: function (r) {
					if (request_id !== frm._leave_days_request_id) return;
					if (r && r.message != null) {
						frm.set_value("total_leave_days", r.message);
						frm.trigger("get_leave_balance");
					}
				},
			});
		}
	},

	posting_date: function (frm) {
		frm.trigger("make_dashboard");
		frm.trigger("get_leave_balance");
	},
});

frappe.tour["Leave Application"] = [
	{
		fieldname: "employee",
		title: "Employee",
		description: __("Select the Employee."),
	},
	{
		fieldname: "leave_type",
		title: "Leave Type",
		description: __(
			"Select type of leave the employee wants to apply for, like Sick Leave, Privilege Leave, Casual Leave, etc.",
		),
	},
	{
		fieldname: "from_date",
		title: "From Date",
		description: __("Select the start date for your Leave Application."),
	},
	{
		fieldname: "to_date",
		title: "To Date",
		description: __("Select the end date for your Leave Application."),
	},
	{
		fieldname: "half_day",
		title: "Half Day",
		description: __("To apply for a Half Day check 'Half Day' and select the Half Day Date"),
	},
];
