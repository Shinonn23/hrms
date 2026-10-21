# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Bring back the payroll cost center custom fields removed by the retired
`remove_cost_center_fields` patch.

Payroll reads Employee and Department `payroll_cost_center` (custom fields that HRMS creates on
install) when it splits salary costs, so they must exist again. Their values stay empty: payroll
then books on the Payroll Entry's cost center, which defaults to the company's. The rest of the
restoration (default cost centers, back-filling empty links) is done by ERPNext's
`restore_cost_center` patch.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.setup import get_custom_fields

FIELDS = {
	"Department": ("payroll_cost_center",),
	"Employee": ("payroll_cost_center",),
}


def execute():
	custom_fields = get_custom_fields()
	fields = {
		doctype: [field for field in custom_fields.get(doctype, []) if field["fieldname"] in fieldnames]
		for doctype, fieldnames in FIELDS.items()
	}
	create_custom_fields(fields, ignore_validate=True)

	# fields placed after payroll_cost_center keep their upstream position
	for doctype, fieldnames in FIELDS.items():
		for field in custom_fields.get(doctype, []):
			if field.get("insert_after") in fieldnames:
				name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]})
				if name:
					frappe.db.set_value("Custom Field", name, "insert_after", field["insert_after"])

	for doctype in FIELDS:
		frappe.clear_cache(doctype=doctype)
