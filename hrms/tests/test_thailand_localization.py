"""Thailand payroll fields: layout checks that do not need a Frappe site."""

import json
import os
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
from hrms.regional.thailand import setup as thai_setup

HRMS = Path(__file__).resolve().parents[1]
# the ERPNext fork holds Employee and Company: next to this app in a bench, else the directory CD_FORK_ERPNEXT names
ERPNEXT = Path(os.environ.get("CD_FORK_ERPNEXT") or HRMS.parents[1] / "erpnext") / "erpnext"


def field_order(path):
	return json.loads(path.read_text())["field_order"]


# The Thailand fields of the payroll DocTypes, in the DocType JSON of the forks (Siwat, 8 Nov 2026): Employee and Company
# are DocTypes of the ERPNext fork, Salary Structure Assignment, Salary Component and Expense Claim of this one.
THAI_FIELDS = {
	"Employee": (
		"column_break_name_en",
		"salutation_en",
		"first_name_en",
		"middle_name_en",
		"last_name_en",
		"full_name_en",
		"sign_button",
		"national_id_section",
		"national_id_number",
		"social_security_section",
		"social_security_id",
		"social_security_column",
		"social_security_eligible",
	),
	"Salary Structure Assignment": (
		"provident_fund_section",
		"provident_fund_rate",
		"provident_fund_column",
		"provident_fund_employer_rate",
	),
	"Salary Component": ("thai_statutory_type",),
	"Company": (
		"social_security_section",
		"social_security_account_no",
		"social_security_column",
		"social_security_branch_no",
	),
}
JSON_OF = {
	"Employee": ERPNEXT / "setup/doctype/employee/employee.json",
	"Company": ERPNEXT / "setup/doctype/company/company.json",
	"Salary Structure Assignment": HRMS
	/ "payroll/doctype/salary_structure_assignment/salary_structure_assignment.json",
	"Salary Component": HRMS / "payroll/doctype/salary_component/salary_component.json",
}


def thai_fields(doctype):
	"""{fieldname: DocField} of the Thailand fields of `doctype` and the field_order of its JSON."""
	document = json.loads(JSON_OF[doctype].read_text())
	by_name = {f["fieldname"]: f for f in document["fields"]}
	return {name: by_name[name] for name in THAI_FIELDS[doctype]}, document["field_order"]


class TestThailandFieldLayout(TestCase):
	def test_every_field_is_in_the_doctype_json_once_and_the_installer_makes_none(self):
		for doctype, names in THAI_FIELDS.items():
			fields, order = thai_fields(doctype)
			self.assertEqual(set(fields), set(names), doctype)
			for name in names:
				self.assertEqual(order.count(name), 1, f"{doctype}.{name}")
		self.assertFalse(hasattr(constants, "HRMS_THAILAND_CUSTOM_FIELDS"))
		self.assertFalse(hasattr(thai_setup, "make_custom_fields"))

	def test_each_section_has_a_label_and_two_columns_at_most(self):
		for doctype in THAI_FIELDS:
			fields, order = thai_fields(doctype)
			columns = 0
			for name in order:
				field = fields.get(name)
				if not field:
					continue
				if field["fieldtype"] == "Section Break":
					self.assertTrue(field["label"], doctype)
					columns = 1
				elif field["fieldtype"] == "Column Break":
					columns += 1
					self.assertLessEqual(columns, 2, doctype)

	def test_the_national_id_and_social_security_id_are_payroll_private(self):
		fields, _ = thai_fields("Employee")
		for name in ("national_id_number", "social_security_id"):
			self.assertEqual(fields[name]["permlevel"], constants.PAYROLL_PERMLEVEL)
		self.assertNotIn("permlevel", fields["social_security_eligible"])

	def test_the_provident_fund_rates_are_on_the_assignment_and_nowhere_else(self):
		assignment, _ = thai_fields("Salary Structure Assignment")
		self.assertIn("provident_fund_rate", assignment)
		self.assertIn("provident_fund_employer_rate", assignment)
		self.assertNotIn("provident_fund_rate", thai_fields("Employee")[0])

	def test_the_statutory_types_are_the_select_options(self):
		field = thai_fields("Salary Component")[0]["thai_statutory_type"]
		self.assertEqual(field["options"].split("\n")[1:], list(constants.STATUTORY_TYPES))


