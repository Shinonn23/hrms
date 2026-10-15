"""Professional license layout checks that do not require a Frappe site."""

import json
from pathlib import Path
from unittest import TestCase

FORM_PATH = (
	Path(__file__).resolve().parents[1]
	/ "hr/doctype/employee_professional_license/employee_professional_license.json"
)


class TestProfessionalLicenseFormLayout(TestCase):
	def test_sections_keep_status_visible_and_review_history_separate(self):
		form = json.loads(FORM_PATH.read_text())
		fields = {row["fieldname"]: row for row in form["fields"]}
		self.assertEqual(form["field_order"], list(fields))
		self.assertEqual(len(fields), len(form["fields"]))
		sections = {}
		section = None
		columns = 0
		for row in fields.values():
			self.assertNotEqual(row["fieldtype"], "Tab Break")
			if row["fieldtype"] == "Section Break":
				section = row["fieldname"]
				columns = 1
				self.assertTrue(row.get("label"))
			elif row["fieldtype"] == "Column Break":
				columns += 1
				self.assertEqual(columns, 2)
			else:
				self.assertIsNotNone(section)
				sections[row["fieldname"]] = section
		for name in (
			"employee",
			"employee_name",
			"license_type",
			"license_number",
			"issuing_authority",
			"jurisdiction",
		):
			self.assertEqual(sections[name], "license_details_section")
		for name in (
			"issue_date",
			"no_expiry",
			"expiry_date",
			"license_document",
			"verification_status",
			"validity_status",
		):
			self.assertEqual(sections[name], "validity_evidence_section")
		self.assertFalse(fields["validity_evidence_section"].get("depends_on"))
		for name in ("review_comment", "reviewed_by", "reviewed_on"):
			self.assertEqual(sections[name], "review_history_section")
			self.assertEqual(fields[name]["read_only"], 1)
		self.assertEqual(
			fields["review_history_section"]["depends_on"],
			"eval:doc.review_comment || doc.reviewed_by || doc.reviewed_on",
		)

	def test_expiry_and_private_evidence_rules_are_preserved(self):
		form = json.loads(FORM_PATH.read_text())
		fields = {row["fieldname"]: row for row in form["fields"]}
		self.assertEqual(fields["expiry_date"]["depends_on"], "eval:!doc.no_expiry")
		self.assertEqual(fields["expiry_date"]["mandatory_depends_on"], "eval:!doc.no_expiry")
		self.assertEqual(fields["license_document"]["make_attachment_public"], 0)
		self.assertFalse(fields["license_document"].get("reqd"))
		self.assertEqual(form["make_attachments_public"], 0)
		for name in ("verification_status", "validity_status"):
			self.assertEqual(fields[name]["read_only"], 1)
		for days in (90, 30, 7):
			field = fields[f"reminder_{days}_days_sent_on"]
			self.assertEqual(field["hidden"], 1)
			self.assertEqual(field["read_only"], 1)
