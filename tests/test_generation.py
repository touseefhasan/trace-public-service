from __future__ import annotations

import unittest

from trace_engine.engine import TraceEngine
from trace_engine.generation import (
    GeneratedAnswer,
    OllamaResponseGenerator,
    deterministic_chat_answer,
)
from trace_engine.models import Recommendation, ServiceProvider


def recommendation() -> Recommendation:
    return Recommendation(
        provider=ServiceProvider(
            provider_id="provider-1",
            name="Wichita Community Shelter",
            organization="Community Services",
            category="Housing & Shelter",
            address="100 Main St, Wichita, KS 67202",
            city="Wichita",
            county="Sedgwick",
            zipcode="67202",
            phone="316-555-0100",
            hours="Mon-Fri 8:00 AM-5:00 PM",
            source_url="https://example.org/shelter",
        ),
        matched_constraints=("city=Wichita",),
        supporting_evidence=(),
        score=1.0,
    )


class StubGenerator:
    def generate(self, query, recommendations):
        return GeneratedAnswer("A grounded conversational answer.", "stub")


class FailingGenerator:
    def generate(self, query, recommendations):
        raise RuntimeError("model unavailable")


class GenerationTests(unittest.TestCase):
    def test_deterministic_answer_preserves_provider_facts(self) -> None:
        item = recommendation()
        answer = deterministic_chat_answer((item,)).text
        for value in (
            item.provider.name,
            item.provider.provider_id,
            item.provider.organization,
            item.provider.category,
            item.provider.address,
            item.provider.phone,
            item.provider.hours,
            item.provider.source_url,
        ):
            self.assertIn(value, answer)

    def test_grounding_validator_rejects_omitted_facts(self) -> None:
        with self.assertRaises(RuntimeError):
            OllamaResponseGenerator._validate_grounding(
                "Wichita Community Shelter may help.", (recommendation(),)
            )

    def test_engine_surfaces_generated_answer(self) -> None:
        provider = recommendation().provider
        result = TraceEngine(
            (provider,), response_generator=StubGenerator()
        ).recommend("I need shelter in Wichita")
        self.assertEqual(result.answer, "A grounded conversational answer.")
        self.assertEqual(result.response_source, "stub")

    def test_engine_falls_back_to_grounded_chat(self) -> None:
        provider = recommendation().provider
        result = TraceEngine(
            (provider,), response_generator=FailingGenerator()
        ).recommend("I need shelter in Wichita")
        self.assertEqual(result.response_source, "deterministic_fallback")
        self.assertIn(provider.name, result.answer)
        self.assertIn(provider.phone, result.answer)
        self.assertIn(provider.provider_id, result.answer)
        self.assertEqual(result.response_error, "model unavailable")


if __name__ == "__main__":
    unittest.main()
