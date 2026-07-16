from __future__ import annotations

import unittest
from pathlib import Path

from trace_engine.engine import TraceEngine
from trace_engine.evaluation import BenchmarkCase, evaluate, load_benchmark
from trace_engine.ingestion import load_directory


ROOT = Path(__file__).parents[1]


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.providers = load_directory(ROOT / "data" / "sample" / "pantries.csv")
        cls.cases = load_benchmark(ROOT / "benchmarks" / "sample.jsonl")

    def test_sample_kg3_benchmark_has_no_hallucinations(self) -> None:
        metrics = evaluate(TraceEngine(self.providers, "kg3"), self.cases, k=3)
        self.assertEqual(metrics.queries, 5)
        self.assertEqual(metrics.retrieval_queries, 5)
        self.assertEqual(metrics.clarification_queries, 0)
        self.assertIsNone(metrics.clarification_accuracy)
        self.assertEqual(metrics.hallucination_rate, 0.0)
        self.assertEqual(metrics.constraint_satisfaction, 1.0)

    def test_rejects_invalid_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "k must be positive"):
            evaluate(TraceEngine(self.providers, "kg3"), self.cases, k=0)

    def test_expected_clarification_is_scored_separately(self) -> None:
        clarification = BenchmarkCase(
            query="Find a pantry near me",
            family="near_me",
            gold_provider_ids=frozenset(),
            retrieval_evaluation_included=False,
            expected_clarification=True,
        )
        metrics = evaluate(
            TraceEngine(self.providers, "kg3"),
            (self.cases[0], clarification),
            k=3,
        )
        self.assertEqual(metrics.queries, 2)
        self.assertEqual(metrics.retrieval_queries, 1)
        self.assertEqual(metrics.clarification_queries, 1)
        self.assertEqual(metrics.clarification_accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()
