from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from .models import Recommendation


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    text: str
    source: str


class ResponseGenerator(Protocol):
    def generate(
        self, query: str, recommendations: tuple[Recommendation, ...]
    ) -> GeneratedAnswer: ...


def deterministic_chat_answer(
    recommendations: tuple[Recommendation, ...],
) -> GeneratedAnswer:
    """Render retrieved records conversationally without changing their facts."""
    if not recommendations:
        return GeneratedAnswer(
            "I couldn't find a matching provider in the current directory. "
            "You could try a nearby city, county, or ZIP code.",
            "deterministic",
        )

    count = len(recommendations)
    noun = "option" if count == 1 else "options"
    paragraphs = [f"I found {count} {noun} that may help:"]
    for item in recommendations:
        provider = item.provider
        details = [f"Provider ID: {provider.provider_id}"]
        if provider.category:
            details.append(f"Category: {provider.category}")
        if provider.organization and provider.organization != provider.name:
            details.append(f"Organization: {provider.organization}")
        if provider.address:
            details.append(f"Address: {provider.address}")
        location = ", ".join(
            value for value in (provider.city, provider.county, provider.zipcode) if value
        )
        if location:
            details.append(f"Location: {location}")
        if provider.phone:
            details.append(f"Phone: {provider.phone}")
        if provider.hours:
            details.append(f"Hours: {provider.hours}")
        if provider.source_url:
            details.append(f"Source: {provider.source_url}")
        detail_text = ". ".join(details)
        paragraphs.append(
            f"{provider.name}. {detail_text}." if detail_text else f"{provider.name}."
        )

    paragraphs.append(
        "Please contact the provider to confirm its hours, availability, and eligibility before visiting."
    )
    return GeneratedAnswer("\n\n".join(paragraphs), "deterministic")


class OllamaResponseGenerator:
    """Turn final retrieved records into prose while enforcing factual grounding."""

    def __init__(
        self,
        *,
        model: str = "qwen3.5:4b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self, query: str, recommendations: tuple[Recommendation, ...]
    ) -> GeneratedAnswer:
        if not recommendations:
            return deterministic_chat_answer(recommendations)

        records = [
            {
                "name": item.provider.name,
                "provider_id": item.provider.provider_id,
                "organization": item.provider.organization,
                "category": item.provider.category,
                "address": item.provider.address,
                "city": item.provider.city,
                "county": item.provider.county,
                "zipcode": item.provider.zipcode,
                "phone": item.provider.phone,
                "hours": item.provider.hours,
                "source_url": item.provider.source_url,
            }
            for item in recommendations
        ]
        prompt = (
            "Write a concise, helpful chat-style response to the user's service request. "
            "Use only the provider records below. Mention every provider in the given order. "
            "Copy every non-empty factual value exactly, including names, provider IDs, categories, addresses, "
            "locations, phone numbers, hours, and source URLs. Do not add facts, infer eligibility, "
            "or claim that a provider is currently available. Omit labels whose values are empty. "
            "End by advising the user to confirm hours, availability, and eligibility before visiting.\n\n"
            f"User request: {query}\n"
            f"Provider records: {json.dumps(records, ensure_ascii=False)}"
        )
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a grounded public-service directory assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0, "num_predict": 1024},
        }
        api_request = request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(api_request, timeout=self.timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama response generation failed: {exc}") from exc

        message = response_payload.get("message")
        answer = message.get("content", "").strip() if isinstance(message, dict) else ""
        if not answer:
            raise RuntimeError("Ollama returned an empty response")
        self._validate_grounding(answer, recommendations)
        return GeneratedAnswer(answer, f"ollama:{self.model}")

    @staticmethod
    def _validate_grounding(
        answer: str, recommendations: tuple[Recommendation, ...]
    ) -> None:
        """Reject prose that drops any provider fact supplied to the model."""
        for item in recommendations:
            provider = item.provider
            required_values = (
                provider.name,
                provider.provider_id,
                provider.organization,
                provider.category,
                provider.address,
                provider.city,
                provider.county,
                provider.zipcode,
                provider.phone,
                provider.hours,
                provider.source_url,
            )
            missing = [value for value in required_values if value and value not in answer]
            if missing:
                raise RuntimeError(
                    "Generated response omitted or changed retrieved facts: "
                    + ", ".join(missing)
                )
