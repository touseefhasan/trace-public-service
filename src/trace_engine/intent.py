from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from .normalization import normalize_text


CATEGORY_ALIASES = {
    "Housing & Shelter": (
        "shelter",
        "shelters",
        "housing",
        "homeless",
        "homelessness",
        "rent assistance",
        "rental assistance",
    ),
    "Food": (
        "food",
        "food pantry",
        "food bank",
        "groceries",
        "grocery",
        "meal",
        "meals",
        "soup kitchen",
        "wic",
    ),
    "Health & Dental Care": (
        "health care",
        "healthcare",
        "medical",
        "dental",
        "dentist",
        "clinic",
        "doctor",
        "prenatal",
        "vaccine",
        "vaccines",
        "vaccination",
        "vision",
        "cancer",
    ),
    "Employment & Education": (
        "employment",
        "job",
        "jobs",
        "job training",
        "education",
        "school",
        "training",
    ),
    "Mental Health & Addiction": (
        "mental health",
        "addiction",
        "substance use",
        "substance abuse",
        "recovery",
        "rehab",
        "counseling",
    ),
    "Family Support": (
        "family support",
        "child care",
        "childcare",
        "parenting",
        "youth services",
    ),
    "Seniors & Disability": (
        "senior",
        "seniors",
        "elderly",
        "disability",
        "disabled",
    ),
    "Legal & Money Management": (
        "legal",
        "lawyer",
        "attorney",
        "money management",
        "budgeting",
        "credit counseling",
    ),
    "Financial Assistance": (
        "financial assistance",
        "financial help",
        "bill assistance",
        "utility assistance",
        "cash assistance",
    ),
    "Clothing, Hygiene & Household Goods": (
        "clothing",
        "clothes",
        "hygiene",
        "household goods",
        "furniture",
    ),
    "Transportation": (
        "transportation",
        "transit",
        "bus",
        "ride",
        "rides",
        "flight",
    ),
    "Taxes": ("tax", "taxes", "tax preparation"),
}


@dataclass(frozen=True, slots=True)
class CategoryClassification:
    categories: tuple[str, ...]
    source: str
    evidence: tuple[str, ...] = ()


class CategoryClassifier(Protocol):
    def classify(
        self, query: str, available_categories: Sequence[str]
    ) -> CategoryClassification: ...


class DeterministicCategoryClassifier:
    """Multi-label keyword baseline retained for offline use and fallback."""

    def classify(
        self, query: str, available_categories: Sequence[str]
    ) -> CategoryClassification:
        available = {
            normalize_text(category): category for category in available_categories
        }
        normalized_query = normalize_text(query)
        padded = f" {normalized_query} "
        matches: list[tuple[int, int, str, str]] = []

        for normalized_category, original in available.items():
            position = padded.find(f" {normalized_category} ")
            if position >= 0:
                matches.append((position, -len(normalized_category), original, original))

        for category, aliases in CATEGORY_ALIASES.items():
            normalized_category = normalize_text(category)
            if normalized_category not in available:
                continue
            for alias in aliases:
                normalized_alias = normalize_text(alias)
                position = padded.find(f" {normalized_alias} ")
                if position >= 0:
                    matches.append(
                        (
                            position,
                            -len(normalized_alias),
                            available[normalized_category],
                            alias,
                        )
                    )

        matches.sort(key=lambda item: (item[0], item[1]))
        categories = tuple(dict.fromkeys(item[2] for item in matches))
        evidence = tuple(dict.fromkeys(item[3] for item in matches))
        return CategoryClassification(categories, "deterministic", evidence)


class OllamaCategoryClassifier:
    """Classify service needs with a local Ollama model and JSON Schema output."""

    def __init__(
        self,
        *,
        model: str = "qwen3.5:4b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _schema(categories: Sequence[str]) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(categories)},
                    "uniqueItems": True,
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["categories", "evidence"],
            "additionalProperties": False,
        }

    @staticmethod
    def _prompt(query: str, categories: Sequence[str]) -> str:
        category_list = "\n".join(f"- {category}" for category in categories)
        return f"""Classify the public services explicitly requested by the user.

Choose zero, one, or multiple labels only from this taxonomy:
{category_list}

Rules:
1. Select multiple labels when the user independently requests multiple services.
2. Classify the service being sought, not incidental context.
3. A ride, flight, bus, or transport to medical care is Transportation; add Health
   only if healthcare itself is also requested.
4. Prenatal care, vaccines, vision care, cancer treatment, and medical clinics are
   Health & Dental Care.
5. WIC can involve Food and Family Support; select labels supported by the wording.
6. Do not infer needs that are not present in the query.
7. Evidence must contain short phrases copied from the query that justify the labels.

Examples:
- "I need a ride to chemotherapy" -> ["Transportation"]
- "I need chemotherapy and a ride to the clinic" ->
  ["Health & Dental Care", "Transportation"]
- "I need transitional housing while recovering from addiction" ->
  ["Housing & Shelter", "Mental Health & Addiction"]
- "I need legal help finding work after prison" ->
  ["Legal & Money Management", "Employment & Education"]
- "My family needs internet and food assistance" ->
  ["Employment & Education", "Food"]

User query: {json.dumps(query, ensure_ascii=False)}
"""

    def classify(
        self, query: str, available_categories: Sequence[str]
    ) -> CategoryClassification:
        categories = tuple(dict.fromkeys(category for category in available_categories if category))
        if not categories:
            return CategoryClassification((), "ollama", ())

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise multi-label public-service intent classifier. "
                        "Return only data matching the supplied JSON schema."
                    ),
                },
                {
                    "role": "user",
                    "content": self._prompt(query, categories),
                },
            ],
            "format": self._schema(categories),
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_ctx": 2048,
                "num_predict": 128,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(api_request, timeout=self.timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Ollama category classification failed: {exc}") from exc

        message = response_payload.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise RuntimeError("Ollama returned no structured message content")
        try:
            classification = json.loads(message["content"])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid category JSON") from exc

        allowed = {normalize_text(category): category for category in categories}
        selected: list[str] = []
        for value in classification.get("categories", []):
            normalized = normalize_text(str(value))
            if normalized in allowed:
                selected.append(allowed[normalized])
        evidence = tuple(
            str(value).strip()
            for value in classification.get("evidence", [])
            if str(value).strip()
        )
        return CategoryClassification(
            tuple(dict.fromkeys(selected)),
            f"ollama:{self.model}",
            tuple(dict.fromkeys(evidence)),
        )
