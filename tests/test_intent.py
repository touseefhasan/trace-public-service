from __future__ import annotations

import unittest

from trace_engine.engine import TraceEngine
from trace_engine.intent import CategoryClassification, DeterministicCategoryClassifier
from trace_engine.models import ServiceProvider


class StubClassifier:
    def __init__(self, categories: tuple[str, ...]) -> None:
        self.categories = categories

    def classify(
        self, query: str, available_categories: tuple[str, ...]
    ) -> CategoryClassification:
        del query, available_categories
        return CategoryClassification(
            self.categories,
            "stub-llm",
            ("housing", "recovery"),
        )


class FailingClassifier:
    def classify(
        self, query: str, available_categories: tuple[str, ...]
    ) -> CategoryClassification:
        del query, available_categories
        raise RuntimeError("model unavailable")


class IntentClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.providers = (
            ServiceProvider(
                "housing",
                "Recovery Housing",
                city="Wichita",
                category="Housing & Shelter",
            ),
            ServiceProvider(
                "recovery",
                "Recovery Support",
                city="Wichita",
                category="Mental Health & Addiction",
            ),
            ServiceProvider(
                "housing-two",
                "Housing Navigation",
                city="Wichita",
                category="Housing & Shelter",
            ),
            ServiceProvider(
                "food",
                "Food Pantry",
                city="Wichita",
                category="Food",
            ),
            ServiceProvider(
                "remote-housing",
                "Topeka Housing",
                city="Topeka",
                category="Housing & Shelter",
            ),
        )

    def test_deterministic_classifier_returns_multiple_categories(self) -> None:
        classifier = DeterministicCategoryClassifier()
        result = classifier.classify(
            "I need transitional housing and addiction recovery help",
            tuple(provider.category for provider in self.providers),
        )
        self.assertEqual(
            result.categories,
            ("Housing & Shelter", "Mental Health & Addiction"),
        )

    def test_medical_vocabulary_maps_to_health(self) -> None:
        classifier = DeterministicCategoryClassifier()
        categories = ("Health & Dental Care", "Transportation")
        for query in (
            "I need prenatal care",
            "Where can my child get vaccines?",
            "I need a vision clinic",
            "Where can I get cancer treatment?",
        ):
            with self.subTest(query=query):
                result = classifier.classify(query, categories)
                self.assertIn("Health & Dental Care", result.categories)

    def test_graph_unions_categories_then_intersects_location(self) -> None:
        classifier = StubClassifier(
            ("Housing & Shelter", "Mental Health & Addiction")
        )
        result = TraceEngine(
            self.providers,
            "kg3",
            category_classifier=classifier,
        ).recommend("I need housing services in Wichita", limit=2)

        self.assertEqual(
            result.constraints.categories,
            ("Housing & Shelter", "Mental Health & Addiction"),
        )
        self.assertEqual(result.constraints.category_source, "stub-llm")
        self.assertEqual(
            {item.provider.category for item in result.recommendations},
            {"Housing & Shelter", "Mental Health & Addiction"},
        )
        self.assertIn(
            "recovery",
            {item.provider.provider_id for item in result.recommendations},
        )

    def test_failed_llm_uses_visible_deterministic_fallback(self) -> None:
        result = TraceEngine(
            self.providers,
            "kg3",
            category_classifier=FailingClassifier(),
        ).recommend("I need food in Wichita")
        self.assertEqual(result.constraints.categories, ("Food",))
        self.assertEqual(
            result.constraints.category_source,
            "deterministic_fallback",
        )
        self.assertEqual(result.recommendations[0].provider.provider_id, "food")


if __name__ == "__main__":
    unittest.main()
