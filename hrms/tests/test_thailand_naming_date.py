"""Buddhist-era naming series parts read the date of the document being named (offline)."""

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import frappe

from hrms.regional.thailand import naming as thai_naming

TODAY = datetime(2026, 10, 24)


def parts(doc, hooks=None, flags=None):
	with (
		patch.object(thai_naming.frappe, "flags", frappe._dict(flags or {})),
		patch.object(thai_naming, "now_datetime", return_value=TODAY),
		patch.object(thai_naming.frappe, "get_hooks", return_value=hooks or {}),
	):
		return (
			thai_naming.year_be_short(doc),
			thai_naming.year_be(doc),
			thai_naming.month_be(doc),
		)


class TestNamingDocumentDate(TestCase):
	def test_a_sales_order_uses_its_transaction_date(self):
		doc = frappe._dict(doctype="Sales Order", transaction_date="2026-09-05")
		self.assertEqual(parts(doc), ("69", "2569", "09"))

	def test_posting_date_wins_over_creation(self):
		doc = frappe._dict(doctype="Sales Invoice", posting_date="2026-03-02", creation="2026-10-01 10:00:00")
		self.assertEqual(parts(doc), ("69", "2569", "03"))

	def test_the_hook_maps_a_doctype_to_its_field_and_the_last_app_wins(self):
		doc = frappe._dict(doctype="Lab Job", posting_date="2026-03-02", due_on="2025-12-31")
		self.assertEqual(parts(doc, {"Lab Job": "due_on"}), ("68", "2568", "12"))
		self.assertEqual(parts(doc, [{"Lab Job": "posting_date"}, {"Lab Job": "due_on"}])[2], "12")
		self.assertEqual(parts(doc, {"Lab Job": ["posting_date", "due_on"]})[2], "12")

	def test_no_document_is_today(self):
		self.assertEqual(parts(None), ("69", "2569", "10"))

	def test_an_object_without_get_is_today(self):
		self.assertEqual(parts(object()), ("69", "2569", "10"))

	def test_an_employee_still_uses_date_of_joining(self):
		doc = frappe._dict(doctype="Employee", date_of_joining="2025-10-01", posting_date="2026-01-01")
		self.assertEqual(parts(doc), ("68", "2568", "10"))

	def test_a_document_without_set_posting_time_uses_today(self):
		doc = frappe._dict(doctype="Sales Invoice", set_posting_time=0, posting_date="2026-03-02")
		self.assertEqual(parts(doc), ("69", "2569", "10"))
		doc.set_posting_time = 1
		self.assertEqual(parts(doc)[2], "03")

	def test_set_posting_time_does_not_matter_without_posting_date(self):
		doc = frappe._dict(doctype="Sales Order", set_posting_time=0, transaction_date="2026-09-05")
		self.assertEqual(parts(doc)[2], "09")

	def test_an_empty_date_is_today(self):
		doc = frappe._dict(doctype="Sales Order", transaction_date="", posting_date=None)
		self.assertEqual(parts(doc), ("69", "2569", "10"))

	def test_the_year_2057_is_00(self):
		doc = frappe._dict(doctype="Sales Order", transaction_date="2057-01-01")
		self.assertEqual(parts(doc), ("00", "2600", "01"))

	def test_an_import_keeps_the_posting_date(self):
		doc = frappe._dict(doctype="Sales Invoice", set_posting_time=0, posting_date="2026-03-02")
		self.assertEqual(parts(doc, flags={"in_import": True})[2], "03")

	def test_a_restore_keeps_the_posting_date(self):
		doc = frappe._dict(
			doctype="Sales Invoice",
			set_posting_time=0,
			posting_date="2026-03-02",
			flags=frappe._dict(from_restore=True),
		)
		self.assertEqual(parts(doc)[2], "03")

	def test_hooks_that_cannot_be_read_mean_no_mappings(self):
		doc = frappe._dict(doctype="Sales Order", transaction_date="2026-09-05")
		with (
			patch.object(thai_naming, "now_datetime", return_value=TODAY),
			patch.object(thai_naming.frappe, "get_hooks", side_effect=RuntimeError("boom")),
		):
			self.assertEqual(thai_naming.month_be(doc), "09")
