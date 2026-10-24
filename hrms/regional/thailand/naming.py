"""Naming series parts of the Thai calendar, taken from the date of the document.

A series is written `YY-BE.MM-BE.###`: YY-BE is the Buddhist-era year (69 for 2026), YYYY-BE the full year (2569) and
MM-BE the month, all of the document's date, which is the Date of Joining of an Employee (the number 6810001 is the
first employee who joined in October 2568) and today for a document without one. Frappe asks `naming_series_variables`
(hooks.py) for a part it does not know.
"""

from frappe.utils import getdate, now_datetime

BUDDHIST_ERA_OFFSET = 543
DATE_FIELD = "date_of_joining"


def reference_date(doc=None):
	"""The date the number is for: the document's Date of Joining, else today."""
	value = doc.get(DATE_FIELD) if doc is not None and hasattr(doc, "get") else None
	return getdate(value) if value else now_datetime()


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
