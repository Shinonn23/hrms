# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from hrms.hr.doctype.employee_professional_license.employee_professional_license import is_hr_manager


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not is_hr_manager():
		frappe.throw(_("Only HR Managers can view this report"), frappe.PermissionError)
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 140,
		},
		{
			"label": _("License Type"),
			"fieldname": "license_type",
			"fieldtype": "Link",
			"options": "Employee Professional License Type",
			"width": 180,
		},
		{"label": _("License Number"), "fieldname": "license_number", "fieldtype": "Data", "width": 150},
		{
			"label": _("Issuing Authority"),
			"fieldname": "issuing_authority",
			"fieldtype": "Data",
			"width": 160,
		},
		{"label": _("Jurisdiction"), "fieldname": "jurisdiction", "fieldtype": "Data", "width": 130},
		{"label": _("Issue Date"), "fieldname": "issue_date", "fieldtype": "Date", "width": 110},
		{"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Verification Status"),
			"fieldname": "verification_status",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Validity Status"),
			"fieldname": "validity_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{"label": _("Review Comment"), "fieldname": "review_comment", "fieldtype": "Data", "width": 200},
	]


def get_data(filters):
	today = getdate()
	conditions = ["1 = 1"]
	values = {"today": today, "expiry_cutoff": add_days(today, 90)}

	for field in ("employee", "license_type", "verification_status"):
		if filters.get(field):
			conditions.append(f"license.{field} = %({field})s")
			values[field] = filters[field]

	if filters.get("validity_status"):
		conditions.append(
			"""CASE
				WHEN license.no_expiry = 1 THEN 'No Expiry'
				WHEN license.expiry_date < %(today)s THEN 'Expired'
				WHEN license.expiry_date <= %(expiry_cutoff)s THEN 'Expiring Soon'
				ELSE 'Active'
			END = %(validity_status)s"""
		)
		values["validity_status"] = filters.validity_status

	return frappe.db.sql(
		f"""
		SELECT
			license.employee,
			employee.employee_name,
			employee.department,
			license.license_type,
			license.license_number,
			license.issuing_authority,
			license.jurisdiction,
			license.issue_date,
			license.expiry_date,
			license.verification_status,
			CASE
				WHEN license.no_expiry = 1 THEN 'No Expiry'
				WHEN license.expiry_date < %(today)s THEN 'Expired'
				WHEN license.expiry_date <= %(expiry_cutoff)s THEN 'Expiring Soon'
				ELSE 'Active'
			END AS validity_status,
			license.review_comment
		FROM `tabEmployee Professional License` license
		INNER JOIN `tabEmployee` employee ON employee.name = license.employee
		WHERE {' AND '.join(conditions)}
		ORDER BY license.expiry_date IS NULL, license.expiry_date, employee.employee_name
		""",
		values,
		as_dict=True,
	)
