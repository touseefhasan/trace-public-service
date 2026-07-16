from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .models import Pantry, QueryConstraints
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


class ConstraintParser:
    """A deterministic baseline parser designed to be replaceable by an LLM parser."""

    def __init__(self, providers: Sequence[Pantry]) -> None:
        self.providers = tuple(providers)
        self.counties = self._choices(item.county for item in self.providers)
        self.cities = self._choices(item.city for item in self.providers)
        self.provider_names = self._choices(item.name for item in self.providers)

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

    def parse(self, query: str) -> QueryConstraints:
        normalized = normalize_text(query)
        zipcode_match = re.search(r"\b\d{5}(?:-\d{4})?\b", query)
        zipcode = zipcode_match.group(0)[:5] if zipcode_match else None

        county = self._contained(normalized, self.counties)
        city = self._contained(normalized, self.cities)
        provider_name = self._contained(normalized, self.provider_names)
        if city and county and normalize_location(city) == normalize_location(county):
            county_phrase = rf"\b{re.escape(normalize_location(county))}\s+county\b"
            city_phrase = rf"\b(?:city of|in the city of)\s+{re.escape(normalize_location(city))}\b"
            if re.search(county_phrase, normalized) and not re.search(city_phrase, normalized):
                city = None

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
            day=day,
            open_at=open_at,
            semantic=tuple(semantic),
        )
