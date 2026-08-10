from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trace_engine.category_evaluation import (
    CategoryBenchmarkCase,
    evaluate_categories,
    load_category_benchmark,
)
from trace_engine.intent import CategoryClassification


class MappingClassifier:
    def classify(self, query: str, available_categories: tuple[str, ...]) -> CategoryClassification:
        del available_categories
        values = {
            "both": ("Food", "Housing & Shelter"),
            "food": ("Food",),
            "miss": (),
        }
        return CategoryClassification(values[query], "mapping")


class CategoryEvaluationTests(unittest.TestCase):
    def test_multilabel_metrics(self) -> None:
        cases = (
            CategoryBenchmarkCase("1", "both", frozenset({"Food", "Housing & Shelter"})),
            CategoryBenchmarkCase("2", "food", frozenset({"Food"})),
            CategoryBenchmarkCase("3", "miss", frozenset({"Housing & Shelter"})),
        )
        metrics = evaluate_categories(
            MappingClassifier(),
            cases,
            ("Food", "Housing & Shelter"),
            classifier_name="mapping",
        )
        self.assertAlmostEqual(metrics.exact_match_accuracy, 2 / 3)
        self.assertAlmostEqual(metrics.micro_precision, 1.0)
        self.assertAlmostEqual(metrics.micro_recall, 0.75)
        self.assertEqual(metrics.multi_label_queries, 1)
        self.assertEqual(metrics.multi_label_exact_match_accuracy, 1.0)

    def test_unvalidated_jsonl_is_excluded_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "benchmark.jsonl"
            path.write_text(
                '{"id":"1","query":"food","gold_categories":["Food"],'
                '"review_status":"Needs Review"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "marked Validated"):
                load_category_benchmark(path)
            cases = load_category_benchmark(path, allow_unvalidated=True)
            self.assertEqual(cases[0].gold_categories, frozenset({"Food"}))


if __name__ == "__main__":
    unittest.main()
