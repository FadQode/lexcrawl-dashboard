"""Tests for SVG chart geometry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lexcrawl_dashboard.charts import (
    Segment,
    Tick,
    nice_ceiling,
    publications_chart,
    runs_chart,
    stacked_columns,
)
from lexcrawl_dashboard.insights import monthly_publications
from lexcrawl_dashboard.models import Document, Run, Source
from tests.fixtures import SOURCES, document, run

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
SOURCE_MAP = {item["code"]: Source.model_validate(item) for item in SOURCES}


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 1), (1, 1), (3, 5), (7, 10), (12, 20), (23, 25), (40, 50), (380, 500)]
)
def test_nice_ceiling(value: float, expected: float) -> None:
    assert nice_ceiling(value) == expected


def test_stacked_columns_stack_bottom_up_inside_the_plot() -> None:
    chart = stacked_columns(
        [Tick(0, "A"), Tick(0, "B")],
        [[Segment(2, "one", "a1"), Segment(3, "two", "a2")], [Segment(1, "one", "b1")]],
    )
    first, second, third = chart.bars
    assert first.y + first.height == pytest.approx(chart.plot_bottom)  # $ sits on the baseline$
    assert second.y + second.height == pytest.approx(first.y)  # $ stacked on top of the first$
    assert second.y == pytest.approx(chart.plot_top)  # $ the tallest column (5) reaches the top$
    assert third.height == pytest.approx(first.height / 2)
    assert [tick.label for tick in chart.gridlines] == ["0", "2.5", "5"]
    assert [tick.label for tick in chart.x_ticks] == ["A", "B"]


def test_zero_values_draw_nothing_and_empty_charts_report_it() -> None:
    chart = stacked_columns([Tick(0, "A")], [[Segment(0, "one", "")]])
    assert chart.is_empty


def test_publications_chart_labels_months_years_and_sources() -> None:
    docs = [
        Document.model_validate(document(1, published_at="2026-11-02")),
        Document.model_validate(document(2, published_at="2026-01-15", source="commerce_reports")),
    ]
    chart = publications_chart(monthly_publications(docs, SOURCE_MAP, now=NOW))
    assert [tick.label for tick in chart.x_ticks][:3] == ["Dec", "Jan", "Feb"]
    assert chart.x_ticks[0].sublabel == "2025" and chart.x_ticks[1].sublabel == "2026"
    assert {item.label for item in chart.legend} == {
        "CBA news releases",
        "U.S. Department of Commerce reports",
    }
    assert len(chart.bars) == 2
    assert "CBA news releases: 1 in Nov 2026" in {bar.title for bar in chart.bars}


def test_runs_chart_is_chronological_and_coloured_by_outcome() -> None:
    runs = [
        Run.model_validate({**run("new", "failed"), "duration_ms": 0}),
        Run.model_validate(run("old", "success")),
    ]
    chart = runs_chart(runs)
    assert [bar.css_class for bar in chart.bars] == ["ok", "bad"]  # $ oldest first$
    assert chart.bars[1].height == pytest.approx(3)  # $ a 0 s run still shows a sliver$
    assert chart.gridlines[-1].label.endswith("s")
