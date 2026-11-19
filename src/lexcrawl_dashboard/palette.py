"""Colour classes shared by templates and charts (the CSS defines what each class looks like)."""

from __future__ import annotations

import zlib
from collections.abc import Iterable

_TONES = 6
_STATUS_TONES = {
    "success": "ok",
    "complete": "ok",
    "partial_failure": "warn",
    "pending": "warn",
    "running": "info",
    "failed": "bad",
    "abandoned": "bad",
}

# Known sources get distinct tones; codes not registered yet fall back to a hash.
_assigned: dict[str, str] = {}


def assign_source_tones(codes: Iterable[str]) -> None:
    """Give each known source its own tone.

    Codes are sorted first, so every process (and every deploy) assigns the same colours,
    and up to six sources never share one.
    """
    _assigned.clear()
    _assigned.update({code: f"tone-{index % _TONES}" for index, code in enumerate(sorted(set(codes)))})


def source_tone(code: str) -> str:
    """The colour class for a source, consistent across every page and chart."""
    return _assigned.get(code) or f"tone-{zlib.crc32(code.encode()) % _TONES}"


def status_tone(status: str | None) -> str:
    """Colour for a run or extraction status: ok, warn, bad, info, or muted."""
    return _STATUS_TONES.get(status or "", "muted")
