from __future__ import annotations

import json
import math
import re
import statistics
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .intent import CategoryClassifier
from .xlsx import read_worksheet


@dataclass(frozen=True, slots=True)
class CategoryBenchmarkCase:
    query_id: str
    query: str
    gold_categories: frozenset[str]
    review_status: str = "Validated"


@dataclass(frozen=True, slots=True)
class LabelMetrics:
    label: str
    support: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class CategoryEvaluationMetrics:
    classifier: str
    queries: int
    labels: int
    exact_match_accuracy: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    mean_jaccard: float
    multi_label_queries: int
    multi_label_exact_match_accuracy: float | None
    failed_queries: int
    median_latency_seconds: float
    p95_latency_seconds: float
    prediction_source_counts: dict[str, int]
    per_label: tuple[LabelMetrics, ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)

        def rounded(item: Any) -> Any:
            if isinstance(item, float):
                return round(item, 6)
            if isinstance(item, (list, tuple)):
                return [rounded(element) for element in item]
            if isinstance(item, dict):
                return {key: rounded(element) for key, element in item.items()}
            return item

        return rounded(value)


def _normalized_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {
        re.sub(r"[^a-z0-9]+", "_", str(key).strip().casefold()).strip("_"): value
        for key, value in row.items()
    }


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_category_benchmark(
    path: str | Path,
    *,
    allow_unvalidated: bool = False,
) -> tuple[CategoryBenchmarkCase, ...]:
    source = Path(path)
    if source.suffix.casefold() == ".jsonl":
        rows = []
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    elif source.suffix.casefold() == ".xlsx":
        rows = read_worksheet(source, "Annotations")
    else:
        raise ValueError("category benchmark must be JSONL or XLSX")

    cases: list[CategoryBenchmarkCase] = []
    for row_number, raw_row in enumerate(rows, start=2):
        row = _normalized_keys(raw_row)
        status = _clean(row.get("review_status")) or "Needs Review"
        if status.casefold() == "excluded":
            continue
        if status.casefold() != "validated" and not allow_unvalidated:
            continue

        query = _clean(row.get("query"))
        if not query:
            raise ValueError(f"category benchmark row {row_number} has no query")

        categories: list[str] = []
        if isinstance(row.get("gold_categories"), list):
            categories.extend(_clean(value) for value in row["gold_categories"])
        else:
            for index in range(1, 7):
                category = _clean(row.get(f"gold_category_{index}"))
                if category:
                    categories.append(category)
        categories = list(dict.fromkeys(category for category in categories if category))
        if not categories:
            raise ValueError(f"category benchmark row {row_number} has no gold categories")
        cases.append(
            CategoryBenchmarkCase(
                query_id=_clean(row.get("id") or row.get("query_id")) or str(row_number - 1),
                query=query,
                gold_categories=frozenset(categories),
                review_status=status,
            )
        )

    if not cases:
        qualifier = "including provisional rows" if allow_unvalidated else "marked Validated"
        raise ValueError(f"category benchmark contains no cases {qualifier}")
    return tuple(cases)


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[rank]


def evaluate_categories(
    classifier: CategoryClassifier,
    cases: Sequence[CategoryBenchmarkCase],
    available_categories: Sequence[str],
    *,
    classifier_name: str,
) -> CategoryEvaluationMetrics:
    labels = tuple(dict.fromkeys(category for category in available_categories if category))
    label_set = set(labels)
    counts = {label: Counter(tp=0, fp=0, fn=0) for label in labels}
    exact_values: list[float] = []
    jaccard_values: list[float] = []
    multi_exact_values: list[float] = []
    latencies: list[float] = []
    sources: Counter[str] = Counter()
    failed_queries = 0

    for case in cases:
        started = time.perf_counter()
        try:
            result = classifier.classify(case.query, labels)
            predicted = set(result.categories) & label_set
            sources[result.source] += 1
        except RuntimeError:
            predicted = set()
            sources["error"] += 1
            failed_queries += 1
        latencies.append(time.perf_counter() - started)

        gold = set(case.gold_categories)
        exact = float(predicted == gold)
        exact_values.append(exact)
        union = predicted | gold
        jaccard_values.append(len(predicted & gold) / len(union) if union else 1.0)
        if len(gold) > 1:
            multi_exact_values.append(exact)
        for label in labels:
            if label in predicted and label in gold:
                counts[label]["tp"] += 1
            elif label in predicted:
                counts[label]["fp"] += 1
            elif label in gold:
                counts[label]["fn"] += 1

    per_label: list[LabelMetrics] = []
    total_tp = total_fp = total_fn = 0
    for label in labels:
        tp, fp, fn = counts[label]["tp"], counts[label]["fp"], counts[label]["fn"]
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        per_label.append(LabelMetrics(label, tp + fn, precision, recall, _f1(precision, recall)))
        total_tp += tp
        total_fp += fp
        total_fn += fn

    micro_precision = _safe_divide(total_tp, total_tp + total_fp)
    micro_recall = _safe_divide(total_tp, total_tp + total_fn)
    supported = [metric for metric in per_label if metric.support]
    return CategoryEvaluationMetrics(
        classifier=classifier_name,
        queries=len(cases),
        labels=len(labels),
        exact_match_accuracy=statistics.fmean(exact_values),
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        micro_f1=_f1(micro_precision, micro_recall),
        macro_precision=statistics.fmean(metric.precision for metric in supported),
        macro_recall=statistics.fmean(metric.recall for metric in supported),
        macro_f1=statistics.fmean(metric.f1 for metric in supported),
        mean_jaccard=statistics.fmean(jaccard_values),
        multi_label_queries=len(multi_exact_values),
        multi_label_exact_match_accuracy=(
            statistics.fmean(multi_exact_values) if multi_exact_values else None
        ),
        failed_queries=failed_queries,
        median_latency_seconds=statistics.median(latencies),
        p95_latency_seconds=_percentile(latencies, 0.95),
        prediction_source_counts=dict(sorted(sources.items())),
        per_label=tuple(per_label),
    )