class TestExpenseClaimTaxInvoiceFields(TestCase):
	"""The Thailand fields of Expense Claim were Custom Fields of the ERPNext fork; they are in its JSON now."""

	def test_the_claim_has_the_tax_invoice_link_fields(self):
		document = json.loads((HRMS / "hr/doctype/expense_claim/expense_claim.json").read_text())
		fields = {f["fieldname"]: f for f in document["fields"]}
		self.assertEqual(fields["tax_invoice_ref"]["options"], "tax_invoice_ref_type")
		self.assertEqual(fields["tax_invoice_ref"]["fieldtype"], "Dynamic Link")
		self.assertEqual(fields["tax_invoice_ref_type"]["hidden"], 1)
		for name in ("tax_invoice", "tax_invoice_number", "tax_invoice_date", "company_tax_address"):
			self.assertIn(name, document["field_order"])


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
			patch("builtins.print"),
		):
			move_rates.execute()
		return frappe_mock

	def test_the_rate_goes_to_the_assignment_in_force_and_the_employee_fields_are_removed(self):
		members = [row(name="6511003", provident_fund_rate=5, provident_fund_employer_rate=0)]
		assignments = {
			"6511003": [
				row(name="SSA-NEW", from_date="2027-01-01", provident_fund_rate=0),
				row(name="SSA-NOW", from_date="2026-01-01", provident_fund_rate=0),
			]
		}
		frappe_mock = self.run_patch(members, assignments)
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
		frappe_mock = self.run_patch(members, assignments)
		frappe_mock.db.set_value.assert_not_called()
		frappe_mock.log_error.assert_not_called()

	def test_a_rate_with_no_assignment_is_logged_before_the_field_goes(self):
		members = [row(name="6511003", provident_fund_rate=5, provident_fund_employer_rate=0)]
		frappe_mock = self.run_patch(members, {"6511003": []})
		frappe_mock.db.set_value.assert_not_called()
		self.assertIn("6511003", frappe_mock.log_error.call_args.kwargs["message"])
		self.assertTrue(frappe_mock.delete_doc.called)

	def test_a_site_without_the_employee_columns_copies_nothing(self):
		frappe_mock = self.run_patch([], {}, columns=())
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
		db.get_value.return_value = None
		frappe_mock = Mock(db=db, get_all=Mock(return_value=["6810001", "6810007", "6910002", "C6707001"]))
		with (
			patch.object(use_series, "frappe", frappe_mock),
			patch.object(use_series, "make_property_setters") as setters,
		):
			use_series.execute()
		setters.assert_called_once()
		calls = [(c.args[0], c.args[1]) for c in db.sql.call_args_list]
		self.assertIn("update `tabEmployee` set naming_series", calls[0][0])
		self.assertEqual(calls[0][1][0], constants.EMPLOYEE_SERIES)

	def test_the_counter_of_each_month_is_set_to_the_highest_number_that_exists(self):
		names = ["6810001", "6810007", "6910002", "C6707001", "CD-EMP-0059", "DUMMY-01"]
		self.assertEqual(use_series.highest_numbers(names), {"6810": 7, "6910": 2})

	def test_a_counter_is_raised_and_never_lowered(self):
		db = Mock()
		with patch.object(use_series, "frappe", Mock(db=db)):
			db.get_value.return_value = 3
			use_series.raise_counter("6810", 7)
			self.assertIn("update `tabSeries`", db.sql.call_args.args[0])
			db.sql.reset_mock()
			db.get_value.return_value = 9
			use_series.raise_counter("6810", 7)
			db.sql.assert_not_called()
			db.get_value.return_value = None
			use_series.raise_counter("6910", 2)
			self.assertIn("insert into `tabSeries`", db.sql.call_args.args[0])


