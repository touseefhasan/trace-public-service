from __future__ import annotations

from collections.abc import Sequence

from .constraints import ConstraintParser
from .generation import GeneratedAnswer, ResponseGenerator, deterministic_chat_answer
from .intent import CategoryClassifier
from .models import QueryConstraints, Recommendation, ServiceProvider, TraceResult
from .retrieval import DirectoryRetriever
from .semantic import check_semantic_constraints


LOCATION_CLARIFICATION = (
    "Where are you looking for services? Please provide a city, county, or ZIP code."
)


def clarification_for(constraints: QueryConstraints) -> str | None:
    if not constraints.has_retrieval_anchor:
        if constraints.categories == ("Food",):
            return (
                "Where are you looking for food? "
                "Please provide a city, county, or ZIP code."
            )
        if constraints.categories:
            services = " or ".join(constraints.categories)
            return (
                f"Where are you looking for {services} services? "
                "Please provide a city, county, or ZIP code."
            )
        return LOCATION_CLARIFICATION
    if constraints.open_at and not constraints.day:
        return f"Which day should I check for availability at {constraints.open_at}?"
    return None


class TraceEngine:
    def __init__(
        self,
        providers: Sequence[ServiceProvider],
        variant: str = "kg3",
        *,
        category_classifier: CategoryClassifier | None = None,
        response_generator: ResponseGenerator | None = None,
    ) -> None:
        self.providers = tuple(providers)
        self.variant = variant
        self.parser = ConstraintParser(
            self.providers, category_classifier=category_classifier
        )
        self.retriever = DirectoryRetriever(self.providers, variant)
        self.response_generator = response_generator

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
        clarification = clarification_for(constraints)
        if clarification:
            return TraceResult(
                query=query,
                variant=self.variant,
                constraints=constraints,
                clarification=clarification,
                answer=clarification if self.response_generator else None,
                response_source="deterministic" if self.response_generator else None,
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

        recommendation_tuple = tuple(recommendations)
        answer = None
        response_source = None
        response_error = None
        if self.response_generator:
            try:
                generated = self.response_generator.generate(query, recommendation_tuple)
            except RuntimeError as exc:
                generated = deterministic_chat_answer(recommendation_tuple)
                generated = GeneratedAnswer(generated.text, "deterministic_fallback")
                response_error = str(exc)
            answer = generated.text
            response_source = generated.source

        return TraceResult(
            query=query,
            variant=self.variant,
            constraints=constraints,
            recommendations=recommendation_tuple,
            candidates_examined=examined,
            answer=answer,
            response_source=response_source,
            response_error=response_error,
        )
