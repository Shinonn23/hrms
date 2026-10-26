# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Payroll books the cost of each Department on its own Journal Entry row (within each cost center)."""

import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import flt

from hrms.payroll.doctype.payroll_entry.payroll_entry import (
	PayrollEntry,
	create_salary_slips_for_employees,
	delete_draft_salary_slips,
)

MODULE = "hrms.payroll.doctype.payroll_entry.payroll_entry."


class Entry(SimpleNamespace):
	"""Borrows the real methods that group and book payroll rows."""

	get_salary_component_total = PayrollEntry.get_salary_component_total
	get_account = PayrollEntry.get_account
	get_payable_amount_for_earnings_and_deductions = (
		PayrollEntry.get_payable_amount_for_earnings_and_deductions
	)
	get_accounting_entries_and_payable_amount = PayrollEntry.get_accounting_entries_and_payable_amount
	get_amount_and_exchange_rate_for_journal_entry = (
		PayrollEntry.get_amount_and_exchange_rate_for_journal_entry
	)
	update_accounting_dimensions = PayrollEntry.update_accounting_dimensions
	make_employer_contribution_jv_entry = PayrollEntry.make_employer_contribution_jv_entry
	set_payable_amount_against_payroll_payable_account = (
		PayrollEntry.set_payable_amount_against_payroll_payable_account
	)
	set_accounting_entries_for_advance_deductions = PayrollEntry.set_accounting_entries_for_advance_deductions
	add_advance_deduction_entry = PayrollEntry.add_advance_deduction_entry
	set_employee_based_payroll_payable_entries = PayrollEntry.set_employee_based_payroll_payable_entries
	process_loan_repayments_for_bank_entry = PayrollEntry.process_loan_repayments_for_bank_entry
	set_accounting_entries_for_bank_entry = PayrollEntry.set_accounting_entries_for_bank_entry
	make_bank_entry = PayrollEntry.make_bank_entry
	create_salary_slips = PayrollEntry.create_salary_slips
	validate_recalculation_allowed = PayrollEntry.validate_recalculation_allowed

	def get(self, key, default=None):
		return getattr(self, key, default)


