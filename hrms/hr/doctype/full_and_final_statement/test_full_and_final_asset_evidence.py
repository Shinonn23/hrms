"""Validation of physical asset evidence before submitting a Full and Final Statement."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from hrms.hr.doctype.full_and_final_statement.full_and_final_statement import FullandFinalStatement


class TestFullAndFinalAssetEvidence(TestCase):
	def setUp(self):
		translations = patch(
			"hrms.hr.doctype.full_and_final_statement.full_and_final_statement._",
			side_effect=lambda message: message,
		)
		translations.start()
		self.addCleanup(translations.stop)

	def statement(self, *, outstanding=True, rows=None):
		movement = {"reference": "AM-1", "asset_name": "Laptop"}
		return SimpleNamespace(
			assets_allocated=rows or [],
			get_assets_movement=lambda: [movement] if outstanding else [],
		)

	def test_draft_status_and_missing_row_cannot_override_outstanding_custody(self):
		marked = frappe._dict(reference="AM-1", asset_name="Laptop", action="Return", status="Returned")
		for rows in ([marked], []):
			with (
				self.subTest(rows=rows),
				patch.object(frappe, "throw", side_effect=frappe.ValidationError),
				self.assertRaises(frappe.ValidationError),
			):
				FullandFinalStatement.validate_assets(self.statement(rows=rows))

	def test_native_return_marks_the_existing_draft_row_returned(self):
		row = frappe._dict(reference="AM-1", asset_name="Laptop", action="Return", status="Owned")
		FullandFinalStatement.validate_assets(self.statement(outstanding=False, rows=[row]))
		self.assertEqual(row.status, "Returned")

	def test_cost_recovery_is_available_for_an_outstanding_asset_only(self):
		row = frappe._dict(reference="AM-1", asset_name="Laptop", action="Recover Cost", status="Returned")
		FullandFinalStatement.validate_assets(self.statement(rows=[row]))
		self.assertEqual(row.status, "Owned")
		with patch.object(frappe, "throw", side_effect=frappe.ValidationError), self.assertRaises(
			frappe.ValidationError
		):
			FullandFinalStatement.validate_assets(self.statement(outstanding=False, rows=[row]))
