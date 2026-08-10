from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .engine import TraceEngine
from .intent import CategoryClassifier
from .models import ServiceProvider
from .normalization import is_open, normalize_location, normalize_text, parse_clock
from .xlsx import read_worksheet


DAY_NAMES = {
    "monday": "monday",
    "tuesday": "tuesday",
    "wednesday": "wednesday",
    "thursday": "thursday",
    "friday": "friday",
    "saturday": "saturday",
    "sunday": "sunday",
}
TIME_PATTERN = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ConstraintCase:
    query_id: str
    query: str
    structured_constraints: str
    gold_categories: tuple[str, ...]
    review_status: str


@dataclass(frozen=True, slots=True)
class LocationExpectation:
    raw: str
    city: str = ""
    county: str = ""
    zipcode: str = ""
    state: str = ""
    area: bool = False


@dataclass(frozen=True, slots=True)
class TemporalExpectation:
    day: str = ""
    open_at: str = ""
    weekend: bool = False
    relative_time: str = ""


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalized_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {
        re.sub(r"[^a-z0-9]+", "_", str(key).strip().casefold()).strip("_"): value
        for key, value in row.items()
    }


def load_constraint_cases(
    path: str | Path,
    *,
    allow_unvalidated: bool = False,
) -> tuple[ConstraintCase, ...]:
    rows = read_worksheet(path, "Annotations")
    cases: list[ConstraintCase] = []
    for row_number, raw_row in enumerate(rows, start=2):
        row = _normalized_keys(raw_row)
        status = _clean(row.get("review_status")) or "Needs Review"
        if status.casefold() == "excluded":
            continue
        if status.casefold() != "validated" and not allow_unvalidated:
            continue
        categories = tuple(
            dict.fromkeys(
                category
                for index in range(1, 7)
                if (category := _clean(row.get(f"gold_category_{index}")))
            )
        )
        if not categories:
            raise ValueError(f"constraint benchmark row {row_number} has no categories")
        query = _clean(row.get("query"))
        if not query:
            raise ValueError(f"constraint benchmark row {row_number} has no query")
        cases.append(
            ConstraintCase(
                query_id=_clean(row.get("id")) or str(row_number - 1),
                query=query,
                structured_constraints=_clean(row.get("structured_constraints")),
                gold_categories=categories,
                review_status=status,
            )
        )
    if not cases:
        qualifier = "including provisional rows" if allow_unvalidated else "marked Validated"
        raise ValueError(f"constraint benchmark contains no cases {qualifier}")
    return tuple(cases)


def structured_constraint_map(value: str) -> dict[str, str]:
    constraints: dict[str, str] = {}
    for part in value.split("|"):
        key, separator, raw_value = part.partition(":")
        if separator and key.strip():
            constraints[key.strip()] = raw_value.strip()
    return constraints


def location_expectation(structured_constraints: str) -> LocationExpectation:
    raw = structured_constraint_map(structured_constraints).get("Location", "")
    normalized = normalize_text(raw)
    zipcode_match = re.search(r"\b\d{5}\b", raw)
    if zipcode_match:
        return LocationExpectation(raw=raw, zipcode=zipcode_match.group(0))
    if normalized in {"kansas", "rural kansas"}:
        return LocationExpectation(raw=raw, state="KS", area=normalized == "rural kansas")

    parenthetical_county = re.fullmatch(r"(.+?)\s*\((.+?)\s+county\)", raw, re.IGNORECASE)
    if parenthetical_county:
        return LocationExpectation(
            raw=raw,
            city=parenthetical_county.group(1).strip(),
            county=parenthetical_county.group(2).strip(),
        )
    county_match = re.fullmatch(r"(.+?)\s+county", raw, re.IGNORECASE)
    if county_match:
        return LocationExpectation(raw=raw, county=county_match.group(1).strip())
    area = normalized.endswith(" area")
    city = re.sub(r"\s+area$", "", raw, flags=re.IGNORECASE).strip()
    return LocationExpectation(raw=raw, city=city, area=area)


def temporal_expectation(query: str, structured_constraints: str) -> TemporalExpectation:
    normalized_query = normalize_text(query)
    structured = structured_constraint_map(structured_constraints)
    constraint_value = normalize_text(structured.get("Constraint", ""))
    if "weekend hours" in constraint_value:
        return TemporalExpectation(weekend=True)

    day = next(
        (canonical for alias, canonical in DAY_NAMES.items() if re.search(rf"\b{alias}\b", normalized_query)),
        "",
    )
    time_match = TIME_PATTERN.search(query)
    open_at = ""
    if time_match:
        minutes = parse_clock(time_match.group(1))
        if minutes is not None:
            open_at = f"{minutes // 60:02d}:{minutes % 60:02d}"
    relative = next(
        (term for term in ("today", "tonight", "right away", "immediate") if term in normalized_query),
        "",
    )
    return TemporalExpectation(day=day, open_at=open_at, relative_time=relative)


