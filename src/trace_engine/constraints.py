from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .models import QueryConstraints, ServiceProvider
from .normalization import (
    DAY_ALIASES,
    clock_label,
    normalize_location,
    normalize_text,
    parse_clock,
)


TIME_PATTERN = re.compile(
    r"\b(?:at|around|by)\s+(?P<time>\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
    flags=re.IGNORECASE,
)
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
    ),
    "Health & Dental Care": (
        "health care",
        "healthcare",
        "medical",
        "dental",
        "dentist",
        "clinic",
        "doctor",
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
    ),
    "Taxes": ("tax", "taxes", "tax preparation"),
}


class ConstraintParser:
    """A deterministic baseline parser designed to be replaceable by an LLM parser."""

    def __init__(self, providers: Sequence[ServiceProvider]) -> None:
        self.providers = tuple(providers)
        self.counties = self._choices(item.county for item in self.providers)
        self.cities = self._choices(item.city for item in self.providers)
        self.provider_names = self._choices(item.name for item in self.providers)
        self.categories = self._choices(item.category for item in self.providers)

    @staticmethod
    def _choices(values: Iterable[str]) -> tuple[tuple[str, str], ...]:
        unique = {str(value) for value in values if value}
        return tuple(
            sorted(
                ((normalize_text(value), value) for value in unique),
                key=lambda item: len(item[0]),
                reverse=True,
            )
        )

    @staticmethod
    def _contained(normalized_query: str, choices: tuple[tuple[str, str], ...]) -> str | None:
        padded = f" {normalized_query} "
        for normalized_choice, original in choices:
            if f" {normalized_choice} " in padded:
                return original
        return None

    def _category(self, normalized_query: str) -> str | None:
        explicit = self._contained(normalized_query, self.categories)
        if explicit:
            return explicit
        available = {
            normalize_text(original): original for _, original in self.categories
        }
        aliases = sorted(
            (
                (normalize_text(alias), normalize_text(category))
                for category, category_aliases in CATEGORY_ALIASES.items()
                for alias in category_aliases
            ),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        padded = f" {normalized_query} "
        for alias, normalized_category in aliases:
            if normalized_category in available and f" {alias} " in padded:
                return available[normalized_category]
        return None

    def parse(self, query: str) -> QueryConstraints:
        normalized = normalize_text(query)
        zipcode_match = re.search(r"\b\d{5}(?:-\d{4})?\b", query)
        zipcode = zipcode_match.group(0)[:5] if zipcode_match else None

        county = self._contained(normalized, self.counties)
        city = self._contained(normalized, self.cities)
        provider_name = self._contained(normalized, self.provider_names)
        category = self._category(normalized)
        if (
            city
            and county
            and normalize_location(city) == normalize_location(county)
        ):
            county_phrase = rf"\b{re.escape(normalize_location(county))}\s+county\b"
            city_phrase = rf"\b(?:city of|in the city of)\s+{re.escape(normalize_location(city))}\b"
            county_is_explicit = re.search(county_phrase, normalized) is not None
            city_is_explicit = re.search(city_phrase, normalized) is not None
            if county_is_explicit and not city_is_explicit:
                city = None
            elif city_is_explicit or not county_is_explicit:
                county = None

        day = None
        for alias, canonical in DAY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                day = canonical
                break

        open_at = None
        time_match = TIME_PATTERN.search(query)
        if time_match:
            minutes = parse_clock(time_match.group("time"))
            if minutes is not None:
                open_at = clock_label(minutes)

        semantic: list[str] = []
        if re.search(r"\b(?:without|no)\s+(?:an?\s+)?(?:id|identification)\b", normalized):
            semantic.append("no id required")
        elif re.search(
            r"\b(?:need|needs|require|requires|requiring|bring)\s+(?:an?\s+)?(?:id|identification)\b",
            normalized,
        ):
            semantic.append("id required")

        return QueryConstraints(
            city=city,
            county=county,
            zipcode=zipcode,
            provider_name=provider_name,
            category=category,
            day=day,
            open_at=open_at,
            semantic=tuple(semantic),
        )
