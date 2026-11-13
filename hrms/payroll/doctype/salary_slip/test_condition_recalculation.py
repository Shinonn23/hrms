from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class TestConditionRecalculation(TestCase):
	def test_false_condition_removes_stale_structure_row_but_keeps_additional_salary(self):
		structure_row = SimpleNamespace(salary_component="Fund", additional_salary=None)
		additional_row = SimpleNamespace(salary_component="Fund", additional_salary="ADDITIONAL-1")
		slip = Mock(salary_slip_based_on_timesheet=False, data={"FUND": 55}, default_data={"FUND": 55})
		slip.eval_condition_and_formula.return_value = None
		slip.get.return_value = [structure_row, additional_row]
		row = SimpleNamespace(salary_component="Fund", abbr="FUND")
		SalarySlip.add_structure_component(slip, row, "deductions")
		slip.set.assert_called_once_with("deductions", [additional_row])
		self.assertEqual(slip.data["FUND"], 0)
		self.assertEqual(slip.default_data["FUND"], 0)
