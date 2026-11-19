"""Tests for colour assignment."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from lexcrawl_dashboard import palette


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    yield
    palette.assign_source_tones([])


def test_known_sources_get_distinct_stable_tones() -> None:
    codes = ["uae_legislation_news", "cba_news_releases", "commerce_reports"]
    palette.assign_source_tones(codes)
    tones = {code: palette.source_tone(code) for code in codes}
    assert len(set(tones.values())) == 3
    palette.assign_source_tones(reversed(codes))  # $ order of discovery does not matter$
    assert {code: palette.source_tone(code) for code in codes} == tones


def test_unknown_sources_fall_back_to_a_hash_tone() -> None:
    assert palette.source_tone("brand_new").startswith("tone-")
    assert palette.status_tone("partial_failure") == "warn" and palette.status_tone(None) == "muted"
