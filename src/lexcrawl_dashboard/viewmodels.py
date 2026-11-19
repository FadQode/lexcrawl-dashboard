"""Page-ready view models: everything a template needs, already computed.

Templates only format and lay out these values; they make no API calls and hold no logic
beyond simple conditionals and loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from lexcrawl_dashboard.models import CreditUsage, Document, DocumentDetail, Resource, Run, RunDetail, Source


@dataclass(frozen=True, slots=True)
class SourceCount:
    """How many documents one source contributed to a window."""

    source: Source
    count: int


@dataclass(frozen=True, slots=True)
class CoverageStats:
    """Headline numbers about the most recent documents."""

    window_size: int
    new_last_24h: int
    new_last_7d: int
    extraction_rate: float | None
    languages: tuple[str, ...]
    by_source: tuple[SourceCount, ...]


@dataclass(frozen=True, slots=True)
class SourceShare:
    """One source's slice of the archive."""

    source: Source
    count: int
    share: float


@dataclass(frozen=True, slots=True)
class SourceSeries:
    """Monthly document counts for one source, aligned with `PublicationSeries.months`."""

    source: Source
    counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PublicationSeries:
    """Documents per publication month, per source, over a fixed window of months."""

    months: tuple[tuple[int, int], ...]
    series: tuple[SourceSeries, ...]
    undated: int
    before_window: int

    @property
    def totals(self) -> tuple[int, ...]:
        """All sources combined, per month."""
        return tuple(sum(row.counts[index] for row in self.series) for index in range(len(self.months)))


@dataclass(frozen=True, slots=True)
class CrawlHealth:
    """Crawl-run health derived from recent runs."""

    api_ready: bool
    last_run: Run | None
    last_success_at: datetime | None
    success_rate: float | None
    average_duration_seconds: float | None
    recent_runs: tuple[Run, ...]

    @property
    def state(self) -> str:
        """One-word state for the masthead badge: ok, degraded, down, or unknown."""
        if not self.api_ready:
            return "down"
        if self.last_run is None:
            return "unknown"
        return "ok" if self.last_run.status == "success" else "degraded"


@dataclass(frozen=True, slots=True)
class CreditSummary:
    """Provider-credit spending, month over month."""

    this_month: int
    last_month: int
    by_source: tuple[tuple[Source, int], ...]

    @property
    def change(self) -> int:
        """Difference against the previous month."""
        return self.this_month - self.last_month


@dataclass(frozen=True, slots=True)
class Section:
    """One source's block on the front page."""

    source: Source
    documents: tuple[Document, ...]


@dataclass(frozen=True, slots=True)
class FrontPage:
    """Everything the front page renders."""

    lead: Document | None
    top_stories: tuple[Document, ...]
    ticker: tuple[Document, ...]
    sections: tuple[Section, ...]
    coverage: CoverageStats | None
    corpus_capped: bool
    health: CrawlHealth | None
    credits: CreditSummary | None
    pending_count: int | None
    pending_capped: bool
    sources: dict[str, Source]
    generated_at: datetime
    notices: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class SectionPage:
    """One source's paginated list of documents."""

    source: Source
    documents: tuple[Document, ...]
    next_cursor: str | None
    sources: dict[str, Source]
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class ArticlePage:
    """One document with its attachments and related stories."""

    document: DocumentDetail
    source: Source
    paragraphs: tuple[str, ...]
    resources: tuple[Resource, ...]
    related: tuple[Document, ...]
    sources: dict[str, Source]
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class ConnectionReport:
    """What the dashboard sees when it calls the API (safe to show: no secrets)."""

    api_host: str
    url_configured: bool
    token_configured: bool
    reachable: bool
    error: str | None
    status_code: int | None


@dataclass(frozen=True, slots=True)
class StatusDesk:
    """Crawl operations: recent runs and the detail of one run."""

    health: CrawlHealth
    selected: RunDetail | None
    credits: tuple[CreditUsage, ...]
    sources: dict[str, Source]
    generated_at: datetime
