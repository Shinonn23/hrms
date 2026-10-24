"""Employee numbers follow YY-BE.MM-BE.### (Buddhist-era year and month of the Date of Joining, running number: 6810001).

The series is the only option of the Employee Series field, and a Select refuses a value that is not an option, so
every Employee that still carries the old series (HR-EMP-) is saved with the new one. Names are not changed: an
Employee keeps the number it has.

Each month has a counter (tabSeries, key 6810) that starts at 0, so an employee who joins in a month that already has
numbers would be named 6810001 again. The counter of every month is set to the highest number that exists.
"""

import re

import frappe

from hrms.regional.thailand.constants import EMPLOYEE_SERIES
from hrms.regional.thailand.setup import make_property_setters

# YY-BE (2 digits) MM-BE (2 digits) then the running number (3 digits or more): 6810001
NUMBER = re.compile(r"^(?P<prefix>\d{4})(?P<number>\d{3,})$")


def execute():
	if not frappe.db.table_exists("Employee"):
		return
	make_property_setters()
	frappe.db.sql(
		"update `tabEmployee` set naming_series = %s where ifnull(naming_series, '') != %s",
		(EMPLOYEE_SERIES, EMPLOYEE_SERIES),
	)
	for prefix, highest in highest_numbers(
		frappe.get_all("Employee", pluck="name", limit_page_length=0)
	).items():
		raise_counter(prefix, highest)
	frappe.clear_cache(doctype="Employee")


def highest_numbers(names):
	highest = {}
	for name in names:
		match = NUMBER.match(name or "")
		if match:
			prefix = match.group("prefix")
			highest[prefix] = max(highest.get(prefix, 0), int(match.group("number")))
	return highest


def raise_counter(prefix, value):
	"""Never lower a counter: a number is skipped, never repeated."""
	current = frappe.db.get_value("Series", prefix, "current", order_by="name")
	if current is None:
		frappe.db.sql("insert into `tabSeries` (name, `current`) values (%s, %s)", (prefix, value))
	elif int(current) < value:
		frappe.db.sql("update `tabSeries` set `current` = %s where name = %s", (value, prefix))
