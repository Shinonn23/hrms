# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now_datetime


HR_MANAGER = "HR Manager"
SYSTEM_MANAGER = "System Manager"
DOCTYPE = "Employee Professional License"
EDITABLE_LICENSE_FIELDS = (
	"license_type",
	"license_number",
	"issuing_authority",
	"jurisdiction",
	"issue_date",
	"no_expiry",
	"expiry_date",
	"license_document",
)


def is_hr_manager(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool({HR_MANAGER, SYSTEM_MANAGER} & set(frappe.get_roles(user)))


def get_employee_for_user(user):
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def is_employee_owner(employee, user):
	return bool(employee and frappe.db.get_value("Employee", employee, "user_id") == user)


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_hr_manager(user):
		return ""

	user = frappe.db.escape(user)
	return (
		f"`tab{DOCTYPE}`.employee in "
		f"(select name from `tabEmployee` where user_id = {user})"
	)


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if is_hr_manager(user):
		return True

	if ptype == "create":
		return bool(get_employee_for_user(user))

	if ptype not in ("read", "write"):
		return False

	if (
		ptype == "write"
		and getattr(doc, "verification_status", None) == "Pending Review"
		and not getattr(doc, "flags", {}).get("license_action")
	):
		return False

	return is_employee_owner(getattr(doc, "employee", None), user)


class EmployeeProfessionalLicense(Document):
	def before_insert(self):
		if not is_hr_manager():
			employee = get_employee_for_user(frappe.session.user)
			if not employee:
				frappe.throw(_("Your user account is not linked to an Employee record"), frappe.PermissionError)
			self.employee = employee
		self.verification_status = "Draft"
		self.review_comment = None
		self.reviewed_by = None
		self.reviewed_on = None
		self.reset_reminder_markers()

	def validate(self):
		self.validate_employee_access()
		self.validate_license_type()
		self.validate_workflow_transition()
		self.validate_dates()
		self.set_validity_status()

	def validate_employee_access(self):
		if is_hr_manager():
			return

		if not is_employee_owner(self.employee, frappe.session.user):
			frappe.throw(_("You can only manage your own professional licenses"), frappe.PermissionError)

		previous = self.get_doc_before_save()
		if previous and previous.employee != self.employee:
			frappe.throw(_("The employee cannot be changed"), frappe.PermissionError)

	def validate_license_type(self):
		if not self.license_type:
			return

		license_type = frappe.db.get_value(
			"Employee Professional License Type",
			self.license_type,
			["disabled", "jurisdiction", "issuing_authority"],
			as_dict=True,
		)
		if not license_type:
			frappe.throw(_("License Type does not exist"))
		previous = self.get_doc_before_save()
		if license_type.disabled and (not previous or previous.license_type != self.license_type):
			frappe.throw(_("This license type is disabled"))
		self.jurisdiction = license_type.jurisdiction
		self.issuing_authority = license_type.issuing_authority

	def validate_dates(self):
		if self.no_expiry:
			self.expiry_date = None
		elif not self.expiry_date:
			frappe.throw(_("Expiry Date is required unless No Expiry is selected"))

		if self.issue_date and self.expiry_date and getdate(self.expiry_date) < getdate(self.issue_date):
			frappe.throw(_("Expiry Date cannot be before Issue Date"))

		previous = self.get_doc_before_save()
		if previous and previous.expiry_date != self.expiry_date:
			self.reset_reminder_markers()

	def validate_workflow_transition(self):
		previous = self.get_doc_before_save()
		action = self.flags.get("license_action")
		if action:
			return

		if is_hr_manager():
			if previous and self.verification_status != previous.verification_status:
				frappe.throw(_("Use the review actions to change verification status"))
			if not previous:
				self.verification_status = "Draft"
			return

		if not previous:
			self.verification_status = "Draft"
			self.review_comment = None
			self.reviewed_by = None
			self.reviewed_on = None
			self.reset_reminder_markers()
			return

		self.review_comment = previous.review_comment
		self.reviewed_by = previous.reviewed_by
		self.reviewed_on = previous.reviewed_on
		self.reminder_90_days_sent_on = previous.reminder_90_days_sent_on
		self.reminder_30_days_sent_on = previous.reminder_30_days_sent_on
		self.reminder_7_days_sent_on = previous.reminder_7_days_sent_on

		if previous.verification_status == "Pending Review":
			frappe.throw(_("A license pending review cannot be edited"))

		if previous.verification_status == "Verified":
			if any(self.get(field) != previous.get(field) for field in EDITABLE_LICENSE_FIELDS):
				self.verification_status = "Pending Review"
				self.reviewed_by = None
				self.reviewed_on = None
				self.review_comment = None
				self.validate_submission()
			else:
				self.verification_status = previous.verification_status
			return

		self.verification_status = previous.verification_status

	def validate_submission(self):
		if not self.license_document:
			frappe.throw(_("Attach the license document before submitting it for review"))
		if not self.license_number or not self.license_type or not self.issue_date:
			frappe.throw(_("License Type, License Number, and Issue Date are required"))
		if not self.no_expiry and not self.expiry_date:
			frappe.throw(_("Expiry Date is required unless No Expiry is selected"))

	def set_validity_status(self):
		if self.no_expiry:
			self.validity_status = "No Expiry"
		elif not self.expiry_date:
			self.validity_status = "Active"
		else:
			today = getdate()
			expiry_date = getdate(self.expiry_date)
			if expiry_date < today:
				self.validity_status = "Expired"
			elif expiry_date <= add_days(today, 90):
				self.validity_status = "Expiring Soon"
			else:
				self.validity_status = "Active"

	def reset_reminder_markers(self):
		self.reminder_90_days_sent_on = None
		self.reminder_30_days_sent_on = None
		self.reminder_7_days_sent_on = None

	@frappe.whitelist(methods=["POST"])
	def submit_for_review(self):
		self.check_permission("write")
		if self.verification_status not in ("Draft", "Changes Requested"):
			frappe.throw(_("Only a draft or returned license can be submitted"))

		self.validate_submission()
		self.verification_status = "Pending Review"
		self.reviewed_by = None
		self.reviewed_on = None
		self.review_comment = None
		self.flags.license_action = "submit"
		self.save()

	@frappe.whitelist(methods=["POST"])
	def verify_license(self):
		self.check_permission("write")
		if not is_hr_manager():
			frappe.throw(_("Only an HR Manager can verify a license"), frappe.PermissionError)
		if self.verification_status != "Pending Review":
			frappe.throw(_("Only a license pending review can be verified"))
		self.validate_submission()

		self.verification_status = "Verified"
		self.review_comment = None
		self.reviewed_by = frappe.session.user
		self.reviewed_on = now_datetime()
		self.flags.license_action = "verify"
		self.save()

	@frappe.whitelist(methods=["POST"])
	def request_changes(self, comment):
		self.check_permission("write")
		if not is_hr_manager():
			frappe.throw(_("Only an HR Manager can request changes"), frappe.PermissionError)
		if self.verification_status != "Pending Review":
			frappe.throw(_("Only a license pending review can be returned"))
		if not comment or not comment.strip():
			frappe.throw(_("Add a comment explaining the requested changes"))

		self.verification_status = "Changes Requested"
		self.review_comment = comment.strip()
		self.reviewed_by = frappe.session.user
		self.reviewed_on = now_datetime()
		self.flags.license_action = "request_changes"
		self.save()


def get_hr_manager_recipients():
	users = frappe.get_all("User", filters={"enabled": 1}, fields=["name", "email"])
	return list(
		{
			user.email or user.name
			for user in users
			if HR_MANAGER in frappe.get_roles(user.name)
			and (user.email or ("@" in user.name and user.name))
		}
	)


def send_license_expiry_reminders():
	"""Refresh validity statuses and notify HR Managers about verified licenses nearing expiry."""
	today = getdate()
	cutoff = add_days(today, 90)
	recipients = None
	licenses = frappe.get_all(
		DOCTYPE,
		fields=[
			"name",
			"employee",
			"license_type",
			"license_number",
			"expiry_date",
			"no_expiry",
			"verification_status",
			"reminder_90_days_sent_on",
			"reminder_30_days_sent_on",
			"reminder_7_days_sent_on",
		],
		filters={"expiry_date": ["is", "set"]},
	)

	for license in licenses:
		expiry_date = getdate(license.expiry_date)
		if license.no_expiry:
			validity_status = "No Expiry"
		elif expiry_date < today:
			validity_status = "Expired"
		elif expiry_date <= cutoff:
			validity_status = "Expiring Soon"
		else:
			validity_status = "Active"
		frappe.db.set_value(DOCTYPE, license.name, "validity_status", validity_status, update_modified=False)

		if license.no_expiry or license.verification_status != "Verified":
			continue

		days_remaining = (expiry_date - today).days
		if days_remaining < 0 or days_remaining > 90:
			continue

		if days_remaining > 30:
			milestone, marker = 90, "reminder_90_days_sent_on"
		elif days_remaining > 7:
			milestone, marker = 30, "reminder_30_days_sent_on"
		else:
			milestone, marker = 7, "reminder_7_days_sent_on"

		if license.get(marker):
			continue

		if recipients is None:
			recipients = get_hr_manager_recipients()
		if not recipients:
			continue

		employee_name = frappe.db.get_value("Employee", license.employee, "employee_name")
		frappe.sendmail(
			recipients=recipients,
			subject=_("Professional license expires in {0} days ({1}-day reminder)").format(
				days_remaining, milestone
			),
			message=_("{0}'s {1} (license number {2}) expires in {3} days, on {4}.").format(
				frappe.utils.escape_html(employee_name or license.employee),
				frappe.utils.escape_html(license.license_type),
				frappe.utils.escape_html(license.license_number),
				days_remaining,
				frappe.utils.formatdate(expiry_date),
			)
			+ "<br><br>"
			+ frappe.utils.get_link_to_form(DOCTYPE, license.name),
			reference_doctype=DOCTYPE,
			reference_name=license.name,
		)
		frappe.db.set_value(DOCTYPE, license.name, marker, now_datetime(), update_modified=False)
