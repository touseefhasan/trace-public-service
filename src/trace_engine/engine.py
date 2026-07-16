from __future__ import annotations

from collections.abc import Sequence

from .constraints import ConstraintParser
from .models import Pantry, Recommendation, TraceResult
from .retrieval import DirectoryRetriever
from .semantic import check_semantic_constraints


CLARIFICATION = "What nearby ZIP code, city, county, pantry name, or operating day should I use?"


class TraceEngine:
    def __init__(self, providers: Sequence[Pantry], variant: str = "kg3") -> None:
        self.providers = tuple(providers)
        self.variant = variant
        self.parser = ConstraintParser(self.providers)
        self.retriever = DirectoryRetriever(self.providers, variant)

    def recommend(
        self,
        query: str,
        *,
        limit: int = 3,
        batch_size: int = 3,
        max_batches: int = 20,
    ) -> TraceResult:
        if limit < 1 or batch_size < 1 or max_batches < 1:
            raise ValueError("limit, batch_size, and max_batches must be positive")

        constraints = self.parser.parse(query)
        if not constraints.has_structural_constraint:
            return TraceResult(
                query=query,
                variant=self.variant,
                constraints=constraints,
                clarification=CLARIFICATION,
            )

        recommendations: list[Recommendation] = []
        examined = 0
        for batch_index in range(max_batches):
            candidates = self.retriever.retrieve(
                query,
                constraints,
                limit=batch_size,
                offset=batch_index * batch_size,
            )
            if not candidates:
                break
            examined += len(candidates)
            for candidate in candidates:
                semantic = check_semantic_constraints(candidate.provider, constraints.semantic)
                if not semantic.satisfied:
                    continue
                evidence = list(semantic.evidence)
                if candidate.provider.hours and constraints.day:
                    evidence.append(candidate.provider.hours)
                recommendations.append(
                    Recommendation(
                        provider=candidate.provider,
                        matched_constraints=candidate.matched_constraints + constraints.semantic,
                        supporting_evidence=tuple(dict.fromkeys(evidence)),
                        score=candidate.score,
                    )
                )
                if len(recommendations) == limit:
                    break
            if len(recommendations) == limit:
                break

        return TraceResult(
            query=query,
            variant=self.variant,
            constraints=constraints,
            recommendations=tuple(recommendations),
            candidates_examined=examined,
        )
