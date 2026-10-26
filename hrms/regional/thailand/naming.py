"""Naming series parts of the Thai calendar, taken from the date of the document.

A series is written `YY-BE.MM-BE.###`: YY-BE is the Buddhist-era year (69 for 2026), YYYY-BE the full year (2569) and
MM-BE the month, all of the business date of the document being named (SO6910001 for a Sales Order of October 2026).
The date field is, in this order: the one an app declares for the doctype in the `naming_series_date_fields` hook
(doctype -> fieldname; the last app wins), date_of_joining for an Employee (6810001 is the first employee who joined in
October 2568), else the first filled of posting_date, transaction_date and date. Today is used when there is no
document, no date, or the document does not set its own posting time (set_posting_time 0: validate overwrites
posting_date with today), except in an import or a restore, which keep the posting_date. Frappe asks
`naming_series_variables` (hooks.py) for a part it does not know, sometimes without a document.
"""

import frappe
from frappe.model.base_document import BaseDocument
from frappe.utils import getdate, now_datetime

BUDDHIST_ERA_OFFSET = 543
EMPLOYEE_DATE_FIELD = "date_of_joining"
DATE_FIELDS = ("posting_date", "transaction_date", "date")


def date_field_hooks():
	"""doctype -> fieldname from the `naming_series_date_fields` hook of every app; the last app wins."""
	try:
		declared = frappe.get_hooks("naming_series_date_fields") or {}
	except Exception:  # no site is connected (offline use) or the hooks cannot be read
		declared = {}
	mappings = declared if isinstance(declared, list | tuple) else [declared]
	merged = {}
	for mapping in mappings:
		if not isinstance(mapping, dict):
			continue
		for doctype, fieldname in mapping.items():
			if isinstance(fieldname, list | tuple):
				fieldname = fieldname[-1] if fieldname else None
			if fieldname:
				merged[doctype] = fieldname
	return merged


def reference_date(doc=None):
	"""The date the number is for: the business date of the document, else today.

	The field comes from the `naming_series_date_fields` hook, else date_of_joining for an Employee, else the first
	filled of posting_date, transaction_date and date. A document that does not set its own posting time gets today
	as posting_date on validate, so today is used for it too. `doc` may be None (Frappe asks without a document).
	"""
	if doc is None or not hasattr(doc, "get"):
		return now_datetime()
	doctype = doc.get("doctype")
	keeps_date = in_import() or (getattr(doc, "flags", None) or {}).get("from_restore")
	if not keeps_date and doc.get("set_posting_time") in (0, "0", False) and "posting_date" in doc_keys(doc):
		return now_datetime()
	hooked = date_field_hooks().get(doctype)
	if hooked:
		fields = [hooked]
	else:
		# a document that does not say what it is (plain dict) is read as an Employee first
		fields = [EMPLOYEE_DATE_FIELD] if doctype == "Employee" else list(DATE_FIELDS)
		if not doctype:
			fields = [EMPLOYEE_DATE_FIELD, *fields]
	for fieldname in fields:
		value = doc.get(fieldname)
		if value:
			return getdate(value)
	return now_datetime()


def in_import():
	try:
		return bool(frappe.flags.get("in_import"))
	except RuntimeError:  # no site is connected (offline use)
		return False


def doc_keys(doc):
	"""The fields a document has, whether it is a Document or a plain dict."""
	if isinstance(doc, BaseDocument):
		return {df.fieldname for df in doc.meta.fields} | {"name", "creation", "modified"}
	return set(doc.keys()) if hasattr(doc, "keys") else set()


def buddhist_year(date=None):
	return (date or now_datetime()).year + BUDDHIST_ERA_OFFSET


def year_be_short(doc=None, part=None):
	"""YY-BE: the last two digits of the Buddhist-era year, 69 for 2569."""
	return f"{buddhist_year(reference_date(doc)) % 100:02d}"


def year_be(doc=None, part=None):
	"""YYYY-BE: the Buddhist-era year, 2569."""
	return str(buddhist_year(reference_date(doc)))


def month_be(doc=None, part=None):
	"""MM-BE: the month of the date, 01 to 12."""
	return f"{reference_date(doc).month:02d}"
