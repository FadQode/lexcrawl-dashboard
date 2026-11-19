"""Jinja filters: presentation-only formatting of dates, numbers, and statuses."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from lexcrawl_dashboard.models import Document
from lexcrawl_dashboard.palette import source_tone, status_tone


def published(document: Document) -> str:
    """Publication date at the precision the source actually gave."""
    if document.published_precision == "day" and document.published_at:
        return document.published_at.strftime("%d %b %Y").lstrip("0")
    if document.published_month and document.published_year:
        return date(document.published_year, document.published_month, 1).strftime("%b %Y")
    if document.published_year:
        return str(document.published_year)
    return "Undated"


def time_ago(moment: datetime | None, now: datetime | None = None) -> str:
    """Human relative time such as '5 min ago' or '3 days ago'."""
    if moment is None:
        return "never"
    reference = now or datetime.now(tz=UTC)
    seconds = int((reference - moment).total_seconds())
    if seconds < 60:
        return "just now"
    for size, unit in ((86_400, "day"), (3_600, "hour"), (60, "min")):
        if seconds >= size:
            amount = seconds // size
            plural = "s" if amount != 1 and unit != "min" else ""
            return f"{amount} {unit}{plural} ago"
    return "just now"


def long_date(moment: datetime | date) -> str:
    """Masthead-style date, e.g. 'Wednesday, 18 November 2026'."""
    return moment.strftime("%A, %d %B %Y").replace(", 0", ", ")


def clock_time(moment: datetime | None) -> str:
    """UTC timestamp for tables, e.g. '18 Nov 07:05 UTC'."""
    if moment is None:
        return "—"
    return moment.astimezone(UTC).strftime("%d %b %H:%M UTC").lstrip("0")


def percent(ratio: float | None) -> str:
    """0.873 -> '87%'; unknown -> '—'."""
    return "—" if ratio is None else f"{round(ratio * 100)}%"


def number(value: int | None) -> str:
    """Thousands separators; unknown -> '—'."""
    return "—" if value is None else f"{value:,}"


def duration(seconds: float | int | None) -> str:
    """75 -> '1m 15s'; 3700 -> '1h 1m'."""
    if seconds is None:
        return "—"
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def signed(value: int) -> str:
    """12 -> '+12', -3 -> '-3', 0 -> '±0'."""
    if value > 0:
        return f"+{value:,}"
    return f"{value:,}" if value < 0 else "±0"


def humanize(value: str | None) -> str:
    """'partial_failure' -> 'Partial failure'."""
    return (value or "unknown").replace("_", " ").capitalize()


FILTERS: dict[str, Callable[..., Any]] = {
    "published": published,
    "time_ago": time_ago,
    "long_date": long_date,
    "clock_time": clock_time,
    "percent": percent,
    "number": number,
    "duration": duration,
    "signed": signed,
    "source_tone": source_tone,
    "status_tone": status_tone,
    "humanize": humanize,
}
