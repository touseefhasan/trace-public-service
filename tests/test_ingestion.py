from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trace_engine.ingestion import load_directory


class IngestionTests(unittest.TestCase):
    def test_kansas_food_source_schema_is_adapted(self) -> None:
        path = Path(__file__).parents[1] / "data" / "sample" / "kansas_source.csv"
        providers = load_directory(path)
        first = providers[0]
        self.assertEqual(first.provider_id, "source-001")
        self.assertEqual(first.name, "Example Pantry")
        self.assertEqual(first.county, "Sedgwick")
        self.assertEqual(first.eligibility, "No ID required, /category/tefap/")
        self.assertEqual(first.source_url, "https://kansasfoodsource.org/category/tefap/")

    def test_json_ingestion_preserves_leading_zipcode_zeroes(self) -> None:
        value = [
            {
                "provider_id": "one",
                "name": "Example",
                "city": "Town",
                "county": "County",
                "zipcode": 1234,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            providers = load_directory(path)
        self.assertEqual(providers[0].zipcode, "01234")

    def test_duplicate_provider_ids_are_rejected(self) -> None:
        value = [
            {"provider_id": "one", "name": "A", "city": "X", "county": "Y", "zipcode": "12345"},
            {"provider_id": "one", "name": "B", "city": "X", "county": "Y", "zipcode": "12345"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be unique"):
                load_directory(path)


if __name__ == "__main__":
    unittest.main()
