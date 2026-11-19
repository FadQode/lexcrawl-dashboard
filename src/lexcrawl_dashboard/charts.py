"""SVG chart geometry.

This module computes every rectangle, label and gridline position; templates only draw
them. Coordinates are in SVG user units inside a fixed `viewBox`, so charts scale to any
width through CSS.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from lexcrawl_dashboard.models import Run
from lexcrawl_dashboard.palette import source_tone, status_tone
from lexcrawl_dashboard.viewmodels import PublicationSeries

_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True, slots=True)
class Bar:
    """One rectangle, with its colour class and hover text."""

    x: float
    y: float
    width: float
    height: float
    css_class: str
    title: str


@dataclass(frozen=True, slots=True)
class Tick:
    """A label at a position along an axis (x for categories, y for gridlines)."""

    position: float
    label: str
    sublabel: str = ""


@dataclass(frozen=True, slots=True)
class LegendItem:
    """One colour key."""

    label: str
    css_class: str


@dataclass(frozen=True, slots=True)
class Chart:
    """A column chart ready to draw."""

    width: int
    height: int
    plot_left: float
    plot_right: float
    plot_top: float
    plot_bottom: float
    bars: tuple[Bar, ...]
    x_ticks: tuple[Tick, ...]
    gridlines: tuple[Tick, ...]
    legend: tuple[LegendItem, ...] = ()

    @property
    def is_empty(self) -> bool:
        """True when there is nothing to plot."""
        return not self.bars


@dataclass(frozen=True, slots=True)
class Segment:
    """One stacked piece of a column: a value, its colour class, and its hover text."""

    value: float
    css_class: str
    title: str


@dataclass(frozen=True, slots=True)
class _Frame:
    width: int = 720
    height: int = 230
    left: float = 34
    right: float = 8
    top: float = 12
    bottom: float = 34

    @property
    def plot_width(self) -> float:
        return self.width - self.left - self.right

    @property
    def plot_height(self) -> float:
        return self.height - self.top - self.bottom


def nice_ceiling(value: float) -> float:
    """Round up to 1, 2, 2.5 or 5 times a power of ten, for readable axis maxima."""
    if value <= 0:
        return 1
    magnitude = float(10 ** math.floor(math.log10(value)))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


def stacked_columns(
    categories: Sequence[Tick],
    stacks: Sequence[Sequence[Segment]],
    *,
    legend: Sequence[LegendItem] = (),
    frame: _Frame | None = None,
    min_height: float = 0.0,
    unit: str = "",
) -> Chart:
    """Lay out one stacked column per category; `categories[i]` labels `stacks[i]`."""
    box = frame or _Frame()
    maximum = nice_ceiling(max((sum(seg.value for seg in stack) for stack in stacks), default=0))
    slot = box.plot_width / max(len(categories), 1)
    column = slot * 0.62
    bars: list[Bar] = []
    x_ticks: list[Tick] = []
    for index, (category, stack) in enumerate(zip(categories, stacks, strict=True)):
        x = box.left + slot * index + (slot - column) / 2
        baseline = box.top + box.plot_height
        for segment in stack:
            # $ min_height keeps tiny (even zero) values visible where that matters, e.g. 0 s runs.$
            height = max(box.plot_height * segment.value / maximum, min_height)
            if height <= 0:
                continue
            baseline -= height
            bars.append(Bar(x=round(x, 2), y=round(baseline, 2), width=round(column, 2),
                            height=round(height, 2), css_class=segment.css_class, title=segment.title))
        x_ticks.append(Tick(round(box.left + slot * index + slot / 2, 2), category.label, category.sublabel))
    gridlines = tuple(
        Tick(round(box.top + box.plot_height * (1 - fraction), 2), _format_value(maximum * fraction) + unit)
        for fraction in (0, 0.5, 1)
    )
    return Chart(
        width=box.width, height=box.height, plot_left=box.left, plot_right=box.width - box.right,
        plot_top=box.top, plot_bottom=box.top + box.plot_height,
        bars=tuple(bars), x_ticks=tuple(x_ticks), gridlines=gridlines, legend=tuple(legend),
    )


def publications_chart(series: PublicationSeries) -> Chart:
    """Stacked monthly columns, one colour per source."""
    categories = [
        Tick(0, _MONTH_ABBR[month - 1], str(year) if index == 0 or month == 1 else "")
        for index, (year, month) in enumerate(series.months)
    ]
    stacks = [
        [
            Segment(row.counts[index], source_tone(row.source.code),
                    f"{row.source.name}: {row.counts[index]} in {_MONTH_ABBR[month - 1]} {year}")
            for row in series.series
        ]
        for index, (year, month) in enumerate(series.months)
    ]
    legend = [LegendItem(row.source.name, source_tone(row.source.code)) for row in series.series]
    return stacked_columns(categories, stacks, legend=legend)


def runs_chart(runs: Sequence[Run], *, limit: int = 20) -> Chart:
    """Recent runs, oldest to newest: height is run time, colour is the outcome."""
    chosen = list(reversed(runs[:limit]))
    categories = [
        Tick(0, run.started_at.strftime("%d %b").lstrip("0") if index in (0, len(chosen) - 1) else "")
        for index, run in enumerate(chosen)
    ]
    stacks = [
        [Segment((run.duration_ms or 0) / 1000, status_tone(run.status), _run_title(run))]
        for run in chosen
    ]
    # $ A run that took ~0 s still gets a visible sliver, so every run shows its outcome.$
    return stacked_columns(categories, stacks, frame=_Frame(height=160, bottom=26), min_height=3, unit="s")


def _run_title(run: Run) -> str:
    seconds = (run.duration_ms or 0) // 1000
    took = f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"
    status = run.status.replace("_", " ").capitalize()
    return f"{status} · {run.started_at:%d %b %H:%M} UTC · {took}"


def _format_value(value: float) -> str:
    """Axis labels: whole numbers plainly, larger ones with a 'k' suffix."""
    if value >= 1000:
        return f"{value / 1000:g}k"
    return f"{value:g}"
