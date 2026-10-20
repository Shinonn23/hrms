# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from contextvars import ContextVar

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import add_days, flt, unique

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

_BOARDING_DOCUMENT_TOKEN = object()
_BOARDING_CANCELLATION_SOURCE = ContextVar("boarding_cancellation_source", default=None)


def get_native_boarding_source(doc):
	if doc.flags.get("boarding_document_token") is _BOARDING_DOCUMENT_TOKEN:
		return doc.flags.get("boarding_source")


def get_native_boarding_cancellation_source(doc):
	source = _BOARDING_CANCELLATION_SOURCE.get()
	if source and doc.doctype == "Project" and doc.name == source[2]:
		return source[:2]


def _can_delete_native_boarding_children(doc, project, tasks):
	"""Authorize only the persisted generated children of a native boarding cancellation."""
	if (
		doc.doctype not in {"Employee Onboarding", "Employee Separation"}
		or getattr(doc, "_action", None) != "cancel"
		or doc.docstatus != 2
	):
		return False
	previous = doc.get_doc_before_save()
	if (
		not previous
		or (previous.doctype, previous.name) != (doc.doctype, doc.name)
		or previous.docstatus != 1
		or previous.project != project
		or previous.company != doc.company
		or previous.get("department") != doc.get("department")
	):
		frappe.throw(_("Cancel only the original boarding document and its linked Project."))
	linked = frappe.get_doc("Project", project)
	if not linked.get("operation_source_doctype") and not linked.get("operation_source_name"):
		return False
	if (
		(linked.get("operation_source_doctype"), linked.get("operation_source_name"))
		!= (doc.doctype, doc.name)
		or linked.company != previous.company
		or linked.get("department") != previous.get("department")
	):
		frappe.throw(_("The generated Project must belong to this boarding document."))
	activity_tasks = {row.task for row in previous.activities if row.get("task")}
	for task in tasks:
		linked_task = frappe.get_doc("Task", task.name)
		if (
			task.name not in activity_tasks
			or linked_task.project != project
			or linked_task.get("company") != previous.company
			or linked_task.get("department") != previous.get("department")
		):
			frappe.throw(_("Cancel only Tasks generated for this boarding document's activities."))
	return True


