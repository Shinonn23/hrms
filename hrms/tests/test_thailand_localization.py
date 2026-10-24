"""Thailand payroll fields: layout checks that do not need a Frappe site."""

import json
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.model import naming

from hrms import hooks
from hrms.patches.v16_0 import move_thailand_provident_fund_rate_to_assignment as move_rates
from hrms.patches.v16_0 import use_thailand_employee_series as use_series
from hrms.regional.thailand import constants
from hrms.regional.thailand import naming as thai_naming

HRMS = Path(__file__).resolve().parents[1]
ERPNEXT = HRMS.parents[1] / "erpnext" / "erpnext"


def field_order(path):
	return json.loads(path.read_text())["field_order"]


class TestThailandFieldLayout(TestCase):
	def test_every_field_hangs_from_a_field_that_exists_or_is_laid_out_before_it(self):
		known = {
			"Employee": set(field_order(ERPNEXT / "setup/doctype/employee/employee.json")),
			"Salary Structure Assignment": set(
				field_order(
					HRMS / "payroll/doctype/salary_structure_assignment/salary_structure_assignment.json"
				)
			),
			# Salary Component 'type' and Company 'skills' come from the doctype and from hrms/setup.py.
			"Salary Component": {"type"},
			"Company": {"skills"},
		}
		for doctype, fields in constants.HRMS_THAILAND_CUSTOM_FIELDS.items():
			placed = known[doctype]
			for field in fields:
				self.assertIn(field["insert_after"], placed, f"{doctype}.{field['fieldname']}")
				placed.add(field["fieldname"])

	def test_each_section_has_a_label_and_two_columns_at_most(self):
		for doctype, fields in constants.HRMS_THAILAND_CUSTOM_FIELDS.items():
			columns = 0
			for field in fields:
				if field["fieldtype"] == "Section Break":
					self.assertTrue(field["label"], doctype)
					columns = 1
				elif field["fieldtype"] == "Column Break":
					columns += 1
					self.assertLessEqual(columns, 2, doctype)

	def test_the_national_id_and_social_security_id_are_payroll_private(self):
		fields = {f["fieldname"]: f for f in constants.HRMS_THAILAND_CUSTOM_FIELDS["Employee"]}
		for name in ("national_id_number", "social_security_id"):
			self.assertEqual(fields[name]["permlevel"], constants.PAYROLL_PERMLEVEL)
		self.assertNotIn("permlevel", fields["social_security_eligible"])

	def test_the_provident_fund_rates_are_on_the_assignment_and_nowhere_else(self):
		names = {
			doctype: [f["fieldname"] for f in fields]
			for doctype, fields in constants.HRMS_THAILAND_CUSTOM_FIELDS.items()
		}
		self.assertIn("provident_fund_rate", names["Salary Structure Assignment"])
		self.assertIn("provident_fund_employer_rate", names["Salary Structure Assignment"])
		self.assertNotIn("provident_fund_rate", names["Employee"])

	def test_the_statutory_types_are_the_select_options(self):
		field = constants.HRMS_THAILAND_CUSTOM_FIELDS["Salary Component"][0]
		self.assertEqual(field["options"].split("\n")[1:], list(constants.STATUTORY_TYPES))


def row(**values):
	return frappe._dict(values)


class TestMoveProvidentFundRate(TestCase):
	def run_patch(
		self, members, assignments, columns=("provident_fund_rate", "provident_fund_employer_rate")
	):
		db = Mock()
		db.table_exists.return_value = True
		db.has_column.side_effect = lambda doctype, field: field in columns
		db.exists.return_value = True

		def get_all(doctype, **kwargs):
			if doctype == "Employee":
				return members
			return assignments[kwargs["filters"]["employee"]]

		frappe_mock = Mock(db=db, get_all=Mock(side_effect=get_all))
		with (
			patch.object(move_rates, "frappe", frappe_mock),
			patch.object(move_rates, "today", return_value="2026-10-24"),
			patch.object(move_rates, "make_custom_fields") as fields,
			patch("builtins.print"),
		):
			move_rates.execute()
		return frappe_mock, fields

	def test_the_rate_goes_to_the_assignment_in_force_and_the_employee_fields_are_removed(self):
		members = [row(name="6511003", provident_fund_rate=5, provident_fund_employer_rate=0)]
		assignments = {
			"6511003": [
				row(name="SSA-NEW", from_date="2027-01-01", provident_fund_rate=0),
				row(name="SSA-NOW", from_date="2026-01-01", provident_fund_rate=0),
			]
		}
		frappe_mock, fields = self.run_patch(members, assignments)
		fields.assert_called_once()
		frappe_mock.db.set_value.assert_called_once_with(
			"Salary Structure Assignment",
			"SSA-NOW",
			{"provident_fund_rate": 5, "provident_fund_employer_rate": 0},
			update_modified=False,
		)
		deleted = [call.args[:2] for call in frappe_mock.delete_doc.call_args_list]
		self.assertIn(("Custom Field", "Employee-provident_fund_rate"), deleted)
		self.assertIn(("Custom Field", "Employee-provident_fund_employer_rate"), deleted)
		self.assertIn(("Property Setter", "Employee-provident_fund_rate-permlevel"), deleted)

	def test_an_assignment_that_already_has_a_rate_is_left_alone(self):
		members = [row(name="6511003", provident_fund_rate=5, provident_fund_employer_rate=0)]
		assignments = {"6511003": [row(name="SSA-NOW", from_date="2026-01-01", provident_fund_rate=3)]}
		frappe_mock, _ = self.run_patch(members, assignments)
		frappe_mock.db.set_value.assert_not_called()
		frappe_mock.log_error.assert_not_called()

	def test_a_rate_with_no_assignment_is_logged_before_the_field_goes(self):
		members = [row(name="6511003", provident_fund_rate=5, provident_fund_employer_rate=0)]
		frappe_mock, _ = self.run_patch(members, {"6511003": []})
		frappe_mock.db.set_value.assert_not_called()
		self.assertIn("6511003", frappe_mock.log_error.call_args.kwargs["message"])
		self.assertTrue(frappe_mock.delete_doc.called)

	def test_a_site_without_the_employee_columns_only_gets_the_assignment_fields(self):
		frappe_mock, fields = self.run_patch([], {}, columns=())
		fields.assert_called_once()
		frappe_mock.log_error.assert_not_called()
		frappe_mock.db.set_value.assert_not_called()


