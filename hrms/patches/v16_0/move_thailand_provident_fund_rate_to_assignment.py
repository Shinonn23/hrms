"""Move the provident fund rates from the Employee to the employee's Salary Structure Assignment.

An assignment is dated and only the payroll roles read it, so who is a member from when is kept as history instead of
a value on the Employee that changes the next slip. A salary structure formula reads the same names, so it needs no
change, but HRMS lets an Employee field win over an assignment field of the same name: the Employee fields must go.

An Employee rate is copied to the assignment in force today (else the latest one) when that assignment has none. An
employee with a rate and no submitted assignment cannot be copied; the rate is printed and logged before the field
goes, for the payroll team to enter on the employee's next assignment.
"""

import frappe
from frappe.utils import today

from hrms.regional.thailand.setup import make_custom_fields

FIELDS = ("provident_fund_rate", "provident_fund_employer_rate")


def execute():
	if not frappe.db.table_exists("Salary Structure Assignment"):
		return
	make_custom_fields()
	frappe.clear_cache(doctype="Salary Structure Assignment")
	present = [field for field in FIELDS if frappe.db.has_column("Employee", field)]
	if present:
		copy_rates(present)
	for field in FIELDS:
		for doctype, name in (
			("Property Setter", f"Employee-{field}-permlevel"),
			("Custom Field", f"Employee-{field}"),
		):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	frappe.clear_cache(doctype="Employee")


def copy_rates(present):
	members = frappe.get_all(
		"Employee", filters={"provident_fund_rate": (">", 0)}, fields=["name", *present], limit_page_length=0
	)
	left = []
	for employee in members:
		assignments = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": employee.name, "docstatus": 1},
			fields=["name", "from_date", "provident_fund_rate"],
			order_by="from_date desc",
		)
		in_force = [row for row in assignments if str(row.from_date) <= today()]
		target = (in_force or assignments or [None])[0]
		if not target:
			left.append([employee.name, *(employee.get(field) for field in present)])
		elif not target.provident_fund_rate:
			frappe.db.set_value(
				"Salary Structure Assignment",
				target.name,
				{field: employee.get(field) for field in present},
				update_modified=False,
			)
	if left:
		print(
			"Provident fund rates with no Salary Structure Assignment to hold them (employee, rate, employer rate):"
		)
		for row in left:
			print("  ", row)
		frappe.log_error(title="Provident fund rates not moved to an assignment", message=repr(left))
