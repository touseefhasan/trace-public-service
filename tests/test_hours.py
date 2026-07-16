from __future__ import annotations

import unittest

from trace_engine.normalization import is_open, parse_hours


class HoursNormalizationTests(unittest.TestCase):
    def test_parses_weekday_range_with_inferred_am_pm(self) -> None:
        schedule = parse_hours("Monday-Friday from 8:30am-3pm")
        self.assertEqual(set(schedule), {"monday", "tuesday", "wednesday", "thursday", "friday"})
        self.assertEqual(schedule["monday"], ((510, 900),))

    def test_parses_day_list(self) -> None:
        schedule = parse_hours("Tuesday and Thursday from 9am-12pm")
        self.assertEqual(schedule["tuesday"], ((540, 720),))
        self.assertEqual(schedule["thursday"], ((540, 720),))

    def test_parses_multiple_clauses(self) -> None:
        schedule = parse_hours(
            "Monday & Wednesday from 8am-5pm, Tuesday & Thursday from 8am-3pm"
        )
        self.assertEqual(schedule["monday"], ((480, 1020),))
        self.assertEqual(schedule["thursday"], ((480, 900),))

    def test_retains_day_when_time_is_unknown(self) -> None:
        schedule = parse_hours("4th Thursday of each month starting at 4pm")
        self.assertEqual(schedule["thursday"], ((None, None),))
        self.assertTrue(is_open("4th Thursday of each month starting at 4pm", "thursday", None))
        self.assertFalse(is_open("4th Thursday of each month starting at 4pm", "thursday", "16:00"))

    def test_does_not_treat_dated_event_as_recurring(self) -> None:
        schedule = parse_hours("Wednesday, March 26, 2025 from 12:30pm to 1:15pm")
        self.assertEqual(schedule, {})

    def test_parses_plural_days_and_twenty_four_seven(self) -> None:
        self.assertEqual(parse_hours("Thursdays from 1-4pm")["thursday"], ((780, 960),))
        always_open = parse_hours("Available 24/7")
        self.assertEqual(
            set(always_open),
            {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"},
        )
        self.assertTrue(is_open("Available 24/7", "sunday", "23:59"))

    def test_parses_m_to_f_abbreviation(self) -> None:
        schedule = parse_hours("Office Hours M-F, 9AM-5PM by appointment only")
        self.assertEqual(schedule["monday"], ((540, 1020),))
        self.assertEqual(schedule["friday"], ((540, 1020),))


if __name__ == "__main__":
    unittest.main()
