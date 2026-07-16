from __future__ import annotations

from dataclasses import dataclass

from .models import Pantry
from .normalization import normalize_text, tokenize


@dataclass(frozen=True, slots=True)
class SemanticMatch:
    satisfied: bool
    evidence: tuple[str, ...]


def check_semantic_constraints(pantry: Pantry, constraints: tuple[str, ...]) -> SemanticMatch:
    if not constraints:
        return SemanticMatch(True, ())

    eligibility = normalize_text(pantry.eligibility)
    evidence: list[str] = []
    for constraint in constraints:
        if constraint == "no id required":
            matched = any(
                phrase in eligibility
                for phrase in ("no id required", "id not required", "without identification")
            )
        elif constraint == "id required":
            negated = any(phrase in eligibility for phrase in ("no id", "id not required"))
            matched = not negated and any(
                phrase in eligibility
                for phrase in ("id required", "identification required", "bring id", "photo id")
            )
        else:
            query_tokens = tokenize(constraint)
            matched = bool(query_tokens) and query_tokens <= tokenize(eligibility)

        if not matched:
            return SemanticMatch(False, tuple(evidence))
        evidence.append(pantry.eligibility)
    return SemanticMatch(True, tuple(dict.fromkeys(evidence)))