class TestEmployeeNumber(TestCase):
	def parse(self, series, doc=None, now=datetime(2026, 10, 24)):
		# Frappe asks the hook for a part it does not know: answer it with the functions the hook names
		parsers = {
			part: [getattr(thai_naming, path.rsplit(".", 1)[1])]
			for part, path in hooks.naming_series_variables.items()
		}
		with (
			patch.object(thai_naming, "now_datetime", return_value=now),
			patch.object(naming, "now_datetime", return_value=now),
			patch.object(naming, "has_custom_parser", side_effect=parsers.get),
			patch.object(naming.frappe, "get_attr", side_effect=lambda method: method),
		):
			return naming.parse_naming_series(series, doc=doc, number_generator=lambda key, digits: "001")

	def test_the_buddhist_era_parts_are_of_today_without_a_date_of_joining(self):
		self.assertEqual(self.parse("YY-BE"), "69")
		self.assertEqual(self.parse("YYYY-BE"), "2569")
		self.assertEqual(self.parse("MM-BE"), "10")
		self.assertEqual(thai_naming.buddhist_year(datetime(2025, 10, 1)), 2568)

	def test_the_employee_number_follows_the_date_of_joining(self):
		self.assertEqual(constants.EMPLOYEE_SERIES, "YY-BE.MM-BE.###")
		joined = frappe._dict(date_of_joining="2025-10-01")
		# today is October 2026, the employee joined in October 2025: 68, 10
		self.assertEqual(self.parse(constants.EMPLOYEE_SERIES, joined), "6810001")
		self.assertEqual(
			self.parse(constants.EMPLOYEE_SERIES, frappe._dict(date_of_joining="2026-01-15")), "6901001"
		)
		self.assertEqual(self.parse(constants.EMPLOYEE_SERIES), "6910001")

	def test_the_series_is_the_only_option_of_the_employee_series_field(self):
		setters = {(d, f, p): v for d, f, p, v, _ in constants.PROPERTY_SETTERS}
		self.assertEqual(setters[("Employee", "naming_series", "options")], constants.EMPLOYEE_SERIES)

	def test_every_employee_still_on_the_old_series_gets_the_new_one(self):
		db = Mock()
		db.table_exists.return_value = True
		with (
			patch.object(use_series, "frappe", Mock(db=db)),
			patch.object(use_series, "make_property_setters") as setters,
		):
			use_series.execute()
		setters.assert_called_once()
		sql = db.sql.call_args
		self.assertIn("update `tabEmployee` set naming_series", sql.args[0])
		self.assertEqual(sql.args[1][0], constants.EMPLOYEE_SERIES)


class TestEmployeeNameLayout(TestCase):
	def test_the_thai_name_block_comes_before_the_english_one_and_the_basics_after(self):
		order = field_order(ERPNEXT / "setup/doctype/employee/employee.json")
		thai = ["naming_series", "salutation", "first_name", "middle_name", "last_name", "employee_name"]
		self.assertEqual([order.index(f) for f in thai], sorted(order.index(f) for f in thai))
		self.assertNotIn("column_break1", order)
		english = [f["fieldname"] for f in constants.HRMS_THAILAND_CUSTOM_FIELDS["Employee"][:6]]
		self.assertEqual(
			english,
			[
				"column_break_name_en",
				"salutation_en",
				"first_name_en",
				"middle_name_en",
				"last_name_en",
				"full_name_en",
			],
		)
		self.assertLess(order.index("employee_name"), order.index("column_break_9"))
		self.assertLess(order.index("column_break_9"), order.index("gender"))
		self.assertLess(order.index("date_of_birth"), order.index("date_of_joining"))
		self.assertLess(order.index("date_of_joining"), order.index("status"))

	def test_the_signature_is_shown_and_made_with_a_button(self):
		fields = {f["fieldname"]: f for f in constants.HRMS_THAILAND_CUSTOM_FIELDS["Employee"]}
		self.assertEqual(fields["sign_button"]["fieldtype"], "Button")
		self.assertEqual(fields["sign_button"]["insert_after"], "signature")
		self.assertIn(("Employee", "signature", "read_only", 1, "Check"), constants.PROPERTY_SETTERS)
		self.assertIn("public/js/thailand/employee.js", hooks.doctype_js["Employee"])
