from __future__ import annotations

import unittest

from trace_engine.constraint_evaluation import (
    ConstraintCase,
    LocationExpectation,
    TemporalExpectation,
    evaluate_constraint_retrieval,
    evaluate_hours,
    evaluate_location,
    location_expectation,
)
from trace_engine.intent import CategoryClassification
from trace_engine.models import ServiceProvider


class StubCategoryClassifier:
    def classify(self, query, available_categories):
        return CategoryClassification(("Food",), "stub:qwen", ("food",))


class ConstraintEvaluationTests(unittest.TestCase):
    def test_location_mismatch_is_unknown_without_service_area(self) -> None:
        provider = ServiceProvider(
            "one", "Statewide Help", city="Topeka", state="KS", zipcode="66603"
        )
        status, _ = evaluate_location(
            provider,
            LocationExpectation(raw="Wichita", city="Wichita"),
        )
        self.assertEqual(status, "Unknown")

    def test_location_parser_supports_city_and_county(self) -> None:
        expected = location_expectation("Location: Pretty Prairie (Reno County) | Age: senior")
        self.assertEqual(expected.city, "Pretty Prairie")
        self.assertEqual(expected.county, "Reno")

    def test_explicit_weekend_hours_can_be_verified(self) -> None:
        provider = ServiceProvider(
            "one", "Weekend Help", hours="Sat 9:00 AM-1:00 PM | Sun Closed"
        )
        status, _ = evaluate_hours(provider, TemporalExpectation(weekend=True))
        self.assertEqual(status, "Satisfied")

    def test_relative_time_without_date_is_unknown(self) -> None:
        provider = ServiceProvider("one", "Clinic", hours="Mon-Fri 8:00 AM-5:00 PM")
        status, _ = evaluate_hours(provider, TemporalExpectation(relative_time="today"))
        self.assertEqual(status, "Unknown")

    def test_retrieval_evaluation_records_classifier_source_and_latency(self) -> None:
        provider = ServiceProvider(
            "one", "Food Help", category="Food", city="Wichita", county="Sedgwick"
        )
        case = ConstraintCase(
            query_id="1",
            query="I need food in Wichita",
            structured_constraints="Location: Wichita",
            gold_categories=("Food",),
            review_status="Validated",
        )
        result = evaluate_constraint_retrieval(
            (provider,),
            (case,),
            category_classifier=StubCategoryClassifier(),
            classifier_name="qwen-test",
        )
        self.assertEqual(result["metrics"]["classifier"], "qwen-test")
        self.assertEqual(result["metrics"]["category_source_counts"], {"stub:qwen": 1})
        self.assertGreaterEqual(result["query_rows"][0]["query_latency_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
