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
	setup()


def after_migrate():
	setup()


def setup():
	"""Idempotent: a field that exists is moved to its place and relabelled, never duplicated."""
	make_custom_fields()
	make_property_setters()
	make_salutations()
	grant_payroll_field_permissions()


def make_custom_fields():
	create_custom_fields(HRMS_THAILAND_CUSTOM_FIELDS, ignore_validate=True)


def make_property_setters():
	for doctype, fieldname, prop, value, property_type in PROPERTY_SETTERS:
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
	security ID). A company's own policy may narrow or widen this afterwards."""
	for role in PAYROLL_ROLES:
		add_permission("Employee", role, PAYROLL_PERMLEVEL)
		update_permission_property("Employee", role, PAYROLL_PERMLEVEL, "read", 1)
		update_permission_property("Employee", role, PAYROLL_PERMLEVEL, "write", 1)
	frappe.clear_cache(doctype="Employee")
