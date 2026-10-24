"""The running number of the Employee series follows the numbers that exist (no site needed)."""

from unittest import TestCase

from hrms.regional.thailand import series

SERIES = "YY-BE.MM.###"


class TestSeriesSync(TestCase):
	def test_the_parts_before_the_running_number_and_its_digits(self):
		self.assertEqual(series.split_series(SERIES), (["YY-BE", "MM"], 3))
		self.assertEqual(series.split_series("EMP-.YYYY-BE.####"), (["EMP-", "YYYY-BE"], 4))
		with self.assertRaises(ValueError):
			series.split_series("YY-BE.MM")
		with self.assertRaises(ValueError):
			series.split_series("###.MM")

	def test_only_the_names_of_the_series_are_counted(self):
		names = [
			"6910001",
			"6910050",
			"6910051",
			"6809003",
			"C6707001",
			"UB-6902001",
			"CD-EMP-0059",
			"DUMMY-01",
		]
		self.assertEqual(series.highest_numbers(SERIES, names), {"6910": 51, "6809": 3})

	def test_a_rename_past_the_counter_is_raised_to_the_new_highest_number(self):
		# the counter stands at 50; Employee 6910050 was renamed 6910051: the next number would be 6910051 again
		names = ["6910001", "6910049", "6910051"]
		rows = series.plan(SERIES, names, {"6910": 50}, "6910")
		self.assertEqual(rows, [{"prefix": "6910", "highest": 51, "counter": 50, "action": "raise"}])

	def test_a_counter_in_step_or_ahead_is_left_alone(self):
		names = ["6910001", "6910002"]
		self.assertEqual(series.plan(SERIES, names, {"6910": 2}, "6910")[0]["action"], "ok")
		# a deleted or renamed number leaves the counter ahead: a number is skipped, never repeated
		self.assertEqual(series.plan(SERIES, names, {"6910": 9}, "6910")[0]["action"], "ahead")

	def test_a_month_with_no_counter_is_looked_at_only_when_asked(self):
		names = ["6810001", "6910003"]
		counters = {"6910": 3}
		self.assertEqual([r["prefix"] for r in series.plan(SERIES, names, counters, "6910")], ["6910"])
		rows = series.plan(SERIES, names, counters, "6910", all_prefixes=True)
		self.assertEqual({r["prefix"]: r["action"] for r in rows}, {"6810": "raise", "6910": "ok"})

	def test_the_prefix_of_today_with_no_employee_yet_is_in_step(self):
		rows = series.plan(SERIES, ["6810001"], {}, "6911")
		self.assertEqual(rows, [{"prefix": "6911", "highest": 0, "counter": None, "action": "ok"}])
