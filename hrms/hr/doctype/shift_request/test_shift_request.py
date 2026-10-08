# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.shift_request.shift_request import OverlappingShiftRequestError
from hrms.hr.doctype.shift_type.test_shift_type import setup_shift_type
from hrms.tests.utils import HRMSTestSuite


class TestShiftRequest(HRMSTestSuite):
	def setUp(self):
		for doctype in ["Shift Request", "Shift Assignment", "Shift Type"]:
			frappe.db.delete(doctype)

	def test_make_shift_request(self):
		"Test creation/updation of Shift Assignment from Shift Request."
		setup_shift_type(shift_type="Day Shift")
		shift_request = make_shift_request()

		# Only one shift assignment is created against a shift request
		shift_assignment = frappe.db.get_value(
			"Shift Assignment",
			filters={"shift_request": shift_request.name},
			fieldname=["employee", "docstatus"],
			as_dict=True,
		)
		self.assertEqual(shift_request.employee, shift_assignment.employee)
		self.assertEqual(shift_assignment.docstatus, 1)

		shift_request.cancel()

		shift_assignment_docstatus = frappe.db.get_value(
			"Shift Assignment", filters={"shift_request": shift_request.name}, fieldname="docstatus"
		)
		self.assertEqual(shift_assignment_docstatus, 2)
		self.assertEqual(shift_request.docstatus, 2)


	def test_overlap_for_request_without_to_date(self):
		# shift should be Ongoing if Only from_date is present
		user = "test_shift_request@example.com"
		employee = make_employee(user, company="_Test Company")
		setup_shift_type(shift_type="Day Shift")

		shift_request = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": "Day Shift",
				"company": "_Test Company",
				"employee": employee,
				"from_date": nowdate(),
			}
		).submit()

		shift_request = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": "Day Shift",
				"company": "_Test Company",
				"employee": employee,
				"from_date": add_days(nowdate(), 2),
			}
		)

		self.assertRaises(OverlappingShiftRequestError, shift_request.save)

	def test_overlap_for_request_with_from_and_to_dates(self):
		user = "test_shift_request@example.com"
		employee = make_employee(user, company="_Test Company")
		setup_shift_type(shift_type="Day Shift")

		shift_request = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": "Day Shift",
				"company": "_Test Company",
				"employee": employee,
				"from_date": nowdate(),
				"to_date": add_days(nowdate(), 30),
			}
		).submit()

		shift_request = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": "Day Shift",
				"company": "_Test Company",
				"employee": employee,
				"from_date": add_days(nowdate(), 10),
				"to_date": add_days(nowdate(), 35),
			}
		)

		self.assertRaises(OverlappingShiftRequestError, shift_request.save)

	def test_overlapping_for_a_fixed_period_shift_and_ongoing_shift(self):
		user = "test_shift_request@example.com"
		employee = make_employee(user, company="_Test Company")

		# shift setup for 8-12
		shift_type = setup_shift_type(shift_type="Shift 1", start_time="08:00:00", end_time="12:00:00")
		date = nowdate()

		# shift with end date
		frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": shift_type.name,
				"company": "_Test Company",
				"employee": employee,
				"from_date": date,
				"to_date": add_days(date, 30),
			}
		).submit()

		# shift setup for 11-15
		shift_type = setup_shift_type(shift_type="Shift 2", start_time="11:00:00", end_time="15:00:00")
		shift2 = frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": shift_type.name,
				"company": "_Test Company",
				"employee": employee,
				"from_date": date,
			}
		)

		self.assertRaises(OverlappingShiftRequestError, shift2.insert)

	@HRMSTestSuite.change_settings("HR Settings", {"allow_multiple_shift_assignments": 1})
	def test_allow_non_overlapping_shift_requests_for_same_day(self):
		user = "test_shift_request@example.com"
		employee = make_employee(user, company="_Test Company")

		# shift setup for 8-12
		shift_type = setup_shift_type(shift_type="Shift 1", start_time="08:00:00", end_time="12:00:00")
		date = nowdate()

		# shift with end date
		frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": shift_type.name,
				"company": "_Test Company",
				"employee": employee,
				"from_date": date,
				"to_date": add_days(date, 30),
			}
		).submit()

		# shift setup for 13-15
		shift_type = setup_shift_type(shift_type="Shift 2", start_time="13:00:00", end_time="15:00:00")
		frappe.get_doc(
			{
				"doctype": "Shift Request",
				"shift_type": shift_type.name,
				"company": "_Test Company",
				"employee": employee,
				"from_date": date,
			}
		).submit()

def make_shift_request(
	employee="_T-Employee-00001",
	employee_name="_Test Employee",
	from_date=None,
	to_date=None,
	do_not_submit=0,
):
	from_date = from_date or nowdate()
	to_date = to_date or add_days(nowdate(), 10)

	shift_request = frappe.get_doc(
		{
			"doctype": "Shift Request",
			"shift_type": "Day Shift",
			"company": "_Test Company",
			"employee": employee,
			"employee_name": employee_name,
			"from_date": from_date,
			"to_date": to_date,
		}
	).insert()

	if do_not_submit:
		return shift_request

	shift_request.submit()
	return shift_request
