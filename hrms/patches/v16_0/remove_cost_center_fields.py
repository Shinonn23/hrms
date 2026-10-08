# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


def execute():
	for field in (
		"Expense Claim-cost_center",
		"Employee-payroll_cost_center",
		"Department-payroll_cost_center",
		"Salary Structure Assignment-payroll_cost_centers",
	):
		frappe.delete_doc("Custom Field", field, force=True, ignore_missing=True)

	for property_setter in frappe.get_all(
		"Property Setter",
		filters={"field_name": "payroll_cost_center", "doc_type": ["in", ["Employee", "Department"]]},
		pluck="name",
	):
		frappe.delete_doc("Property Setter", property_setter, force=True, ignore_missing=True)

	for custom_field in frappe.get_all(
		"Custom Field",
		filters={"options": "Cost Center", "fieldtype": "Link"},
		pluck="name",
	):
		frappe.delete_doc("Custom Field", custom_field, force=True, ignore_missing=True)

	frappe.delete_doc("DocType", "Employee Cost Center", force=True, ignore_missing=True)
