from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .knowledge_graph import KnowledgeGraphQuery, PropertyGraph, build_knowledge_graph
from .models import QueryConstraints, ServiceProvider
from .normalization import is_open, normalize_location, normalize_text, tokenize


VARIANT_FIELDS = {
    "kg0": frozenset(),
    "kg1": frozenset({"provider_name", "city", "county", "zipcode", "category"}),
    "kg2": frozenset({"provider_name", "day", "open_at"}),
    "kg3": frozenset(
        {
            "provider_name",
            "city",
            "county",
            "zipcode",
            "category",
            "day",
            "open_at",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    provider: ServiceProvider
    score: float
    matched_constraints: tuple[str, ...]


class DirectoryRetriever:
    def __init__(self, providers: Sequence[ServiceProvider], variant: str) -> None:
        if variant not in VARIANT_FIELDS:
            raise ValueError(f"unknown retrieval variant: {variant}")
        self.providers = tuple(providers)
        self.variant = variant
        self.exact_fields = VARIANT_FIELDS[variant]
        self.record_tokens = {
            provider.provider_id: frozenset(tokenize(provider.searchable_text))
            for provider in self.providers
        }
        self.graph: PropertyGraph | None = (
            build_knowledge_graph(self.providers, variant) if variant != "kg0" else None
        )
        self.graph_query = KnowledgeGraphQuery(self.graph) if self.graph else None

    @staticmethod
    def _constraint_labels(
        provider: ServiceProvider, constraints: QueryConstraints
    ) -> tuple[str, ...]:
        labels: list[str] = []
        if constraints.provider_name and normalize_text(provider.name) == normalize_text(
            constraints.provider_name
        ):
            labels.append(f"name={provider.name}")
        if constraints.city and normalize_location(provider.city) == normalize_location(
            constraints.city
        ):
            labels.append(f"city={provider.city}")
        if constraints.county and normalize_location(provider.county) == normalize_location(
            constraints.county
        ):
            labels.append(f"county={provider.county}")
        if constraints.zipcode and provider.zipcode == constraints.zipcode:
            labels.append(f"zipcode={provider.zipcode}")
        if constraints.categories and normalize_text(provider.category) in {
            normalize_text(category) for category in constraints.categories
        }:
            labels.append(f"category={provider.category}")
        if constraints.day and is_open(provider.hours, constraints.day, constraints.open_at):
            label = f"open={constraints.day}"
            if constraints.open_at:
                label += f"@{constraints.open_at}"
            labels.append(label)
        return tuple(labels)

    def _text_score(
        self, query_tokens: set[str], provider: ServiceProvider
    ) -> float:
        if not query_tokens:
            return 0.0
        record_tokens = self.record_tokens[provider.provider_id]
        name_overlap = len(query_tokens & tokenize(provider.name))
        category_overlap = len(query_tokens & tokenize(provider.category))
        record_overlap = len(query_tokens & record_tokens)
        return (3 * name_overlap + 2 * category_overlap + record_overlap) / len(
            query_tokens
        )

    @staticmethod
    def _category_diversified(
        ranked: list[RankedCandidate], categories: tuple[str, ...]
    ) -> list[RankedCandidate]:
        """Place the best candidate for each requested category before extras."""
        if len(categories) < 2:
            return ranked
        selected: list[RankedCandidate] = []
        selected_ids: set[str] = set()
        for category in categories:
            normalized_category = normalize_text(category)
            candidate = next(
                (
                    item
                    for item in ranked
                    if item.provider.provider_id not in selected_ids
                    and normalize_text(item.provider.category) == normalized_category
                ),
                None,
            )
            if candidate is not None:
                selected.append(candidate)
                selected_ids.add(candidate.provider.provider_id)
        return selected + [
            item for item in ranked if item.provider.provider_id not in selected_ids
        ]

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
                provider=provider,
                score=self._text_score(query_tokens, provider),
                matched_constraints=self._constraint_labels(provider, constraints),
            )
            for provider in self.providers
            if allowed_ids is None or provider.provider_id in allowed_ids
        ]
        ranked.sort(key=lambda item: (-item.score, item.provider.name.casefold()))
        ranked = self._category_diversified(ranked, constraints.categories)
        return tuple(ranked[offset : offset + limit])