class EmployeeBoardingController(Document):
	"""
	Create the project and the task for the boarding process
	Assign to the concerned person and roles as per the onboarding/separation template
	"""

	def validate(self):
		# remove the task if linked before submitting the form
		if self.amended_from:
			for activity in self.activities:
				activity.task = ""

	def on_submit(self):
		# create the project for the given employee onboarding
		project_name = _(self.doctype) + " : "
		if self.doctype == "Employee Onboarding":
			project_name += self.job_applicant or self.employee_name
		else:
			project_name += self.employee

		project = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": project_name,
				"expected_start_date": self.date_of_joining
				if self.doctype == "Employee Onboarding"
				else self.resignation_letter_date,
				"department": self.department,
				"company": self.company,
			}
		)
		project.flags.boarding_document_token = _BOARDING_DOCUMENT_TOKEN
		project.flags.boarding_source = (self.doctype, self.name)
		project.insert(ignore_permissions=True, ignore_mandatory=True)

		self.db_set("project", project.name)
		self.db_set("boarding_status", "Pending")
		self.reload()
		self.create_task_and_notify_user()

	def create_task_and_notify_user(self):
		# create the task for the given project and assign to the concerned person
		holiday_list = self.get_holiday_list()

		for activity in self.activities:
			if activity.task:
				continue

			dates = self.get_task_dates(activity, holiday_list)

			task = frappe.get_doc(
				{
					"doctype": "Task",
					"project": self.project,
					"subject": activity.activity_name + " : " + self.employee_name,
					"description": activity.description,
					"department": self.department,
					"company": self.company,
					"task_weight": activity.task_weight,
					"exp_start_date": dates[0],
					"exp_end_date": dates[1],
				}
			)
			task.flags.boarding_document_token = _BOARDING_DOCUMENT_TOKEN
			task.flags.boarding_source = (self.doctype, self.name)
			task.insert(ignore_permissions=True)
			activity.db_set("task", task.name)

			users = [activity.user] if activity.user else []
			if activity.role:
				has_role = frappe.qb.DocType("Has Role")
				user = frappe.qb.DocType("User")
				user_list = (
					frappe.qb.from_(has_role)
					.left_join(user)
					.on(has_role.parent == user.name)
					.select(has_role.parent)
					.distinct()
					.where(
						(has_role.parenttype == "User")
						& (user.enabled == 1)
						& (has_role.role == activity.role)
					)
					.run(pluck="parent")
				)
				users = unique(users + user_list)

				if "Administrator" in users:
					users.remove("Administrator")

			# assign the task the users
			if users:
				self.assign_task_to_users(task, users)

	def get_holiday_list(self):
		if self.doctype == "Employee Separation":
			return get_holiday_list_for_employee(self.employee, as_on=self.boarding_begins_on)
		else:
			if self.employee:
				return get_holiday_list_for_employee(self.employee, as_on=self.boarding_begins_on)
			else:
				if not self.holiday_list:
					frappe.throw(_("Please set the Holiday List."), frappe.MandatoryError)
				else:
					return self.holiday_list

	def get_task_dates(self, activity, holiday_list):
		start_date = end_date = None

		if activity.begin_on is not None:
			start_date = add_days(self.boarding_begins_on, activity.begin_on)
			start_date = self.update_if_holiday(start_date, holiday_list)

			if activity.duration is not None:
				end_date = add_days(self.boarding_begins_on, activity.begin_on + activity.duration)
				end_date = self.update_if_holiday(end_date, holiday_list)

		return [start_date, end_date]

	def update_if_holiday(self, date, holiday_list):
		while is_holiday(holiday_list, date):
			date = add_days(date, 1)
		return date

	def assign_task_to_users(self, task, users):
		for user in users:
			args = {
				"assign_to": [user],
				"doctype": task.doctype,
				"name": task.name,
				"description": task.description or task.subject,
				"notify": self.notify_users_by_email,
			}
			assign_to.add(args)

	def on_cancel(self):
		# delete task project
		project = self.project
		if not project:
			return
		tasks = frappe.get_all("Task", filters={"project": project})
		generated_cleanup = _can_delete_native_boarding_children(self, project, tasks)
		# Task deletion saves its Project after the boarding document is cancelled.
		token = _BOARDING_CANCELLATION_SOURCE.set((self.doctype, self.name, project))
		try:
			for task in tasks:
				frappe.delete_doc("Task", task.name, force=1, ignore_permissions=generated_cleanup)
			frappe.delete_doc("Project", project, force=1, ignore_permissions=generated_cleanup)
		finally:
			_BOARDING_CANCELLATION_SOURCE.reset(token)
		self.db_set("project", "")
		for activity in self.activities:
			activity.db_set("task", "")

		frappe.msgprint(
			_("Linked Project {} and Tasks deleted.").format(project), alert=True, indicator="blue"
		)


@frappe.whitelist()
def get_onboarding_details(parent: str, parenttype: str):
	frappe.has_permission(parenttype, "read", parent, throw=True)
	return frappe.get_all(
		"Employee Boarding Activity",
		fields=[
			"activity_name",
			"role",
			"user",
			"required_for_employee_creation",
			"description",
			"task_weight",
			"begin_on",
			"duration",
		],
		filters={"parent": parent, "parenttype": parenttype},
		order_by="idx",
	)


def update_employee_boarding_status(project, event=None):
	employee_onboarding = frappe.db.exists("Employee Onboarding", {"project": project.name})
	employee_separation = frappe.db.exists("Employee Separation", {"project": project.name})

	if not (employee_onboarding or employee_separation):
		return

	status = "Pending"
	if flt(project.percent_complete) > 0.0 and flt(project.percent_complete) < 100.0:
		status = "In Process"
	elif flt(project.percent_complete) == 100.0:
		status = "Completed"

	if employee_onboarding:
		frappe.db.set_value("Employee Onboarding", employee_onboarding, "boarding_status", status)
	elif employee_separation:
		frappe.db.set_value("Employee Separation", employee_separation, "boarding_status", status)


def update_task(task, event=None):
	if task.project and not task.flags.from_project:
		update_employee_boarding_status(frappe.get_cached_doc("Project", task.project))
