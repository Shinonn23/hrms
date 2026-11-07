"""Thai payroll localization of HRMS: the fields of `constants.py`, and who may read the payroll ones."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import add_permission, update_permission_property

from hrms.regional.thailand.constants import (
	HRMS_THAILAND_CUSTOM_FIELDS,
	PAYROLL_PERMLEVEL,
	PAYROLL_ROLES,
	PROPERTY_SETTERS,
	THAI_SALUTATIONS,
)


def after_install():
	"""The one time the payroll rights are given (Role Profile Authority Design 12.1)."""
	setup()
	grant_payroll_field_permissions()


def after_migrate():
	"""Schema only: a migrate adds what is missing and writes nothing again that a site may have changed."""
	setup()


def setup():
	"""Idempotent and create-only: a field or property that exists is left as the site has it."""
	make_custom_fields()
	make_property_setters(overwrite=False)
	make_salutations()


def make_custom_fields():
	create_custom_fields(HRMS_THAILAND_CUSTOM_FIELDS, ignore_validate=True, update=False)


def make_property_setters(overwrite=True):
	"""`overwrite=False` (every migrate): only a property with no Property Setter yet. The patch that moved Employees
	to the Thai series writes it with `overwrite=True`."""
	for doctype, fieldname, prop, value, property_type in PROPERTY_SETTERS:
		if not overwrite and frappe.db.exists(
			"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": prop}
		):
			continue
		make_property_setter(
			doctype, fieldname, prop, value, property_type, validate_fields_for_doctype=False
		)
	frappe.clear_cache(doctype="Employee")


def make_salutations():
	for salutation in THAI_SALUTATIONS:
		if not frappe.db.exists("Salutation", salutation):
			frappe.get_doc({"doctype": "Salutation", "salutation": salutation}).insert(
				ignore_permissions=True
			)


def grant_payroll_field_permissions():
	"""HR Manager and Payroll Manager read and write the permlevel 1 fields of Employee (national ID, social
	security ID). Only `after_install` calls it: a migrate must not give the rights again after a company's own policy
	(the Role Profile flags `reads_employee_pay_fields` / `edits_employee_pay_fields`) narrowed them."""
	for role in PAYROLL_ROLES:
		add_permission("Employee", role, PAYROLL_PERMLEVEL)
		update_permission_property("Employee", role, PAYROLL_PERMLEVEL, "read", 1)
		update_permission_property("Employee", role, PAYROLL_PERMLEVEL, "write", 1)
	frappe.clear_cache(doctype="Employee")
