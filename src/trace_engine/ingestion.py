from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .models import Pantry


REQUIRED_FIELDS = {"provider_id", "name", "city", "county", "zipcode"}
OPTIONAL_FIELDS = {
    "address",
    "phone",
    "hours",
    "eligibility",
    "source_url",
    "last_verified_at",
}
KANSAS_SOURCE_FIELDS = {
    "pid",
    "pantry_name",
    "address_cleaned",
    "zipcode",
    "city",
    "county",
    "phone",
    "hours",
    "other_info",
}
KANSAS_FOOD_SOURCE_BASE_URL = "https://kansasfoodsource.org/"


def _source_url(other_info: str) -> str:
    absolute = re.search(r"https?://[^\s,]+", other_info)
    if absolute:
        return absolute.group(0).rstrip(".;)")
    relative = re.search(r"(?:^|[\s,])(/[^\s,]+)", other_info)
    if relative:
        return urljoin(KANSAS_FOOD_SOURCE_BASE_URL, relative.group(1).rstrip(".;)"))
    return ""


def _adapt_source_row(row: dict[str, Any]) -> dict[str, Any]:
    if not KANSAS_SOURCE_FIELDS <= set(row):
        return row
    other_info = "" if row.get("other_info") is None else str(row["other_info"]).strip()
    county = "" if row.get("county") is None else str(row["county"]).strip()
    county = re.sub(r"\s+County\s*,\s*Kansas\s*$", "", county, flags=re.IGNORECASE)
    return {
        "provider_id": row.get("pid"),
        "name": row.get("pantry_name"),
        "address": row.get("address_cleaned"),
        "city": row.get("city"),
        "county": county,
        "zipcode": row.get("zipcode"),
        "phone": row.get("phone"),
        "hours": row.get("hours"),
        "eligibility": other_info,
        "source_url": _source_url(other_info),
        "last_verified_at": "",
    }


def _build_pantry(row: dict[str, Any], row_number: int) -> Pantry:
    row = _adapt_source_row(row)
    normalized = {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
    missing = sorted(field for field in REQUIRED_FIELDS if not normalized.get(field))
    if missing:
        raise ValueError(f"row {row_number} is missing required fields: {', '.join(missing)}")
    allowed = REQUIRED_FIELDS | OPTIONAL_FIELDS
    values = {field: normalized.get(field, "") for field in allowed}
    values["zipcode"] = values["zipcode"].zfill(5)
    return Pantry(**values)


def load_directory(path: str | Path) -> tuple[Pantry, ...]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"directory file does not exist: {source}")

    suffix = source.suffix.casefold()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".json":
        with source.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError("JSON directory must contain a list of provider objects")
        rows = value
    else:
        raise ValueError(f"unsupported directory format: {source.suffix}; use CSV or JSON")

    records = tuple(_build_pantry(row, index) for index, row in enumerate(rows, start=2))
    identifiers = [record.provider_id for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("provider_id values must be unique")
    return records
