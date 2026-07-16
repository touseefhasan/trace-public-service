from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .engine import TraceEngine


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    query: str
    family: str
    gold_provider_ids: frozenset[str]
    query_id: str = ""
    num_matches_structural: int | None = None
    gold_provider_names: tuple[str, ...] = ()
    retrieval_evaluation_included: bool = True
    expected_clarification: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    variant: str
    queries: int
    retrieval_queries: int
    clarification_queries: int
    k: int
    precision_at_k: float
    recall_at_k: float
    f1_at_k: float
    constraint_satisfaction: float
    hallucination_rate: float
    clarification_accuracy: float | None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {
            key: round(item, 6) if isinstance(item, float) else item
            for key, item in value.items()
        }


def load_benchmark(path: str | Path) -> tuple[BenchmarkCase, ...]:
    cases: list[BenchmarkCase] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            query = value.get("query")
            family = value.get("family")
            gold = value.get("gold_provider_ids")
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"benchmark line {line_number} requires a non-empty query")
            if not isinstance(family, str) or not family.strip():
                raise ValueError(f"benchmark line {line_number} requires a family")
            if not isinstance(gold, list) or not all(isinstance(item, str) for item in gold):
                raise ValueError(
                    f"benchmark line {line_number} requires a list of gold_provider_ids"
                )
            query_id = value.get("query_id", "")
            num_matches = value.get("num_matches_structural")
            gold_names = value.get("gold_provider_names", [])
            retrieval_included = value.get("retrieval_evaluation_included", True)
            expected_clarification = value.get("expected_clarification", False)
            if not isinstance(query_id, str):
                raise ValueError(f"benchmark line {line_number} has an invalid query_id")
            if num_matches is not None and not isinstance(num_matches, int):
                raise ValueError(
                    f"benchmark line {line_number} has an invalid num_matches_structural"
                )
            if not isinstance(gold_names, list) or not all(
                isinstance(item, str) for item in gold_names
            ):
                raise ValueError(
                    f"benchmark line {line_number} requires a list of gold_provider_names"
                )
            if not isinstance(retrieval_included, bool):
                raise ValueError(
                    f"benchmark line {line_number} has an invalid retrieval_evaluation_included"
                )
            if not isinstance(expected_clarification, bool):
                raise ValueError(
                    f"benchmark line {line_number} has an invalid expected_clarification"
                )
            cases.append(
                BenchmarkCase(
                    query=query,
                    family=family,
                    gold_provider_ids=frozenset(gold),
                    query_id=query_id,
                    num_matches_structural=num_matches,
                    gold_provider_names=tuple(gold_names),
                    retrieval_evaluation_included=retrieval_included,
                    expected_clarification=expected_clarification,
                )
            )
    if not cases:
        raise ValueError("benchmark contains no query cases")
    return tuple(cases)


def evaluate(engine: TraceEngine, cases: tuple[BenchmarkCase, ...], k: int = 3) -> EvaluationMetrics:
    if k < 1:
        raise ValueError("k must be positive")

    directory_ids = {provider.provider_id for provider in engine.providers}
    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []
    satisfied_values: list[float] = []
    hallucination_values: list[float] = []
    clarification_values: list[float] = []

    for case in cases:
        result = engine.recommend(case.query, limit=k)
        if case.expected_clarification:
            clarification_values.append(float(result.clarification is not None))
        if not case.retrieval_evaluation_included:
            continue
        returned_ids = {item.provider.provider_id for item in result.recommendations}
        hits = len(returned_ids & case.gold_provider_ids)
        precision = hits / k
        recall = hits / len(case.gold_provider_ids) if case.gold_provider_ids else float(not returned_ids)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        constraints_satisfied = (
            returned_ids <= case.gold_provider_ids if returned_ids else not case.gold_provider_ids
        )
        hallucinated = bool(returned_ids - directory_ids)

        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)
        satisfied_values.append(float(constraints_satisfied))
        hallucination_values.append(float(hallucinated))

    count = len(precision_values)
    if not count:
        raise ValueError("benchmark contains no retrieval evaluation cases")
    return EvaluationMetrics(
        variant=engine.variant,
        queries=len(cases),
        retrieval_queries=count,
        clarification_queries=len(clarification_values),
        k=k,
        precision_at_k=sum(precision_values) / count,
        recall_at_k=sum(recall_values) / count,
        f1_at_k=sum(f1_values) / count,
        constraint_satisfaction=sum(satisfied_values) / count,
        hallucination_rate=sum(hallucination_values) / count,
        clarification_accuracy=(
            sum(clarification_values) / len(clarification_values)
            if clarification_values
            else None
        ),
    )
