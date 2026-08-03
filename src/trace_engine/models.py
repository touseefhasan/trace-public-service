from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ServiceProvider:
    """A normalized public-service listing retained with source provenance."""

    provider_id: str
    name: str
    address: str = ""
    city: str = ""
    county: str = ""
    zipcode: str = ""
    organization: str = ""
    description: str = ""
    category: str = ""
    state: str = ""
    phone: str = ""
    email: str = ""
    hours: str = ""
    eligibility: str = ""
    application_process: str = ""
    required_documents: str = ""
    fees: str = ""
    source_url: str = ""
    last_verified_at: str = ""
    location_source: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.name,
                self.organization,
                self.description,
                self.category,
                self.address,
                self.city,
                self.state,
                self.county,
                self.zipcode,
                self.phone,
                self.email,
                self.hours,
                self.eligibility,
                self.application_process,
                self.required_documents,
                self.fees,
            )
        )


# Backward-compatible import for existing callers and published examples.
Pantry = ServiceProvider


@dataclass(frozen=True, slots=True)
class QueryConstraints:
    city: str | None = None
    county: str | None = None
    zipcode: str | None = None
    provider_name: str | None = None
    category: str | None = None
    categories: tuple[str, ...] = ()
    category_source: str = "deterministic"
    category_evidence: tuple[str, ...] = ()
    day: str | None = None
    open_at: str | None = None
    semantic: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        categories = tuple(dict.fromkeys(item for item in self.categories if item))
        if self.category and not categories:
            categories = (self.category,)
        if categories and not self.category:
            object.__setattr__(self, "category", categories[0])
        object.__setattr__(self, "categories", categories)

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
                self.categories,
                self.day,
                self.open_at,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["semantic"] = list(self.semantic)
        value["categories"] = list(self.categories)
        value["category_evidence"] = list(self.category_evidence)
        return value


@dataclass(frozen=True, slots=True)
class Recommendation:
    provider: ServiceProvider
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
    answer: str | None = None
    response_source: str | None = None
    response_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "variant": self.variant,
            "constraints": self.constraints.as_dict(),
            "clarification": self.clarification,
            "candidates_examined": self.candidates_examined,
            "answer": self.answer,
            "response_source": self.response_source,
            "response_error": self.response_error,
            "recommendations": [item.as_dict() for item in self.recommendations],
        }
