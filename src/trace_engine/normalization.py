from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache


DAY_ALIASES = {
    "mon": "monday",
    "monday": "monday",
    "mondays": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "tuesday": "tuesday",
    "tuesdays": "tuesday",
    "wed": "wednesday",
    "wednesday": "wednesday",
    "wednesdays": "wednesday",
    "thu": "thursday",
    "thur": "thursday",
    "thurs": "thursday",
    "thursday": "thursday",
    "thursdays": "thursday",
    "fri": "friday",
    "friday": "friday",
    "fridays": "friday",
    "sat": "saturday",
    "saturday": "saturday",
    "saturdays": "saturday",
    "sun": "sunday",
    "sunday": "sunday",
    "sundays": "sunday",
}
DAY_ORDER = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
DAY_TOKEN_PATTERN = (
    r"mondays|monday|mon|tuesdays|tuesday|tues|tue|wednesdays|wednesday|wed|"
    r"thursdays|thursday|thurs|thur|thu|fridays|friday|fri|saturdays|saturday|"
    r"sat|sundays|sunday|sun"
)
DAY_EXPRESSION_PATTERN = re.compile(
    rf"\b(?:every\s+)?(?:{DAY_TOKEN_PATTERN})"
    rf"(?:\s*(?:,|&|and|through|thru|to|-)\s*(?:every\s+)?(?:{DAY_TOKEN_PATTERN}))*\b",
    flags=re.IGNORECASE,
)
TIME_VALUE_PATTERN = r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?"
TIME_RANGE_PATTERN = re.compile(
    rf"(?P<start>{TIME_VALUE_PATTERN})\s*(?:-|–|—|to|until)\s*"
    rf"(?P<end>{TIME_VALUE_PATTERN})",
    flags=re.IGNORECASE,
)
MONTH_PATTERN = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\b",
    flags=re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_location(value: str) -> str:
    return normalize_text(value.removesuffix(" County").removesuffix(" county"))


def tokenize(value: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "at",
        "do",
        "for",
        "find",
        "help",
        "i",
        "in",
        "looking",
        "me",
        "need",
        "of",
        "on",
        "pantry",
        "service",
        "services",
        "show",
        "the",
        "to",
        "where",
    }
    return {token for token in normalize_text(value).split() if token not in stopwords}


def parse_clock(value: str) -> int | None:
    """Convert a user-facing time to minutes after midnight."""

    match = re.fullmatch(
        r"\s*(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*"
        r"(?P<period>a\.?m\.?|p\.?m\.?)?\s*",
        value.casefold(),
    )
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    period = (match.group("period") or "").replace(".", "") or None
    if minute > 59:
        return None
    if period:
        if not 1 <= hour <= 12:
            return None
        hour %= 12
        if period == "pm":
            hour += 12
    elif hour > 23:
        return None
    return hour * 60 + minute


def clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@lru_cache(maxsize=4096)
def parse_hours(value: str) -> dict[str, tuple[tuple[int | None, int | None], ...]]:
    """Extract recurring day/time intervals without inventing missing times."""

    text = value.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\bM\s*-\s*F\b", "Monday-Friday", text, flags=re.IGNORECASE)
    if not text.strip() or normalize_text(text) in {"not available", "n a", "na"}:
        return {}
    if re.search(r"\b24\s*/\s*7\b", text):
        return {day: ((0, 1440),) for day in DAY_ORDER}

    day_matches = list(DAY_EXPRESSION_PATTERN.finditer(text))
    time_matches = list(TIME_RANGE_PATTERN.finditer(text))
    schedule: dict[str, set[tuple[int | None, int | None]]] = defaultdict(set)
    associated_day_starts: set[int] = set()

    for time_match in time_matches:
        preceding = [match for match in day_matches if match.end() <= time_match.start()]
        if not preceding:
            continue
        day_match = max(preceding, key=lambda match: match.end())
        context = text[day_match.start() : time_match.end()]
        if time_match.start() - day_match.end() > 120:
            continue
        if (
            MONTH_PATTERN.search(context)
            and re.search(r"\b20\d{2}\b", context)
        ) or re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", context):
            continue
        interval = _parse_time_range(time_match.group("start"), time_match.group("end"))
        if interval is None:
            continue
        associated_day_starts.add(day_match.start())
        for day in _expand_days(day_match.group(0)):
            schedule[day].add(interval)

    for day_match in day_matches:
        if day_match.start() in associated_day_starts:
            continue
        nearby = text[day_match.start() : min(len(text), day_match.end() + 80)]
        if (
            MONTH_PATTERN.search(nearby)
            and re.search(r"\b20\d{2}\b", nearby)
        ) or re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", nearby):
            continue
        for day in _expand_days(day_match.group(0)):
            schedule[day].add((None, None))

    return {
        day: tuple(sorted(intervals, key=lambda interval: (interval[0] is None, interval)))
        for day, intervals in schedule.items()
    }


def _expand_days(value: str) -> tuple[str, ...]:
    aliases = re.findall(DAY_TOKEN_PATTERN, value.casefold())
    days = [DAY_ALIASES[alias] for alias in aliases]
    if len(days) >= 2 and re.search(r"\b(?:through|thru|to)\b|-", value, re.IGNORECASE):
        start = DAY_ORDER.index(days[0])
        end = DAY_ORDER.index(days[1])
        if start <= end:
            return DAY_ORDER[start : end + 1]
    return tuple(dict.fromkeys(days))


def _period(value: str) -> str | None:
    match = re.search(r"([ap])\.?m\.?", value, flags=re.IGNORECASE)
    return f"{match.group(1).casefold()}m" if match else None


def _parse_time_range(start_value: str, end_value: str) -> tuple[int, int] | None:
    start_period = _period(start_value)
    end_period = _period(end_value)
    start = parse_clock(start_value)
    end = parse_clock(end_value)

    if start_period is None and end_period:
        same_period = parse_clock(f"{start_value.strip()} {end_period}")
        opposite = "am" if end_period == "pm" else "pm"
        opposite_period = parse_clock(f"{start_value.strip()} {opposite}")
        if same_period is not None and end is not None and same_period < end:
            start = same_period
        elif opposite_period is not None:
            start = opposite_period
    elif start_period and end_period is None:
        same_period = parse_clock(f"{end_value.strip()} {start_period}")
        opposite = "pm" if start_period == "am" else "am"
        opposite_period = parse_clock(f"{end_value.strip()} {opposite}")
        if same_period is not None and start is not None and start < same_period:
            end = same_period
        elif opposite_period is not None:
            end = opposite_period

    if start is None or end is None or start >= end:
        return None
    return start, end


def is_open(hours: str, day: str | None, open_at: str | None) -> bool:
    if not day and not open_at:
        return True
    if not day:
        return False
    schedule = parse_hours(hours)
    ranges = schedule.get(day.casefold(), ())
    if not ranges:
        return False
    if not open_at:
        return True
    minute = parse_clock(open_at)
    return minute is not None and any(
        start is not None and end is not None and start <= minute < end
        for start, end in ranges
    )


def first_contained_value(query: str, values: Iterable[str]) -> str | None:
    normalized_query = f" {normalize_text(query)} "
    choices = sorted({value for value in values if value}, key=len, reverse=True)
    for choice in choices:
        if f" {normalize_text(choice)} " in normalized_query:
            return choice
    return None