def evaluate_location(provider: ServiceProvider, expected: LocationExpectation) -> tuple[str, str]:
    if not expected.raw:
        return "Not Applicable", "No gold location constraint."
    if expected.zipcode:
        if provider.zipcode == expected.zipcode:
            return "Satisfied", f"Provider ZIP {provider.zipcode} matches."
        return "Unknown", "Mailing ZIP differs; service area is unavailable."
    if expected.state:
        if provider.state.casefold() == expected.state.casefold():
            return "Satisfied", f"Provider mailing state is {provider.state}."
        return "Unknown", "Provider service area/statewide availability is unavailable."
    if expected.city and normalize_location(provider.city) == normalize_location(expected.city):
        return "Satisfied", f"Provider city {provider.city} matches."
    if expected.county and normalize_location(provider.county) == normalize_location(expected.county):
        return "Satisfied", f"Provider county {provider.county} matches."
    if expected.area and expected.city.casefold() == "wichita" and normalize_location(provider.county) == "sedgwick":
        return "Satisfied", "Provider is in Sedgwick County within the Wichita area."
    return "Unknown", "Mailing location differs; service area is unavailable."


def evaluate_hours(provider: ServiceProvider, expected: TemporalExpectation) -> tuple[str, str]:
    applicable = expected.day or expected.open_at or expected.weekend or expected.relative_time
    if not applicable:
        return "Not Applicable", "No gold temporal constraint."
    if expected.relative_time and not expected.day:
        return "Unknown", "Relative time lacks a benchmark date/day for verification."
    if not provider.hours:
        return "Unknown", "Provider hours are unavailable."
    if expected.weekend:
        satisfied = is_open(provider.hours, "saturday", None) or is_open(provider.hours, "sunday", None)
        return (
            ("Satisfied", "Provider has Saturday or Sunday hours.")
            if satisfied
            else ("Violated", "Published hours show no weekend availability.")
        )
    if expected.day:
        satisfied = is_open(provider.hours, expected.day, expected.open_at or None)
        label = expected.day + (f" at {expected.open_at}" if expected.open_at else "")
        return (
            ("Satisfied", f"Published hours support {label}.")
            if satisfied
            else ("Violated", f"Published hours do not support {label}.")
        )
    return "Unknown", "Time was found without a verifiable day."


def _semantic_constraints(structured_constraints: str) -> str:
    values = structured_constraint_map(structured_constraints)
    return " | ".join(f"{key}: {value}" for key, value in values.items() if key != "Location")


