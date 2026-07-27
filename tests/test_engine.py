from __future__ import annotations

import unittest
from pathlib import Path

from trace_engine.engine import TraceEngine
from trace_engine.ingestion import load_directory
from trace_engine.models import ServiceProvider


SAMPLE_DATA = Path(__file__).parents[1] / "data" / "sample" / "pantries.csv"


class TraceEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.providers = load_directory(SAMPLE_DATA)

    def test_kg3_enforces_location_hours_and_semantics(self) -> None:
        result = TraceEngine(self.providers, "kg3").recommend(
            "Find a pantry in Sedgwick County open Monday at 10am without ID"
        )
        self.assertIsNone(result.clarification)
        self.assertEqual([item.provider.provider_id for item in result.recommendations], ["ks-001"])
        # Two providers satisfy the exact location and hours constraints; the
        # eligibility checker then rejects the one that requires identification.
        self.assertEqual(result.candidates_examined, 2)

    def test_asks_for_clarification_without_structural_constraint(self) -> None:
        result = TraceEngine(self.providers, "kg3").recommend("I need food assistance")
        self.assertEqual(
            result.clarification,
            "Where are you looking for food? Please provide a city, county, or ZIP code.",
        )
        self.assertEqual(result.recommendations, ())

    def test_time_without_location_asks_for_location(self) -> None:
        result = TraceEngine(self.providers, "kg3").recommend("I need food at 10am")
        self.assertEqual(result.constraints.open_at, "10:00")
        self.assertEqual(
            result.clarification,
            "Where are you looking for food? Please provide a city, county, or ZIP code.",
        )
        self.assertEqual(result.recommendations, ())
        self.assertEqual(result.candidates_examined, 0)

    def test_location_and_time_without_day_asks_for_day(self) -> None:
        result = TraceEngine(self.providers, "kg3").recommend(
            "I need food in Wichita at 10am"
        )
        self.assertEqual(result.constraints.city, "Wichita")
        self.assertEqual(result.constraints.open_at, "10:00")
        self.assertEqual(
            result.clarification,
            "Which day should I check for availability at 10:00?",
        )
        self.assertEqual(result.recommendations, ())

    def test_named_provider_is_a_retrieval_anchor(self) -> None:
        result = TraceEngine(self.providers, "kg3").recommend(
            "Tell me about Sunrise Community Pantry"
        )
        self.assertIsNone(result.clarification)
        self.assertEqual(
            [item.provider.provider_id for item in result.recommendations],
            ["ks-001"],
        )

    def test_semantic_filter_fetches_later_batches(self) -> None:
        result = TraceEngine(self.providers, "kg1").recommend(
            "Which pantries in Sedgwick County require ID?",
            limit=2,
            batch_size=1,
        )
        self.assertEqual(
            {item.provider.provider_id for item in result.recommendations},
            {"ks-002", "ks-004"},
        )
        self.assertGreaterEqual(result.candidates_examined, 2)

    def test_results_only_contain_directory_records(self) -> None:
        known_ids = {provider.provider_id for provider in self.providers}
        result = TraceEngine(self.providers, "kg0").recommend("Pantry near Wichita", limit=5)
        self.assertTrue({item.provider.provider_id for item in result.recommendations} <= known_ids)

    def test_category_and_derived_city_retrieve_relevant_services(self) -> None:
        providers = (
            ServiceProvider(
                "shelter",
                "Downtown Emergency Shelter",
                city="Wichita",
                county="Sedgwick",
                zipcode="67202",
                category="Housing & Shelter",
                description="Emergency overnight shelter for adults.",
            ),
            ServiceProvider(
                "internet",
                "Internet Access Program",
                city="Wichita",
                county="Sedgwick",
                zipcode="67211",
                category="Housing & Shelter",
                description="Free mobile hotspots for students.",
            ),
            ServiceProvider(
                "food",
                "Community Food Pantry",
                city="Wichita",
                county="Sedgwick",
                zipcode="67214",
                category="Food",
            ),
        )
        result = TraceEngine(providers, "kg3").recommend(
            "Where do I find shelter in Wichita?"
        )
        self.assertEqual(result.constraints.city, "Wichita")
        self.assertEqual(result.constraints.category, "Housing & Shelter")
        self.assertEqual(result.recommendations[0].provider.provider_id, "shelter")
        self.assertTrue(
            all(
                item.provider.category == "Housing & Shelter"
                for item in result.recommendations
            )
        )

    def test_service_category_without_location_requests_location(self) -> None:
        providers = (
            ServiceProvider(
                "one",
                "Example Shelter",
                city="Wichita",
                category="Housing & Shelter",
            ),
        )
        result = TraceEngine(providers, "kg3").recommend("I need shelter")
        self.assertEqual(result.constraints.category, "Housing & Shelter")
        self.assertEqual(
            result.clarification,
            (
                "Where are you looking for Housing & Shelter services? "
                "Please provide a city, county, or ZIP code."
            ),
        )


if __name__ == "__main__":
    unittest.main()
