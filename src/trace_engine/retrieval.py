from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .knowledge_graph import KnowledgeGraphQuery, PropertyGraph, build_knowledge_graph
from .models import Pantry, QueryConstraints
from .normalization import is_open, normalize_location, normalize_text, tokenize


VARIANT_FIELDS = {
    "kg0": frozenset(),
    "kg1": frozenset({"provider_name", "city", "county", "zipcode"}),
    "kg2": frozenset({"provider_name", "day", "open_at"}),
    "kg3": frozenset(
        {"provider_name", "city", "county", "zipcode", "day", "open_at"}
    ),
}


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    provider: Pantry
    score: float
    matched_constraints: tuple[str, ...]


class DirectoryRetriever:
    def __init__(self, providers: Sequence[Pantry], variant: str) -> None:
        if variant not in VARIANT_FIELDS:
            raise ValueError(f"unknown retrieval variant: {variant}")
        self.providers = tuple(providers)
        self.variant = variant
        self.exact_fields = VARIANT_FIELDS[variant]
        self.record_tokens = {
            pantry.provider_id: frozenset(tokenize(pantry.searchable_text))
            for pantry in self.providers
        }
        self.graph: PropertyGraph | None = (
            build_knowledge_graph(self.providers, variant) if variant != "kg0" else None
        )
        self.graph_query = KnowledgeGraphQuery(self.graph) if self.graph else None

    @staticmethod
    def _constraint_labels(pantry: Pantry, constraints: QueryConstraints) -> tuple[str, ...]:
        labels: list[str] = []
        if constraints.provider_name and normalize_text(pantry.name) == normalize_text(
            constraints.provider_name
        ):
            labels.append(f"name={pantry.name}")
        if constraints.city and normalize_location(pantry.city) == normalize_location(constraints.city):
            labels.append(f"city={pantry.city}")
        if constraints.county and normalize_location(pantry.county) == normalize_location(
            constraints.county
        ):
            labels.append(f"county={pantry.county}")
        if constraints.zipcode and pantry.zipcode == constraints.zipcode:
            labels.append(f"zipcode={pantry.zipcode}")
        if constraints.day and is_open(pantry.hours, constraints.day, constraints.open_at):
            label = f"open={constraints.day}"
            if constraints.open_at:
                label += f"@{constraints.open_at}"
            labels.append(label)
        return tuple(labels)

    def _text_score(self, query_tokens: set[str], pantry: Pantry) -> float:
        if not query_tokens:
            return 0.0
        record_tokens = self.record_tokens[pantry.provider_id]
        overlap = len(query_tokens & record_tokens)
        return overlap / len(query_tokens)

    def retrieve(
        self,
        query: str,
        constraints: QueryConstraints,
        *,
        limit: int,
        offset: int = 0,
    ) -> tuple[RankedCandidate, ...]:
        query_tokens = tokenize(query)
        allowed_ids = (
            self.graph_query.candidate_provider_ids(constraints, self.exact_fields)
            if self.graph_query
            else None
        )
        ranked = [
            RankedCandidate(
                provider=pantry,
                score=self._text_score(query_tokens, pantry),
                matched_constraints=self._constraint_labels(pantry, constraints),
            )
            for pantry in self.providers
            if allowed_ids is None or pantry.provider_id in allowed_ids
        ]
        ranked.sort(key=lambda item: (-item.score, item.provider.name.casefold()))
        return tuple(ranked[offset : offset + limit])
