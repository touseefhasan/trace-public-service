from __future__ import annotations

import unittest
from pathlib import Path

from trace_engine.constraints import ConstraintParser
from trace_engine.ingestion import load_directory
from trace_engine.normalization import normalize_text


SAMPLE_DATA = Path(__file__).parents[1] / "data" / "sample" / "pantries.csv"


class ConstraintParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = ConstraintParser(load_directory(SAMPLE_DATA))

    def test_extracts_location_hours_and_negated_id(self) -> None:
        constraints = self.parser.parse(
            "Find a pantry in Sedgwick County open Monday at 10am without ID"
        )
        self.assertEqual(constraints.county, "Sedgwick")
        self.assertEqual(constraints.day, "monday")
        self.assertEqual(constraints.open_at, "10:00")
        self.assertEqual(constraints.semantic, ("no id required",))

    def test_extracts_zipcode(self) -> None:
        constraints = self.parser.parse("What is available near 67114?")
        self.assertEqual(constraints.zipcode, "67114")

    def test_normalization_removes_trailing_punctuation_space(self) -> None:
        self.assertEqual(normalize_text("Food Bank Inc."), "food bank inc")

    def test_county_phrase_does_not_also_select_same_named_city(self) -> None:
        constraints = self.parser.parse("Pantries in Sedgwick County")
        self.assertEqual(constraints.county, "Sedgwick")
        self.assertIsNone(constraints.city)


if __name__ == "__main__":
    unittest.main()
