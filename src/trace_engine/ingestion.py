from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin

from .models import ServiceProvider
from .xlsx import read_first_worksheet


REQUIRED_FIELDS = {"provider_id", "name"}
OPTIONAL_FIELDS = {
    "address",
    "city",
    "county",
    "zipcode",
    "organization",
    "description",
    "category",
    "state",
    "phone",
    "email",
    "hours",
    "eligibility",
    "application_process",
    "required_documents",
    "fees",
    "source_url",
    "last_verified_at",
    "location_source",
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
ADDRESS_PATTERN = re.compile(
    r",\s*(?P<city>[^,]+?)\s*,\s*(?P<state>[A-Z]{2})"
    r"(?:\s+(?P<zipcode>\d{5})(?:[-\s]+\d{3,4})?)?\s*$",
    flags=re.IGNORECASE,
)


def _source_url(other_info: str) -> str:
    absolute = re.search(r"https?://[^\s,]+", other_info)
    if absolute:
        return absolute.group(0).rstrip(".;)")
    relative = re.search(r"(?:^|[\s,])(/[^\s,]+)", other_info)
    if relative:
        return urljoin(KANSAS_FOOD_SOURCE_BASE_URL, relative.group(1).rstrip(".;)"))
    return ""


def _clean(value: Any) -> str:
    normalized = "" if value is None else str(value).strip()
    return "" if normalized == "-" else normalized


def _normalize_county(value: Any) -> str:
    county = _clean(value)
    county = re.sub(r"\s+County\s*,\s*Kansas\s*$", "", county, flags=re.IGNORECASE)
    return re.sub(r"\s+County$", "", county, flags=re.IGNORECASE).strip()


def _normalize_zipcode(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    if re.fullmatch(r"\d+\.0", raw):
        raw = raw[:-2]
    match = re.search(r"\b(\d{4,5})(?:[-\s]+\d{3,4})?\b", raw)
    return match.group(1).zfill(5) if match else raw


def parse_mailing_address(address: Any) -> dict[str, str]:
    """Derive city, state, and five-digit ZIP without discarding the raw address."""

    raw = _clean(address)
    match = ADDRESS_PATTERN.search(raw)
    if not match:
        return {"city": "", "state": "", "zipcode": ""}
    return {
        "city": match.group("city").strip(),
        "state": match.group("state").upper(),
        "zipcode": _normalize_zipcode(match.group("zipcode")),
    }


def _normalized_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {
        re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_"): value
        for key, value in row.items()
    }


def _provider_id(name: str, organization: str, source_url: str) -> str:
    decoded_url = unquote(source_url)
    source_id = re.search(r'"id"\s*:\s*(\d+)', decoded_url)
    if source_id:
        return f"211-{source_id.group(1)}"
    digest = hashlib.sha256(
        "\x1f".join((name, organization, source_url)).encode("utf-8")
    ).hexdigest()[:16]
    return f"service-{digest}"


def _adapt_211_row(row: dict[str, Any]) -> dict[str, Any]:
    values = _normalized_keys(row)
    if not {"name", "category_auto"} <= set(values):
        return row

    address = _clean(values.get("mailing_address"))
    parsed = parse_mailing_address(address)
    explicit_city = _clean(values.get("city"))
    explicit_state = _clean(values.get("state"))
    explicit_zipcode = _normalize_zipcode(values.get("zipcode") or values.get("zip"))
    city = explicit_city or parsed["city"]
    state = explicit_state.upper() or parsed["state"]
    zipcode = explicit_zipcode or parsed["zipcode"]
    parsed_location = bool(parsed["city"] or parsed["state"] or parsed["zipcode"])
    provided_location = bool(explicit_city or explicit_state or explicit_zipcode)
    if provided_location and parsed_location:
        location_source = "provided+parsed"
    elif provided_location:
        location_source = "provided"
    elif parsed_location:
        location_source = "parsed"
    else:
        location_source = "missing"

    name = _clean(values.get("name"))
    organization = _clean(values.get("organization"))
    source_url = _clean(values.get("service_page_url"))
    return {
        "provider_id": _provider_id(name, organization, source_url),
        "name": name,
        "organization": organization,
        "description": _clean(values.get("description")),
        "category": _clean(values.get("category_auto")),
        "address": address,
        "city": city,
        "state": state,
        "county": _normalize_county(values.get("county")),
        "zipcode": zipcode,
        "phone": _clean(values.get("phones") or values.get("phone")),
        "email": _clean(values.get("email")),
        "hours": _clean(values.get("hours")),
        "application_process": _clean(values.get("application_process")),
        "required_documents": _clean(values.get("required_documents")),
        "fees": _clean(values.get("fees")),
        "eligibility": _clean(values.get("eligibility")),
        "source_url": source_url,
        "last_verified_at": "",
        "location_source": location_source,
    }


def _adapt_source_row(row: dict[str, Any]) -> dict[str, Any]:
    adapted_211 = _adapt_211_row(row)
    if adapted_211 is not row:
        return adapted_211
    if not KANSAS_SOURCE_FIELDS <= set(row):
        legacy_fields = {"provider_id", "name", "city", "county", "zipcode"}
        if legacy_fields <= set(row) and "category" not in row:
            return {**row, "category": "Food", "location_source": "provided"}
        return row
    other_info = "" if row.get("other_info") is None else str(row["other_info"]).strip()
    return {
        "provider_id": row.get("pid"),
        "name": row.get("pantry_name"),
        "address": row.get("address_cleaned"),
        "city": row.get("city"),
        "county": _normalize_county(row.get("county")),
        "zipcode": row.get("zipcode"),
        "phone": row.get("phone"),
        "hours": row.get("hours"),
        "eligibility": other_info,
        "category": "Food",
        "source_url": _source_url(other_info),
        "last_verified_at": "",
        "location_source": "provided",
    }


def _build_provider(row: dict[str, Any], row_number: int) -> ServiceProvider:
    row = _adapt_source_row(row)
    normalized = {str(key): _clean(value) for key, value in row.items()}
    missing = sorted(field for field in REQUIRED_FIELDS if not normalized.get(field))
    if missing:
        raise ValueError(f"row {row_number} is missing required fields: {', '.join(missing)}")
    allowed = REQUIRED_FIELDS | OPTIONAL_FIELDS
    values = {field: normalized.get(field, "") for field in allowed}
    values["county"] = _normalize_county(values["county"])
    values["zipcode"] = _normalize_zipcode(values["zipcode"])
    return ServiceProvider(**values)


def load_directory(path: str | Path) -> tuple[ServiceProvider, ...]:
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
    elif suffix == ".xlsx":
        rows = read_first_worksheet(source)
    else:
        raise ValueError(
            f"unsupported directory format: {source.suffix}; use CSV, JSON, or XLSX"
        )

    records = tuple(_build_provider(row, index) for index, row in enumerate(rows, start=2))
    identifiers = [record.provider_id for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("provider_id values must be unique")
    return records
