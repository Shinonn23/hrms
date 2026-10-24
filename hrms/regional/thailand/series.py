"""Keep the running number of the Employee series in step with the numbers that exist.

Frappe numbers a new document from a counter (tabSeries, one row per prefix: `6910` for YY-BE.MM.###) and does not
look at the names already taken. Rename Employee 6910050 to 6910051 while the counter stands at 50 and the next
Employee is numbered 6910051 too: the save fails with "already exists" until the counter has moved on. `plan` finds
every prefix whose counter is below its highest number, `apply` raises it to that number.
"""

from __future__ import annotations

import re

import frappe

# What each part of a series is in a name; a part that is none of these is text and stands for itself.
PART_PATTERNS = {
	"YY-BE": r"\d{2}",
	"YYYY-BE": r"\d{4}",
	"YY": r"\d{2}",
	"YYYY": r"\d{4}",
	"MM": r"\d{2}",
	"DD": r"\d{2}",
}


def split_series(series: str) -> tuple[list[str], int]:
	"""The parts before the running number, and how many digits it has at least: YY-BE.MM.### -> (['YY-BE', 'MM'], 3)."""
	parts = [part for part in series.split(".") if part]
	for index, part in enumerate(parts):
		if part.startswith("#"):
			if index != len(parts) - 1:
				raise ValueError(f"The running number must end the series, not {series}.")
			return parts[:index], len(part)
	raise ValueError(f"The series {series} has no running number (###).")


def name_pattern(series: str) -> re.Pattern:
	"""A regular expression with the groups `prefix` (the counter's key) and `number` for the names of a series."""
	prefix_parts, digits = split_series(series)
	prefix = "".join(PART_PATTERNS.get(part) or re.escape(part) for part in prefix_parts)
	return re.compile(rf"^(?P<prefix>{prefix})(?P<number>\d{{{digits},}})$")


def highest_numbers(series: str, names: list[str]) -> dict[str, int]:
	"""The highest running number per prefix among the names that follow the series (others are left out)."""
	pattern = name_pattern(series)
	highest: dict[str, int] = {}
	for name in names:
		match = pattern.match(name or "")
		if match:
			key = match.group("prefix")
			highest[key] = max(highest.get(key, 0), int(match.group("number")))
	return highest


def plan(series: str, names: list[str], counters: dict[str, int], current_prefix: str, all_prefixes=False):
	"""One row per prefix: its highest number, its counter and what to do (`raise`, `ok`, or `ahead` when the counter
	is above the highest number, which is safe: numbers are skipped, never repeated). Only the prefix of today and the
	prefixes that already have a counter are looked at, unless all_prefixes (old months have no counter to repair)."""
	highest = highest_numbers(series, names)
	rows = []
	for key in sorted(set(highest) | set(counters) | {current_prefix}):
		if not (all_prefixes or key in counters or key == current_prefix):
			continue
		top = highest.get(key, 0)
		counter = counters.get(key)
		action = "raise" if (counter or 0) < top else "ahead" if (counter or 0) > top else "ok"
		rows.append({"prefix": key, "highest": top, "counter": counter, "action": action})
	return rows


def current_series() -> str:
	"""The Employee series the form offers (the first option of the Series field)."""
	options = (frappe.get_meta("Employee").get_field("naming_series").options or "").split("\n")
	return next(option for option in options if option)


def current_prefix(series: str) -> str:
	from frappe.model.naming import parse_naming_series

	return parse_naming_series(split_series(series)[0])


def sync(series: str | None = None, apply: bool = False, all_prefixes: bool = False) -> dict:
	series = series or current_series()
	names = frappe.get_all("Employee", pluck="name", limit_page_length=0)
	counters = {
		name: int(current or 0) for name, current in frappe.db.sql("select name, `current` from `tabSeries`")
	}
	rows = plan(series, names, counters, current_prefix(series), all_prefixes)
	todo = [row for row in rows if row["action"] == "raise"]
	if apply:
		for row in todo:
			frappe.db.sql(
				"insert into `tabSeries` (name, `current`) values (%s, %s) on duplicate key update `current` = %s",
				(row["prefix"], row["highest"], row["highest"]),
			)
		frappe.db.commit()
	return {"series": series, "applied": bool(apply), "to_raise": len(todo), "rows": rows}
