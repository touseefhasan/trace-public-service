from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Pantry:
    """A normalized provider record retained alongside its source provenance."""

    provider_id: str
    name: str
    address: str
    city: str
    county: str
    zipcode: str
    phone: str = ""
    hours: str = ""
    eligibility: str = ""
    source_url: str = ""
    last_verified_at: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.name,
                self.address,
                self.city,
                self.county,
                self.zipcode,
                self.hours,
                self.eligibility,
            )
        )


@dataclass(frozen=True, slots=True)
class QueryConstraints:
    city: str | None = None
    county: str | None = None
    zipcode: str | None = None
    provider_name: str | None = None
    day: str | None = None
    open_at: str | None = None
    semantic: tuple[str, ...] = ()

    @property
    def has_retrieval_anchor(self) -> bool:
        """Whether the query identifies a geographic area or named provider."""
        return any((self.city, self.county, self.zipcode, self.provider_name))

    @property
    def has_structural_constraint(self) -> bool:
        return any(
            (
                self.city,
                self.county,
                self.zipcode,
                self.provider_name,
                self.day,
                self.open_at,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic"] = list(self.semantic)
        return value


@dataclass(frozen=True, slots=True)
class Recommendation:
    provider: Pantry
    matched_constraints: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.as_dict(),
            "matched_constraints": list(self.matched_constraints),
            "supporting_evidence": list(self.supporting_evidence),
            "score": round(self.score, 6),
        }


@dataclass(frozen=True, slots=True)
class TraceResult:
    query: str
    variant: str
    constraints: QueryConstraints
    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)
    clarification: str | None = None
    candidates_examined: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "variant": self.variant,
            "constraints": self.constraints.as_dict(),
            "clarification": self.clarification,
            "candidates_examined": self.candidates_examined,
            "recommendations": [item.as_dict() for item in self.recommendations],
        }
