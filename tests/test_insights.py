"""Tests for the pure figure calculations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lexcrawl_dashboard.cache import TtlCache
from lexcrawl_dashboard.insights import coverage_stats, crawl_health, credit_summary, paragraphs, source_for
from lexcrawl_dashboard.models import CreditUsage, Document, Run, Source
from tests.fixtures import CREDITS, SOURCES, document, run

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
SOURCE_MAP = {item["code"]: Source.model_validate(item) for item in SOURCES}


def _doc(doc_id: int, **overrides: object) -> Document:
    return Document.model_validate(document(doc_id, **overrides))


def test_coverage_counts_recency_rate_and_sources() -> None:
    docs = [
        _doc(1, first_seen_at="2026-11-18T08:00:00Z"),
        _doc(2, first_seen_at="2026-11-15T08:00:00Z", source="commerce_reports"),
        _doc(3, first_seen_at="2026-10-01T08:00:00Z", extraction_status="failed", language="ar"),
    ]
    stats = coverage_stats(docs, SOURCE_MAP, now=NOW)
    assert (stats.window_size, stats.new_last_24h, stats.new_last_7d) == (3, 1, 2)
    assert stats.extraction_rate == 2 / 3
    assert stats.languages == ("ar", "en")
    assert stats.by_source[0].source.code == "cba_news_releases" and stats.by_source[0].count == 2


def test_coverage_of_an_empty_window() -> None:
    stats = coverage_stats([], SOURCE_MAP, now=NOW)
    assert stats.window_size == 0 and stats.extraction_rate is None and stats.by_source == ()


def test_crawl_health_states() -> None:
    runs = [
        Run.model_validate(run("r3", "partial_failure")),
        Run.model_validate(run("r2", "success")),
        Run.model_validate(run("r1", "running")),
    ]
    health = crawl_health(runs, api_ready=True)
    assert health.state == "degraded"
    assert health.success_rate == 0.5
    assert health.last_success_at is not None
    assert health.average_duration_seconds == 300.0
    assert crawl_health([], api_ready=True).state == "unknown"
    assert crawl_health(runs, api_ready=False).state == "down"


def test_credit_summary_compares_months_including_january() -> None:
    usage = [CreditUsage.model_validate(item) for item in CREDITS]
    summary = credit_summary(usage, SOURCE_MAP, now=NOW)
    assert (summary.this_month, summary.last_month, summary.change) == (42, 30, 12)
    assert summary.by_source[0][0].code == "commerce_reports"
    january = credit_summary(
        [CreditUsage.model_validate({**CREDITS[0], "month": "2025-12-01T00:00:00Z"})],
        SOURCE_MAP,
        now=datetime(2026, 1, 5, tzinfo=UTC),
    )
    assert january.last_month == 42


def test_paragraphs_drop_marker_and_split() -> None:
    assert paragraphs("TEXT-BEGIN\nOne.\n\nTwo.") == ("One.", "Two.")
    assert paragraphs("TEXT-BEGIN\nLine one\nLine two") == ("Line one", "Line two")
    assert paragraphs(None) == ()


def test_unknown_source_gets_a_readable_name() -> None:
    assert source_for("new_source_code", {}).name == "New Source Code"


def test_ttl_cache_reuses_until_expiry_and_never_caches_failures() -> None:
    clock = [0.0]
    cache = TtlCache(10, clock=lambda: clock[0])
    calls = [0]

    def produce() -> int:
        calls[0] += 1
        return calls[0]

    assert cache.get_or_set("k", produce) == 1
    assert cache.get_or_set("k", produce) == 1
    clock[0] = 11
    assert cache.get_or_set("k", produce) == 2

    def fail() -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        cache.get_or_set("other", fail)
    assert cache.get_or_set("other", produce) == 3
