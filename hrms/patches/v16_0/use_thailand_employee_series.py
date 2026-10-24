"""Employee numbers follow YY-BE.MM.### (Buddhist-era year, month, running number: 6910001).

The series is the only option of the Employee Series field, and a Select refuses a value that is not an option, so
every Employee that still carries the old series (HR-EMP-) is saved with the new one. Names are not changed: an
Employee keeps the number it has.
"""

import frappe

from hrms.regional.thailand.constants import EMPLOYEE_SERIES
from hrms.regional.thailand.setup import make_property_setters


def execute():
	if not frappe.db.table_exists("Employee"):
		return
	make_property_setters()
	frappe.db.sql(
		"update `tabEmployee` set naming_series = %s where ifnull(naming_series, '') != %s",
		(EMPLOYEE_SERIES, EMPLOYEE_SERIES),
	)
	frappe.clear_cache(doctype="Employee")
