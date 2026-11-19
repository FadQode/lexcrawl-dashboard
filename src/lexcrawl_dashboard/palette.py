"""Colour classes shared by templates and charts (the CSS defines what each class looks like)."""

from __future__ import annotations

import zlib

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


def source_tone(code: str) -> str:
    """A stable colour class per source, so each source keeps its colour everywhere."""
    return f"tone-{zlib.crc32(code.encode()) % _TONES}"


def status_tone(status: str | None) -> str:
    """Colour for a run or extraction status: ok, warn, bad, info, or muted."""
    return _STATUS_TONES.get(status or "", "muted")
