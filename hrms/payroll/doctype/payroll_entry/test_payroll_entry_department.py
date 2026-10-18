# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Payroll books the cost of each Department on its own Journal Entry row."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry

MODULE = "hrms.payroll.doctype.payroll_entry.payroll_entry."


class Entry(SimpleNamespace):
	"""Borrows the real methods that group and book payroll rows."""

	get_salary_component_total = PayrollEntry.get_salary_component_total
	get_account = PayrollEntry.get_account
	get_payable_amount_for_earnings_and_deductions = PayrollEntry.get_payable_amount_for_earnings_and_deductions
	get_accounting_entries_and_payable_amount = PayrollEntry.get_accounting_entries_and_payable_amount
	get_amount_and_exchange_rate_for_journal_entry = PayrollEntry.get_amount_and_exchange_rate_for_journal_entry
	update_accounting_dimensions = PayrollEntry.update_accounting_dimensions
	make_employer_contribution_jv_entry = PayrollEntry.make_employer_contribution_jv_entry

	def get(self, key, default=None):
		return getattr(self, key, default)


class TestPayrollEntryDepartment(unittest.TestCase):
	def entry(self, slip_rows):
		entry = Entry(
			project=None,
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
			get_salary_component_account=lambda component: {"Basic": "Salary", "Bonus": "Salary", "Tax": "Tax Payable"}[
				component
			],
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
				{"salary_component": "Basic", "amount": 100, "employee": "E1", "department": "Lab", "additional_salary": None},
				{"salary_component": "Bonus", "amount": 20, "employee": "E1", "department": "Lab", "additional_salary": None},
				{"salary_component": "Basic", "amount": 70, "employee": "E2", "department": "Sales", "additional_salary": None},
				{"salary_component": "Basic", "amount": 50, "employee": "E3", "department": None, "additional_salary": None},
			]
		)
		totals = entry.get_salary_component_total("earnings")
		self.assertEqual(totals, {("Salary", "Lab"): 120, ("Salary", "Sales"): 70, ("Salary", None): 50})

	def test_expense_rows_carry_their_department(self):
		entry = self.entry([])
		accounts, currencies = [], []
		entry.get_payable_amount_for_earnings_and_deductions(
			accounts,
			{("Salary", "Lab"): 120, ("Salary", None): 50},
			{("Tax Payable", "Lab"): 12},
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
		self.assertNotIn("department", next(row for row in accounts if row["account"] == "Salary" and row.get("department") is None))

	def test_employer_contribution_expense_is_split_by_department_but_liability_is_not(self):
		entry = self.entry([])
		booked = {}
		entry.get_employer_contribution_accounts = lambda components: {"Fund": ("Fund Expense", "Fund Liability")}
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
		expense = {row.get("department"): row["debit_in_account_currency"] for row in accounts if row["account"] == "Fund Expense"}
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
