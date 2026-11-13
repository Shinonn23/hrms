from unittest import TestCase
from unittest.mock import patch

import frappe

from hrms.payroll.utils import employee_welfare_fund_base


class TestEmployeeWelfareFund(TestCase):
	def test_selected_earnings_use_actual_or_full_cycle_amount(self):
		rows = [
			frappe._dict(salary_component="Salary", amount=8000, default_amount=10000),
			frappe._dict(salary_component="Travel", amount=500, default_amount=500),
			frappe._dict(salary_component="Bonus", amount=2000, default_amount=2000),
		]
		with patch.object(frappe, "get_cached_value", side_effect=lambda dt, name, field: name != "Travel"):
			self.assertEqual(employee_welfare_fund_base(rows, "amount"), 10000)
			self.assertEqual(employee_welfare_fund_base(rows, "default_amount"), 12000)
			rows[2].statistical_component = 1
			self.assertEqual(employee_welfare_fund_base(rows, "amount"), 8000)