class TestPayrollEntryDepartment(unittest.TestCase):
	def entry(self, slip_rows):
		entry = Entry(
			project=None,
			cost_center="Main",
			exchange_rate=1,
			company="Company",
			start_date="2026-10-01",
			end_date="2026-10-31",
			doctype="Payroll Entry",
			name="PE-1",
			employee_based_payroll_payable_entries={},
			_advance_deduction_entries=[],
			get_salary_components=lambda component_type: [frappe._dict(row) for row in slip_rows],
			get_advance_deductions=lambda component_type, rows: {},
			get_payroll_cost_centers_for_employee=lambda employee, salary_structure: {"Main": 100},
			get_salary_component_account=lambda component: {
				"Basic": "Salary",
				"Bonus": "Salary",
				"Tax": "Tax Payable",
			}[component],
		)
		for patcher in (
			patch.object(frappe, "db", new=MagicMock(**{"get_value.return_value": "THB"})),
			patch.object(frappe, "get_cached_value", return_value="THB"),
			patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"),
			patch(MODULE + "_", new=lambda text: text),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		return entry

	def test_components_are_totalled_per_account_and_department(self):
		entry = self.entry(
			[
				{
					"salary_component": "Basic",
					"amount": 100,
					"employee": "E1",
					"department": "Lab",
					"additional_salary": None,
				},
				{
					"salary_component": "Bonus",
					"amount": 20,
					"employee": "E1",
					"department": "Lab",
					"additional_salary": None,
				},
				{
					"salary_component": "Basic",
					"amount": 70,
					"employee": "E2",
					"department": "Sales",
					"additional_salary": None,
				},
				{
					"salary_component": "Basic",
					"amount": 50,
					"employee": "E3",
					"department": None,
					"additional_salary": None,
				},
			]
		)
		totals = entry.get_salary_component_total("earnings")
		self.assertEqual(
			totals,
			{("Salary", "Main", "Lab"): 120, ("Salary", "Main", "Sales"): 70, ("Salary", "Main", None): 50},
		)

	def test_expense_rows_carry_their_department(self):
		entry = self.entry([])
		accounts, currencies = [], []
		entry.get_payable_amount_for_earnings_and_deductions(
			accounts,
			{("Salary", "Main", "Lab"): 120, ("Salary", "Main", None): 50},
			{("Tax Payable", "Main", "Lab"): 12},
			currencies,
			"THB",
			[],
			2,
			0,
			False,
		)
		rows = {(row["account"], row.get("department")): row for row in accounts}
		self.assertEqual(rows[("Salary", "Lab")]["debit_in_account_currency"], 120)
		self.assertEqual(rows[("Salary", None)]["debit_in_account_currency"], 50)
		self.assertEqual(rows[("Tax Payable", "Lab")]["credit_in_account_currency"], 12)
		self.assertNotIn(
			"department",
			next(row for row in accounts if row["account"] == "Salary" and row.get("department") is None),
		)

	def test_employer_contribution_expense_is_split_by_department_but_liability_is_not(self):
		entry = self.entry([])
		booked = {}
		entry.get_employer_contribution_accounts = lambda components: {
			"Fund": ("Fund Expense", "Fund Liability")
		}
		entry.make_journal_entry = lambda accounts, *args, **kwargs: booked.setdefault("accounts", accounts)
		contributions = [
			frappe._dict(salary_component="Fund", amount=10, employee="E1", department="Lab"),
			frappe._dict(salary_component="Fund", amount=6, employee="E2", department="Lab"),
			frappe._dict(salary_component="Fund", amount=4, employee="E3", department="Sales"),
		]
		with (
			patch(MODULE + "get_accounting_dimensions", return_value=[]),
			patch(MODULE + "erpnext.get_company_currency", return_value="THB"),
			patch.object(frappe, "get_precision", return_value=2),
		):
			entry.make_employer_contribution_jv_entry(contributions)
		accounts = booked["accounts"]
		expense = {
			row.get("department"): row["debit_in_account_currency"]
			for row in accounts
			if row["account"] == "Fund Expense"
		}
		self.assertEqual(expense, {"Lab": 16, "Sales": 4})
		liability = [row for row in accounts if row["account"] == "Fund Liability"]
		self.assertEqual(sum(row["credit_in_account_currency"] for row in liability), 20)
		self.assertTrue(all("department" not in row for row in liability))

	def test_the_slips_department_is_not_replaced_by_a_department_accounting_dimension(self):
		entry = self.entry([])
		entry.department = "Payroll Entry filter"
		accounts = []
		entry.get_accounting_entries_and_payable_amount(
			"Salary",
			"Main",
			100,
			[],
			"THB",
			0,
			["department"],
			2,
			entry_type="debit",
			accounts=accounts,
			department="Lab",
		)
		self.assertEqual(accounts[0]["department"], "Lab")


def totals(rows):
	debit = round(sum(row.get("debit_in_account_currency", 0) for row in rows), 2)
	credit = round(sum(row.get("credit_in_account_currency", 0) for row in rows), 2)
	return debit, credit


def net(rows, department, skip_account):
	"""Debits less credits of the department's rows other than the payable rows themselves"""
	return round(
		sum(
			row.get("debit_in_account_currency", 0) - row.get("credit_in_account_currency", 0)
			for row in rows
			if row.get("department") == department and row["account"] != skip_account
		),
		2,
	)


class TestPayrollEntryDepartmentPayable(unittest.TestCase):
	entry = TestPayrollEntryDepartment.entry

	def accrual(self, entry, employee_wise):
		accounts, currencies, payable_by_department = [], [], {}
		earnings = {
			("Salary", "Main", "Lab"): 100.01,
			("Salary", "Main", "Sales"): 70.03,
			("Salary", "Main", None): 50.5,
		}
		deductions = {("Tax Payable", "Main", "Lab"): 10.005, ("Tax Payable", "Main", "Sales"): 3.33}
		payable = entry.get_payable_amount_for_earnings_and_deductions(
			accounts, earnings, deductions, currencies, "THB", [], 2, 0, employee_wise, payable_by_department
		)
		entry._advance_deduction_entries = [
			{
				"employee": "E1",
				"account": "Advance",
				"amount": 5.55,
				"cost_center": "Main",
				"department": "Lab",
				"reference_name": "ADV-1",
			}
		]
		payable = entry.set_accounting_entries_for_advance_deductions(
			accounts, currencies, "THB", [], 2, payable, payable_by_department
		)
		return accounts, currencies, payable, payable_by_department

	def payable_entry(self):
		entry = self.entry([])
		entry.payroll_payable_account = "Payroll Payable"
		entry.project = None
		return entry

	def test_payable_is_split_per_department_and_balances(self):
		entry = self.payable_entry()
		accounts, currencies, payable, by_department = self.accrual(entry, False)
		entry.set_payable_amount_against_payroll_payable_account(
			accounts, currencies, "THB", [], 2, payable, "Payroll Payable", False, by_department
		)
		payable_rows = [row for row in accounts if row["account"] == "Payroll Payable"]
		self.assertEqual({row.get("department") for row in payable_rows}, {"Lab", "Sales", None})
		for row in payable_rows:
			department = row.get("department")
			self.assertEqual(row["credit_in_account_currency"], net(accounts, department, "Payroll Payable"))
		debit, credit = totals(accounts)
		self.assertEqual(debit, credit)

	def test_advance_credit_rows_carry_the_department(self):
		entry = self.payable_entry()
		accounts, *_ = self.accrual(entry, False)
		advance = next(row for row in accounts if row["account"] == "Advance")
		self.assertEqual(advance["department"], "Lab")
		self.assertEqual(advance["reference_type"], "Employee Advance")

	def test_advance_entry_remembers_the_slip_department(self):
		entry = self.entry([])
		item = frappe._dict(employee="E1", department="Lab")
		entry.add_advance_deduction_entry(
			item, 5, "Main", frappe._dict(advance_account="Adv", employee_advance="A")
		)
		self.assertEqual(entry._advance_deduction_entries[0]["department"], "Lab")

	def test_employee_wise_payable_rows_carry_the_department(self):
		entry = self.payable_entry()
		entry.employee_based_payroll_payable_entries = {}
		entry.set_employee_based_payroll_payable_entries("earnings", "E1", 100, department="Lab")
		entry.set_employee_based_payroll_payable_entries("deductions", "E1", 10, department="Lab")
		entry.set_employee_based_payroll_payable_entries("earnings", "E2", 50)
		accounts, currencies = [], []
		entry.set_payable_amount_against_payroll_payable_account(
			accounts, currencies, "THB", [], 2, 0, "Payroll Payable", True, {}
		)
		rows = {row["party"]: row for row in accounts}
		self.assertEqual(rows["E1"]["department"], "Lab")
		self.assertEqual(rows["E1"]["credit_in_account_currency"], 90)
		self.assertNotIn("department", rows["E2"])


class TestPayrollEntryDepartmentBank(unittest.TestCase):
	entry = TestPayrollEntryDepartment.entry

	def bank_entry(self, **extra):
		entry = self.entry([])
		entry.payment_account = "Bank"
		entry.bank_account = None
		entry.payroll_payable_account = "Payroll Payable"
		entry.department = None
		entry.project = None
		entry.docstatus = 1
		entry.booked = {}

		def make_journal_entry(accounts, *args, **kwargs):
			entry.booked["accounts"] = accounts
			return SimpleNamespace(name="ACC-JV-1")

		entry.make_journal_entry = make_journal_entry
		for key, value in extra.items():
			setattr(entry, key, value)
		for patcher in (
			patch(MODULE + "get_accounting_dimensions", return_value=extra.pop("dimensions", [])),
			patch(MODULE + "erpnext.get_company_currency", return_value="THB"),
			patch.object(frappe, "get_precision", return_value=2),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		return entry

	def test_employee_wise_payable_debits_carry_the_department_and_balance(self):
		entry = self.bank_entry(
			employee_based_payroll_payable_entries={
				"E1": {"earnings": 100.01, "deductions": 10.02, "department": "Lab", "salary_structure": "S"},
				"E2": {"earnings": 70.03, "deductions": 0, "salary_structure": "S"},
			},
			get_payroll_cost_centers_for_employee=lambda employee, structure: {"A": 33.33, "B": 66.67},
		)
		entry.set_accounting_entries_for_bank_entry(160.02, "salaries", True)
		accounts = entry.booked["accounts"]
		debit_rows = [row for row in accounts if row["account"] == "Payroll Payable"]
		self.assertEqual({row["department"] for row in debit_rows if row["party"] == "E1"}, {"Lab"})
		self.assertTrue(all("department" not in row for row in debit_rows if row["party"] == "E2"))
		bank = next(row for row in accounts if row["account"] == "Bank")
		self.assertNotIn("department", bank)
		debit, credit = totals(accounts)
		self.assertEqual(debit, credit)

	def test_aggregate_payable_debit_is_split_per_department(self):
		entry = self.bank_entry(employee_based_payroll_payable_entries={})
		entry.set_accounting_entries_for_bank_entry(
			190.05, "salaries", False, {"Lab": 100.01, "Sales": 70.03, None: 20.01}
		)
		accounts = entry.booked["accounts"]
		debit_rows = [row for row in accounts if row["account"] == "Payroll Payable"]
		self.assertEqual({row.get("department") for row in debit_rows}, {"Lab", "Sales", None})
		self.assertEqual(
			next(r for r in debit_rows if r.get("department") == "Lab")["debit_in_account_currency"], 100.01
		)
		debit, credit = totals(accounts)
		self.assertEqual(debit, credit)
		self.assertEqual(credit, 190.05)

	def test_a_negative_department_net_becomes_a_credit_row(self):
		entry = self.bank_entry(employee_based_payroll_payable_entries={})
		entry.set_accounting_entries_for_bank_entry(95.01, "salaries", False, {"Lab": 100.01, "Sales": -5})
		accounts = entry.booked["accounts"]
		sales = next(row for row in accounts if row.get("department") == "Sales")
		self.assertEqual(sales["credit_in_account_currency"], 5)
		debit, credit = totals(accounts)
		self.assertEqual(debit, credit)

	def test_a_foreign_currency_payable_keeps_a_single_row_that_balances_as_erpnext_computes_it(self):
		entry = self.bank_entry(employee_based_payroll_payable_entries={}, exchange_rate=1.5)
		db = MagicMock()
		db.get_value.side_effect = lambda doctype, name, field, **kwargs: "USD"
		with patch.object(frappe, "db", new=db):
			entry.set_accounting_entries_for_bank_entry(
				20.02, "salaries", False, {"Lab": 10.01, "Sales": 10.01}
			)
		accounts = entry.booked["accounts"]
		self.assertEqual(len([row for row in accounts if row["account"] == "Payroll Payable"]), 1)

		def company(side):
			return round(sum(flt(row.get(side, 0) * row["exchange_rate"], 2) for row in accounts), 2)

		self.assertEqual(company("debit_in_account_currency"), company("credit_in_account_currency"))

	def test_bank_credit_row_takes_the_payroll_entry_department(self):
		entry = self.bank_entry(employee_based_payroll_payable_entries={}, department="HR")
		entry.set_accounting_entries_for_bank_entry(10, "salaries", False, {"Lab": 10})
		bank = next(row for row in entry.booked["accounts"] if row["account"] == "Bank")
		self.assertEqual(bank["department"], "HR")

	def test_bank_rows_leave_a_custom_dimension_untouched(self):
		entry = self.bank_entry(
			employee_based_payroll_payable_entries={},
			uat_department="UAT-1",
			dimensions=["uat_department"],
		)
		entry.set_accounting_entries_for_bank_entry(10, "salaries", False, {"Lab": 10})
		accounts = entry.booked["accounts"]
		self.assertTrue(all(row["uat_department"] == "UAT-1" for row in accounts))
		self.assertEqual(next(r for r in accounts if r["account"] == "Payroll Payable")["department"], "Lab")

	def make_bank_entry(self, withheld, employee_wise):
		entry = self.bank_entry(employee_based_payroll_payable_entries={})

		def slip(employee, department, component, parentfield, amount):
			return frappe._dict(
				employee=employee,
				department=department,
				salary_structure="S",
				salary_component=component,
				parentfield=parentfield,
				amount=amount,
			)

		entry.get_salary_slip_details = lambda for_withheld: [
			slip("E1", "Lab", "Basic", "earnings", 100.01),
			slip("E1", "Lab", "Tax", "deductions", 10.02),
			slip("E2", "Sales", "Basic", "earnings", 70.03),
		]
		entry.get_payroll_cost_centers_for_employee = lambda employee, structure: {"A": 33.33, "B": 66.67}
		entry.check_permission = lambda permission: None
		db = MagicMock()
		db.get_value.side_effect = lambda doctype, name, field, **kwargs: {
			"docstatus": 1,
			"account_currency": "THB",
		}.get(field, 0)
		db.get_single_value.return_value = employee_wise
		with (
			patch.object(frappe, "db", new=db),
			patch.object(frappe, "get_installed_apps", return_value=[]),
			patch(MODULE + "link_bank_entry_in_salary_withholdings") as link,
		):
			entry.make_bank_entry(for_withheld_salaries=withheld)
		return entry.booked["accounts"], link

	def test_bank_entry_rows_carry_the_department_for_both_accounting_modes(self):
		for employee_wise in (1, 0):
			accounts, _ = self.make_bank_entry(False, employee_wise)
			debit_rows = [row for row in accounts if row["account"] == "Payroll Payable"]
			self.assertEqual({row.get("department") for row in debit_rows}, {"Lab", "Sales"})
			debit, credit = totals(accounts)
			self.assertEqual(debit, credit)
			self.assertEqual(credit, 160.02)

	def test_withheld_release_rows_carry_the_department(self):
		accounts, link = self.make_bank_entry(True, 0)
		link.assert_called_once()
		self.assertEqual(
			{row.get("department") for row in accounts if row["account"] == "Payroll Payable"},
			{"Lab", "Sales"},
		)


class TestPayrollEntryRecalculation(unittest.TestCase):
	SLIPS: ClassVar[list] = [
		{"name": "SS-DRAFT", "docstatus": 0, "payroll_entry": "PE-1"},
		{"name": "SS-CORRECTED", "docstatus": 0, "payroll_entry": "PE-1"},
		{"name": "SS-SUBMITTED", "docstatus": 1, "payroll_entry": "PE-1"},
		{"name": "SS-CANCELLED", "docstatus": 2, "payroll_entry": "PE-1"},
		{"name": "SS-OTHER", "docstatus": 0, "payroll_entry": "PE-2"},
	]

	def delete(self, entry_docstatus=0):
		def get_all(doctype, filters=None, pluck=None):
			return [
				slip["name"]
				for slip in self.SLIPS
				if all(slip[key] == value for key, value in filters.items())
			]

		deleted = []
		with (
			patch.object(frappe, "get_all", side_effect=get_all),
			patch.object(frappe, "db", new=MagicMock(**{"get_value.return_value": entry_docstatus})) as db,
			patch.object(frappe, "delete_doc", side_effect=lambda doctype, name: deleted.append(name)),
		):
			db.exists.side_effect = (
				lambda doctype, filters: filters["salary_slip_reference"] == "SS-CORRECTED"
			)
			result = delete_draft_salary_slips("PE-1")
		return result, deleted

	def test_only_plain_draft_slips_of_the_entry_are_deleted(self):
		result, deleted = self.delete()
		self.assertEqual(deleted, ["SS-DRAFT"])
		self.assertEqual(result, ["SS-DRAFT"])

	def test_a_submitted_payroll_entry_keeps_every_slip(self):
		self.assertEqual(self.delete(entry_docstatus=1), ([], []))

	def test_recalculation_deletes_before_creating_and_plain_create_does_not(self):
		for recalculate in (True, False):
			calls = []
			args = frappe._dict(
				payroll_entry="PE-1", company="C", start_date="2026-10-01", end_date="2026-10-31"
			)
			entry = SimpleNamespace(docstatus=0, db_set=lambda *a, **k: None)
			with (
				patch.object(frappe, "get_cached_doc", return_value=entry),
				patch.object(frappe, "publish_realtime"),
				patch.object(frappe, "session", new=SimpleNamespace(user="Administrator")),
				patch.object(frappe, "in_test", True, create=True),
				patch(MODULE + "delete_draft_salary_slips", side_effect=lambda name: calls.append("delete")),
				patch(
					MODULE + "get_existing_salary_slips",
					side_effect=lambda *a: calls.append("existing") or [],
				),
				patch.object(
					frappe,
					"get_doc",
					side_effect=lambda doc: MagicMock(insert=lambda: calls.append("insert")),
				),
			):
				create_salary_slips_for_employees(
					["E1"], args, publish_progress=False, recalculate=recalculate
				)
			self.assertEqual(calls, (["delete"] if recalculate else []) + ["existing", "insert"])

	def test_a_large_recalculation_is_deleted_inside_the_queued_job(self):
		entry = Entry(
			employees=[SimpleNamespace(employee=f"E{i}") for i in range(31)],
			salary_slip_based_on_timesheet=0,
			payroll_frequency="Monthly",
			start_date="2026-10-01",
			end_date="2026-10-31",
			company="C",
			posting_date="2026-10-31",
			deduct_tax_for_unsubmitted_tax_exemption_proof=0,
			name="PE-1",
			docstatus=0,
			doctype="Payroll Entry",
			exchange_rate=1,
			currency="THB",
			check_permission=lambda permission: None,
			db_set=lambda *a, **k: None,
		)
		with (
			patch.object(frappe, "enqueue") as enqueue,
			patch.object(frappe, "msgprint"),
			patch(MODULE + "get_workflow_name", return_value=None),
			patch.object(frappe, "get_hooks", return_value=[]),
			patch(MODULE + "delete_draft_salary_slips") as delete,
		):
			entry.create_salary_slips(recalculate="1")
		self.assertTrue(enqueue.call_args.kwargs["recalculate"])
		delete.assert_not_called()


class TestPayrollEntryRecalculationGuard(unittest.TestCase):
	def attempt(self, workflow_state):
		entry = Entry(
			docstatus=0,
			doctype="Payroll Entry",
			name="PE-1",
			workflow_state=workflow_state,
			employees=[SimpleNamespace(employee="E1")],
			check_permission=lambda permission: None,
			db_set=MagicMock(),
		)
		db = MagicMock()
		db.get_value.return_value = "Approver"
		with (
			patch.object(frappe, "db", new=db),
			patch.object(frappe, "session", new=SimpleNamespace(user="planner@example.com")),
			patch.object(frappe, "get_roles", return_value=["Planner"]),
			patch.object(frappe, "get_hooks", return_value=[]),
			patch.object(frappe, "throw", side_effect=frappe.ValidationError),
			patch.object(frappe, "bold", new=lambda text: text),
			patch(MODULE + "_", new=lambda text: text),
			patch(MODULE + "get_workflow_name", return_value="Payroll Workflow"),
			patch(MODULE + "delete_draft_salary_slips") as delete,
			patch(MODULE + "create_salary_slips_for_employees") as create,
			patch.object(frappe, "enqueue") as enqueue,
		):
			with self.assertRaises(frappe.ValidationError):
				entry.create_salary_slips(recalculate=True)
		return entry, delete, create, enqueue

	def test_recalculation_in_a_state_the_user_cannot_edit_does_nothing(self):
		entry, delete, create, enqueue = self.attempt("Plan Pending Approval")
		delete.assert_not_called()
		create.assert_not_called()
		enqueue.assert_not_called()
		entry.db_set.assert_not_called()
