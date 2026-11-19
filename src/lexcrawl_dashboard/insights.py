"""Pure functions that turn API data into dashboard figures.

No I/O and no clock reads: callers pass `now`, so every figure is easy to test.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta

from lexcrawl_dashboard.models import CreditUsage, Document, Run, Source
from lexcrawl_dashboard.viewmodels import (
    CoverageStats,
    CrawlHealth,
    CreditSummary,
    PublicationSeries,
    SourceCount,
    SourceSeries,
    SourceShare,
)

# The crawler prefixes extracted text with a marker line; it is not part of the story.
_TEXT_MARKER = "TEXT-BEGIN"


def source_for(code: str, sources: Mapping[str, Source]) -> Source:
    """Look up a source, falling back to a readable placeholder for unknown codes."""
    known = sources.get(code)
    if known is not None:
        return known
    return Source(code=code, name=code.replace("_", " ").title())


def coverage_stats(
    documents: Sequence[Document], sources: Mapping[str, Source], *, now: datetime
) -> CoverageStats:
    """Headline numbers about a window of recent documents."""
    statuses = [doc.extraction_status for doc in documents if doc.extraction_status]
    complete = sum(1 for status in statuses if status == "complete")
    per_source = Counter(doc.source_code for doc in documents)
    return CoverageStats(
        window_size=len(documents),
        new_last_24h=sum(1 for doc in documents if now - doc.first_seen_at <= timedelta(days=1)),
        new_last_7d=sum(1 for doc in documents if now - doc.first_seen_at <= timedelta(days=7)),
        extraction_rate=(complete / len(statuses)) if statuses else None,
        languages=tuple(sorted({doc.language for doc in documents})),
        by_source=tuple(
            SourceCount(source=source_for(code, sources), count=count)
            for code, count in per_source.most_common()
        ),
    )


def crawl_health(runs: Sequence[Run], *, api_ready: bool) -> CrawlHealth:
    """Summarise recent runs (newest first) into a health snapshot."""
    finished = [run for run in runs if run.status != "running"]
    successes = [run for run in finished if run.status == "success"]
    durations = [run.duration_ms / 1000 for run in finished if run.duration_ms is not None]
    return CrawlHealth(
        api_ready=api_ready,
        last_run=runs[0] if runs else None,
        last_success_at=successes[0].finished_at if successes else None,
        success_rate=(len(successes) / len(finished)) if finished else None,
        average_duration_seconds=(sum(durations) / len(durations)) if durations else None,
        recent_runs=tuple(runs),
    )


def credit_summary(
    usage: Iterable[CreditUsage], sources: Mapping[str, Source], *, now: datetime
) -> CreditSummary:
    """Credits spent this calendar month versus last month."""
    this_month = (now.year, now.month)
    last_month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    this_total = 0
    last_total = 0
    by_source: Counter[str] = Counter()
    for row in usage:
        key = (row.month.year, row.month.month)
        if key == this_month:
            this_total += row.credits_used
            by_source[row.source] += row.credits_used
        elif key == last_month:
            last_total += row.credits_used
    return CreditSummary(
        this_month=this_total,
        last_month=last_total,
        by_source=tuple((source_for(code, sources), credits) for code, credits in by_source.most_common()),
    )


def month_window(now: datetime, months: int) -> tuple[tuple[int, int], ...]:
    """The last `months` calendar months as (year, month), oldest first, ending with `now`'s month."""
    index = now.year * 12 + (now.month - 1)
    return tuple(
        (value // 12, value % 12 + 1) for value in range(index - months + 1, index + 1)
    )


def publication_month(document: Document) -> tuple[int, int] | None:
    """The (year, month) a document was published, when the source gave at least a month."""
    if document.published_at is not None:
        return document.published_at.year, document.published_at.month
    if document.published_year and document.published_month:
        return document.published_year, document.published_month
    return None


def monthly_publications(
    documents: Iterable[Document], sources: Mapping[str, Source], *, now: datetime, months: int = 12
) -> PublicationSeries:
    """Count documents per publication month and source over the last `months` months."""
    window = month_window(now, months)
    position = {key: index for index, key in enumerate(window)}
    counts: dict[str, list[int]] = {}
    undated = 0
    before = 0
    for document in documents:
        key = publication_month(document)
        if key is None:
            undated += 1
        elif key in position:
            counts.setdefault(document.source_code, [0] * months)[position[key]] += 1
        elif key < window[0]:
            before += 1
    ranked = sorted(counts.items(), key=lambda item: -sum(item[1]))
    return PublicationSeries(
        months=window,
        series=tuple(
            SourceSeries(source=source_for(code, sources), counts=tuple(row)) for code, row in ranked
        ),
        undated=undated,
        before_window=before,
    )


def source_shares(coverage: CoverageStats) -> tuple[SourceShare, ...]:
    """Each source's share of the documents counted in `coverage`."""
    total = coverage.window_size
    return tuple(
        SourceShare(source=item.source, count=item.count, share=(item.count / total) if total else 0.0)
        for item in coverage.by_source
    )


def headline_insights(
    coverage: CoverageStats,
    publications: PublicationSeries,
    health: CrawlHealth | None,
    *,
    pending: int | None,
) -> tuple[str, ...]:
    """Plain-language findings for the data desk, most notable first."""
    findings: list[str] = []
    if coverage.by_source:
        top = coverage.by_source[0]
        share = top.count / coverage.window_size if coverage.window_size else 0
        findings.append(f"{top.source.name} supplies the most material: {top.count} documents ({share:.0%}).")
    totals = publications.totals
    if any(totals):
        peak = max(range(len(totals)), key=lambda index: totals[index])
        year, month = publications.months[peak]
        findings.append(
            f"Busiest month in the last {len(totals)}: {MONTH_NAMES[month - 1]} {year}, "
            f"with {totals[peak]} documents published."
        )
    if coverage.new_last_7d:
        findings.append(f"{coverage.new_last_7d} documents were discovered in the past week.")
    if pending:
        findings.append(f"{pending} documents are still waiting for their full text.")
    if health is not None and health.state == "degraded" and health.last_run is not None:
        findings.append("The most recent crawl run did not finish cleanly; see the status desk.")
    return tuple(findings)


MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December")


def paragraphs(text: str | None) -> tuple[str, ...]:
    """Split extracted text into readable paragraphs, dropping the crawler's marker."""
    if not text:
        return ()
    body = text.removeprefix(_TEXT_MARKER).strip()
    blocks = re.split(r"\n\s*\n", body)
    if len(blocks) == 1:
        # $ Single-newline text (common for PDFs) still reads better as separate lines.$
        blocks = body.splitlines()
    return tuple(block.strip() for block in blocks if block.strip())