def evaluate_constraint_retrieval(
    providers: tuple[ServiceProvider, ...],
    cases: tuple[ConstraintCase, ...],
    *,
    variant: str = "kg3",
    limit: int = 3,
    category_classifier: CategoryClassifier | None = None,
    classifier_name: str = "deterministic",
) -> dict[str, Any]:
    engine = TraceEngine(
        providers,
        variant=variant,
        category_classifier=category_classifier,
    )
    provider_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    query_latencies: list[float] = []
    category_sources: Counter[str] = Counter()

    for case in cases:
        started = time.perf_counter()
        result = engine.recommend(case.query, limit=limit)
        query_latency = time.perf_counter() - started
        query_latencies.append(query_latency)
        category_sources[result.constraints.category_source] += 1
        expected_location = location_expectation(case.structured_constraints)
        expected_time = temporal_expectation(case.query, case.structured_constraints)
        covered_categories: set[str] = set()
        strict_candidates = 0
        no_violation_candidates = 0

        for rank, item in enumerate(result.recommendations, start=1):
            provider = item.provider
            category_status = (
                "Satisfied" if provider.category in case.gold_categories else "Violated"
            )
            if category_status == "Satisfied":
                covered_categories.add(provider.category)
            location_status, location_evidence = evaluate_location(provider, expected_location)
            hours_status, hours_evidence = evaluate_hours(provider, expected_time)
            applicable = [category_status, location_status, hours_status]
            applicable = [status for status in applicable if status != "Not Applicable"]
            hard_status = (
                "Violated"
                if "Violated" in applicable
                else "Strictly Satisfied"
                if applicable and all(status == "Satisfied" for status in applicable)
                else "No Known Violation"
            )
            if hard_status == "Strictly Satisfied":
                strict_candidates += 1
            if hard_status != "Violated":
                no_violation_candidates += 1

            provider_rows.append(
                {
                    "query_id": case.query_id,
                    "query": case.query,
                    "structured_constraints": case.structured_constraints,
                    "gold_categories": "; ".join(case.gold_categories),
                    "rank": rank,
                    "provider_id": provider.provider_id,
                    "provider_name": provider.name,
                    "organization": provider.organization,
                    "provider_category": provider.category,
                    "address": provider.address,
                    "city": provider.city,
                    "county": provider.county,
                    "zipcode": provider.zipcode,
                    "phone": provider.phone,
                    "hours": provider.hours,
                    "description": provider.description,
                    "eligibility": provider.eligibility,
                    "fees": provider.fees,
                    "application_process": provider.application_process,
                    "source_url": provider.source_url,
                    "category_status": category_status,
                    "location_status": location_status,
                    "location_evidence": location_evidence,
                    "hours_status": hours_status,
                    "hours_evidence": hours_evidence,
                    "automated_hard_status": hard_status,
                    "semantic_constraints": _semantic_constraints(case.structured_constraints),
                    "semantic_status": "Needs Review",
                    "service_area_status": "Needs Review" if location_status == "Unknown" else location_status,
                    "human_relevance_grade": "",
                    "human_review_status": "Needs Review",
                    "reviewer_notes": "",
                }
            )

        coverage = len(covered_categories) / len(case.gold_categories) if case.gold_categories else 1.0
        query_rows.append(
            {
                "query_id": case.query_id,
                "query": case.query,
                "gold_categories": "; ".join(case.gold_categories),
                "structured_constraints": case.structured_constraints,
                "annotation_status": case.review_status,
                "parsed_categories": "; ".join(result.constraints.categories),
                "category_source": result.constraints.category_source,
                "category_evidence": "; ".join(result.constraints.category_evidence),
                "parsed_city": result.constraints.city or "",
                "parsed_county": result.constraints.county or "",
                "parsed_zipcode": result.constraints.zipcode or "",
                "clarification": result.clarification or "",
                "returned_providers": len(result.recommendations),
                "categories_covered": "; ".join(sorted(covered_categories)),
                "need_coverage_at_k": coverage,
                "full_need_coverage": coverage == 1.0,
                "strict_candidates": strict_candidates,
                "no_violation_candidates": no_violation_candidates,
                "strict_query_success": strict_candidates > 0,
                "no_known_violation_success": no_violation_candidates > 0,
                "query_latency_seconds": query_latency,
            }
        )

    recommendations = len(provider_rows)
    category_satisfied = sum(row["category_status"] == "Satisfied" for row in provider_rows)
    strict = sum(row["automated_hard_status"] == "Strictly Satisfied" for row in provider_rows)
    no_violation = sum(row["automated_hard_status"] != "Violated" for row in provider_rows)
    location_applicable = [row for row in provider_rows if row["location_status"] != "Not Applicable"]
    hours_applicable = [row for row in provider_rows if row["hours_status"] != "Not Applicable"]
    metrics = {
        "classifier": classifier_name,
        "variant": variant,
        "k": limit,
        "queries": len(query_rows),
        "recommendations": recommendations,
        "mean_recommendations_per_query": recommendations / len(query_rows) if query_rows else 0.0,
        "provider_category_satisfaction_rate": category_satisfied / recommendations if recommendations else 0.0,
        "provider_strict_hard_satisfaction_rate": strict / recommendations if recommendations else 0.0,
        "provider_no_known_violation_rate": no_violation / recommendations if recommendations else 0.0,
        "exact_location_confirmation_rate": (
            sum(row["location_status"] == "Satisfied" for row in location_applicable) / len(location_applicable)
            if location_applicable else None
        ),
        "location_unknown_rate": (
            sum(row["location_status"] == "Unknown" for row in location_applicable) / len(location_applicable)
            if location_applicable else None
        ),
        "hours_constraint_recommendations": len(hours_applicable),
        "hours_satisfaction_rate": (
            sum(row["hours_status"] == "Satisfied" for row in hours_applicable) / len(hours_applicable)
            if hours_applicable else None
        ),
        "hours_unknown_rate": (
            sum(row["hours_status"] == "Unknown" for row in hours_applicable) / len(hours_applicable)
            if hours_applicable else None
        ),
        "mean_need_coverage_at_k": sum(row["need_coverage_at_k"] for row in query_rows) / len(query_rows),
        "full_need_coverage_rate": sum(row["full_need_coverage"] for row in query_rows) / len(query_rows),
        "strict_query_success_rate": sum(row["strict_query_success"] for row in query_rows) / len(query_rows),
        "no_known_violation_query_success_rate": (
            sum(row["no_known_violation_success"] for row in query_rows) / len(query_rows)
        ),
        "no_result_rate": sum(row["returned_providers"] == 0 for row in query_rows) / len(query_rows),
        "clarification_rate": sum(bool(row["clarification"]) for row in query_rows) / len(query_rows),
        "semantic_review_required": recommendations,
        "mean_query_latency_seconds": (
            statistics.fmean(query_latencies) if query_latencies else 0.0
        ),
        "median_query_latency_seconds": (
            statistics.median(query_latencies) if query_latencies else 0.0
        ),
        "p95_query_latency_seconds": (
            sorted(query_latencies)[max(0, int(0.95 * len(query_latencies)) - 1)]
            if query_latencies else 0.0
        ),
        "category_source_counts": dict(sorted(category_sources.items())),
    }
    return {
        "metrics": metrics,
        "query_rows": query_rows,
        "provider_rows": provider_rows,
    }


def write_constraint_evaluation(result: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
