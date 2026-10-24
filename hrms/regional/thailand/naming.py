"""Naming series parts of the Thai calendar: YY-BE (69) and YYYY-BE (2569) for the Buddhist-era year.

A series is written `YY-BE.MM.###`; Frappe asks `naming_series_variables` (hooks.py) for the part it does not know.
"""

from frappe.utils import now_datetime

BUDDHIST_ERA_OFFSET = 543


def buddhist_year(date=None):
	return (date or now_datetime()).year + BUDDHIST_ERA_OFFSET


def year_be_short(doc=None, part=None):
	"""YY-BE: the last two digits of the Buddhist-era year, 69 for 2569."""
	return f"{buddhist_year() % 100:02d}"


def year_be(doc=None, part=None):
	"""YYYY-BE: the Buddhist-era year, 2569."""
	return str(buddhist_year())