class TestEmployeeNameLayout(TestCase):
	def test_the_thai_name_block_comes_before_the_english_one_and_the_basics_after(self):
		order = field_order(ERPNEXT / "setup/doctype/employee/employee.json")
		thai = ["naming_series", "salutation", "first_name", "middle_name", "last_name", "employee_name"]
		self.assertEqual([order.index(f) for f in thai], sorted(order.index(f) for f in thai))
		self.assertNotIn("column_break1", order)
		english = ["column_break_name_en", "salutation_en", "first_name_en", "middle_name_en", "last_name_en"]
		start = order.index("column_break_name_en")
		self.assertEqual(order[start : start + 6], [*english, "full_name_en"])
		self.assertLess(order.index("employee_name"), start)
		self.assertLess(order.index("employee_name"), order.index("column_break_9"))
		self.assertLess(order.index("column_break_9"), order.index("gender"))
		self.assertLess(order.index("date_of_birth"), order.index("date_of_joining"))
		self.assertLess(order.index("date_of_joining"), order.index("status"))

	def test_the_signature_is_shown_and_made_with_a_button(self):
		fields, order = thai_fields("Employee")
		self.assertEqual(fields["sign_button"]["fieldtype"], "Button")
		self.assertEqual(order[order.index("sign_button") - 1], "signature")
		self.assertIn(("Employee", "signature", "read_only", 1, "Check"), constants.PROPERTY_SETTERS)
		self.assertIn("public/js/thailand/employee.js", hooks.doctype_js["Employee"])


class TestMigrateWritesSchemaOnly(TestCase):
	"""A migrate adds what is missing; it never overwrites a field and never gives the payroll rights again."""

	def setUp(self):
		from hrms.regional.thailand import setup as thai_setup

		self.setup = thai_setup
		patches = [
			patch.object(thai_setup, "make_property_setter"),
			patch.object(thai_setup, "add_permission"),
			patch.object(thai_setup, "update_permission_property"),
			patch.object(thai_setup, "make_salutations"),
			patch.object(frappe, "clear_cache"),
			patch.object(frappe, "db", Mock(exists=Mock(return_value=False))),
		]
		self.mocks = [item.start() for item in patches]
		for item in patches:
			self.addCleanup(item.stop)
		(self.make_setter, self.add_permission, self.update_permission) = self.mocks[:3]

	def test_a_migrate_makes_no_field_and_gives_no_rights(self):
		self.setup.after_migrate()
		self.assertFalse(hasattr(self.setup, "create_custom_fields"))
		self.add_permission.assert_not_called()
		self.update_permission.assert_not_called()

	def test_a_property_the_site_has_is_not_written_again_by_a_migrate(self):
		frappe.db.exists.return_value = True
		self.setup.after_migrate()
		self.make_setter.assert_not_called()
		frappe.db.exists.return_value = False
		self.setup.after_migrate()
		self.assertEqual(self.make_setter.call_count, len(constants.PROPERTY_SETTERS))

	def test_the_patch_still_writes_the_series_over_a_site_value(self):
		frappe.db.exists.return_value = True
		self.setup.make_property_setters()
		self.assertEqual(self.make_setter.call_count, len(constants.PROPERTY_SETTERS))

	def test_the_rights_are_given_once_at_install(self):
		self.setup.after_install()
		self.assertEqual(self.add_permission.call_count, len(constants.PAYROLL_ROLES))
		self.assertEqual(self.update_permission.call_count, 2 * len(constants.PAYROLL_ROLES))

	def test_the_hooks_run_the_migrate_and_install_entry_points(self):
		self.assertIn("hrms.regional.thailand.setup.after_migrate", hooks.after_migrate)
		from hrms import install

		self.assertIs(install.setup_thailand, self.setup.after_install)
