# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import ShiftAssignmentTool
from hrms.hr.doctype.shift_schedule.shift_schedule import get_or_insert_shift_schedule
from hrms.hr.doctype.shift_type.test_shift_type import make_shift_assignment, setup_shift_type
from hrms.tests.test_utils import create_company
from hrms.tests.utils import HRMSTestSuite


class TestShiftAssignmentTool(HRMSTestSuite):
	def setUp(self):
		create_company()
		create_company("_Test Company2")
		self.shift1 = setup_shift_type(shift_type="Shift 1", start_time="08:00:00", end_time="12:00:00")
		self.shift2 = setup_shift_type(shift_type="Shift 2", start_time="11:00:00", end_time="15:00:00")
		self.shift3 = setup_shift_type(shift_type="Shift 3", start_time="14:00:00", end_time="18:00:00")
		self.schedule1 = get_or_insert_shift_schedule(self.shift1.name, "Every Week", ["Monday"])
		self.schedule2 = get_or_insert_shift_schedule(self.shift2.name, "Every Week", ["Monday"])
		self.schedule3 = get_or_insert_shift_schedule(self.shift3.name, "Every Week", ["Monday"])
		self.schedule4 = get_or_insert_shift_schedule(self.shift1.name, "Every Week", ["Tuesday"])
		self.emp1 = make_employee("employee1@test.com", company="_Test Company")
		self.emp2 = make_employee("employee2@test.com", company="_Test Company")
		self.emp3 = make_employee("employee3@test.com", company="_Test Company")
		self.emp4 = make_employee("employee4@test.com", company="_Test Company2")
		self.emp5 = make_employee("employee5@test.io", company="_Test Company")

	@HRMSTestSuite.change_settings("HR Settings", {"allow_multiple_shift_assignments": 0})
	def test_get_employees_for_assigning_shifts(self):
		today = getdate()

		args = {
			"doctype": "Shift Assignment Tool",
			"action": "Assign Shift",
			"company": "_Test Company",  # excludes emp4
			"shift_type": self.shift1.name,
			"status": "Active",
			"start_date": today,
		}
		shift_assignment_tool = ShiftAssignmentTool(args)
		advanced_filters = [["name", "in", [self.emp1, self.emp2, self.emp3]]]

		# does not exclude emp1 as dates don't overlap
		make_shift_assignment(self.shift3.name, self.emp1, add_days(today, -5), add_days(today, -1))
		# excludes emp2 due to overlapping dates
		make_shift_assignment(self.shift3.name, self.emp2, add_days(today, 6))
		# excludes emp3 due to overlapping dates
		make_shift_assignment(self.shift3.name, self.emp3, today)

		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 1)  # emp1

		# includes emp2 as dates don't overlap anymore
		shift_assignment_tool.end_date = add_days(today, 5)
		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 2)  # emp1, emp2

		# includes emp3 as multiple shifts in a day are allowed and timings don't overlap
		frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 1)
		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 3)  # emp1, emp2, emp3

		# excludes emp3 due to overlapping shift timings
		shift_assignment_tool.shift_type = self.shift2.name
		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 2)  # emp1, emp2

		employee_names = [d.employee for d in employees]
		self.assertIn(self.emp1, employee_names)
		self.assertIn(self.emp2, employee_names)

	def test_get_employees_for_assigning_shift_schedule(self):
		today = getdate()

		args = {
			"doctype": "Shift Assignment Tool",
			"action": "Assign Shift Schedule",
			"company": "_Test Company",  # excludes emp4
			"shift_schedule": self.schedule1,
			"start_date": today,
		}
		shift_assignment_tool = ShiftAssignmentTool(args)
		advanced_filters = [["name", "in", [self.emp1, self.emp2, self.emp3]]]

		# does not exclude emp1 as days don't overlap
		make_shift_schedule_assignment(self.schedule4, self.emp1)
		# excludes emp2 due to overlapping days
		make_shift_schedule_assignment(self.schedule2, self.emp2)
		# excludes emp3 due to overlapping days
		make_shift_schedule_assignment(self.schedule3, self.emp3)

		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 1)  # emp1

		# includes emp3 as multiple shifts in a day are allowed and timings don't overlap
		frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 1)
		employees = shift_assignment_tool.get_employees(advanced_filters)
		self.assertEqual(len(employees), 2)  # emp1, emp3

		employee_names = [d.employee for d in employees]
		self.assertIn(self.emp1, employee_names)
		self.assertIn(self.emp3, employee_names)


	def test_bulk_assign_shift(self):
		today = getdate()

		args = {
			"doctype": "Shift Assignment Tool",
			"action": "Assign Shift",
			"company": "_Test Company",
			"shift_type": self.shift1.name,
			"status": "Active",
			"start_date": today,
			"end_date": add_days(today, 10),
		}
		shift_assignment_tool = ShiftAssignmentTool(args)

		employees = [self.emp1, self.emp2, self.emp3]
		shift_assignment_tool.bulk_assign(employees)
		shift_assignment_employees = frappe.get_list(
			"Shift Assignment",
			filters={
				"shift_type": self.shift1.name,
				"status": "Active",
				"start_date": today,
				"end_date": add_days(today, 10),
				"docstatus": 1,
			},
			pluck="employee",
		)
		self.assertIn(self.emp1, shift_assignment_employees)
		self.assertIn(self.emp2, shift_assignment_employees)
		self.assertIn(self.emp3, shift_assignment_employees)

	def test_bulk_assign_shift_schedule(self):
		today = getdate()

		args = {
			"doctype": "Shift Assignment Tool",
			"action": "Assign Shift Schedule",
			"company": "_Test Company",
			"shift_schedule": self.schedule1,
			"status": "Active",
			"start_date": today,
			"end_date": add_days(today, 10),
		}
		shift_assignment_tool = ShiftAssignmentTool(args)

		employees = [self.emp1, self.emp2, self.emp3]
		shift_assignment_tool._bulk_assign(employees)
		assigned_employees = frappe.get_list(
			"Shift Schedule Assignment",
			filters={
				"shift_schedule": self.schedule1,
				"shift_status": "Active",
				"enabled": 0,
			},
			pluck="employee",
		)
		self.assertIn(self.emp1, assigned_employees)
		self.assertIn(self.emp2, assigned_employees)
		self.assertIn(self.emp3, assigned_employees)



def make_shift_schedule_assignment(schedule, employee, create_shifts_after=None, enabled=1):
	assignment = frappe.new_doc("Shift Schedule Assignment")
	assignment.shift_schedule = schedule
	assignment.employee = employee
	assignment.company = "_Test Company"
	assignment.enabled = enabled
	assignment.create_shifts_after = create_shifts_after or getdate()
	assignment.save()

	return assignment.name
