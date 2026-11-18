"""Tests for the template formatting filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lexcrawl_dashboard.models import Document
from lexcrawl_dashboard.web.formatting import (
    duration,
    humanize,
    percent,
    published,
    signed,
    source_tone,
    status_tone,
    time_ago,
)
from tests.fixtures import document

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def test_published_respects_precision() -> None:
    assert published(Document.model_validate(document(1, published_at="2026-11-07"))) == "7 Nov 2026"
    month = document(1, published_at=None, published_precision="month", published_month=3)
    assert published(Document.model_validate(month)) == "Mar 2026"
    year = document(1, published_at=None, published_precision="year", published_month=None)
    assert published(Document.model_validate(year)) == "2026"
    undated = document(1, published_at=None, published_month=None, published_year=None,
                       published_precision="unknown")
    assert published(Document.model_validate(undated)) == "Undated"


def test_time_ago() -> None:
    assert time_ago(NOW - timedelta(seconds=10), NOW) == "just now"
    assert time_ago(NOW - timedelta(minutes=5), NOW) == "5 min ago"
    assert time_ago(NOW - timedelta(hours=1), NOW) == "1 hour ago"
    assert time_ago(NOW - timedelta(days=3), NOW) == "3 days ago"
    assert time_ago(None, NOW) == "never"


def test_numbers_and_labels() -> None:
    assert percent(0.876) == "88%" and percent(None) == "—"
    assert duration(75) == "1m 15s" and duration(3700) == "1h 1m" and duration(9) == "9s"
    assert signed(12) == "+12" and signed(-3) == "-3" and signed(0) == "±0"
    assert humanize("partial_failure") == "Partial failure"
    assert status_tone("success") == "ok" and status_tone("weird") == "muted"


def test_source_tone_is_stable() -> None:
    assert source_tone("cba_news_releases") == source_tone("cba_news_releases")
    assert source_tone("x").startswith("tone-")
