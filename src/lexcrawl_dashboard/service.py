"""Dashboard service: fetches (and caches) API data, then assembles page view models.

Each front-page panel is fetched independently. When one endpoint fails, that panel is
left empty and a notice is shown, instead of the whole page failing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from lexcrawl_dashboard.cache import TtlCache
from lexcrawl_dashboard.charts import publications_chart, runs_chart
from lexcrawl_dashboard.client import LexCrawlApiError, LexCrawlClient
from lexcrawl_dashboard.config import Settings
from lexcrawl_dashboard.insights import (
    coverage_stats,
    crawl_health,
    credit_summary,
    headline_insights,
    monthly_publications,
    paragraphs,
    source_for,
    source_shares,
)
from lexcrawl_dashboard.models import Document, Run, Source
from lexcrawl_dashboard.palette import assign_source_tones
from lexcrawl_dashboard.viewmodels import (
    ArticlePage,
    ConnectionReport,
    CrawlHealth,
    DataDesk,
    FrontPage,
    Section,
    SectionPage,
    StatusDesk,
)

LOGGER = logging.getLogger(__name__)

_TOP_STORIES = 4
_TICKER_ITEMS = 10
_SECTION_ITEMS = 5
_RELATED_ITEMS = 5
_PENDING_LIMIT = 500
_API_PAGE_LIMIT = 200  # the API's maximum page size


class DashboardService:
    """Builds every page's view model from the LexCrawl API."""

    def __init__(
        self,
        client: LexCrawlClient,
        settings: Settings,
        *,
        cache: TtlCache | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
    ) -> None:
        self._client = client
        self._settings = settings
        self._cache = cache or TtlCache(settings.cache_ttl_seconds)
        self._clock = clock

    # --- Pages -------------------------------------------------------------

    def front_page(self) -> FrontPage:
        """The newspaper front page: lead story, sections, and the dashboard rail."""
        now = self._clock()
        notices: list[str] = []
        sources = self._sources(notices)
        archive = self._attempt(self._archive, "latest documents", notices)
        corpus, corpus_capped = archive if archive is not None else (None, False)
        latest = corpus[: self._settings.front_page_documents] if corpus is not None else None
        runs = self._attempt(lambda: self._recent_runs(), "crawl runs", notices)
        usage = self._attempt(lambda: self._cached(("credits",), self._client.credits), "credits", notices)
        pending = self._attempt(
            lambda: self._cached(("pending",), lambda: self._client.pending(limit=_PENDING_LIMIT)),
            "pending documents",
            notices,
        )
        sections = tuple(
            Section(source=source, documents=tuple(docs))
            for source in sources.values()
            if (docs := [doc for doc in (latest or []) if doc.source_code == source.code][:_SECTION_ITEMS])
        )
        stories = latest or []
        lead = _lead_story(stories)
        health = crawl_health(runs, api_ready=self._ready()) if runs is not None else None
        pending_count = len(pending) if pending is not None else None
        return FrontPage(
            lead=lead,
            top_stories=tuple(doc for doc in stories if doc is not lead)[:_TOP_STORIES],
            ticker=tuple(stories[:_TICKER_ITEMS]),
            sections=sections,
            data_desk=(
                _data_desk(corpus, corpus_capped, sources, runs, health, pending_count, now=now)
                if corpus is not None
                else None
            ),
            health=health,
            credits=credit_summary(usage, sources, now=now) if usage is not None else None,
            pending_count=pending_count,
            pending_capped=pending is not None and len(pending) >= _PENDING_LIMIT,
            sources=sources,
            generated_at=now,
            notices=tuple(notices),
        )

    def section(self, source_code: str, *, cursor: str | None = None) -> SectionPage:
        """One source's documents, newest first, with keyset pagination."""
        sources = self._sources([])
        page = self._cached(
            ("documents", source_code, cursor),
            lambda: self._client.documents(
                source=source_code, limit=self._settings.section_page_size, cursor=cursor
            ),
        )
        return SectionPage(
            source=source_for(source_code, sources),
            documents=tuple(page.items),
            next_cursor=page.next_cursor if page.has_more else None,
            sources=sources,
            generated_at=self._clock(),
        )

    def article(self, document_id: int) -> ArticlePage:
        """One document with its text, attachments, and related stories."""
        sources = self._sources([])
        document = self._cached(("document", document_id), lambda: self._client.document(document_id))
        resources = self._attempt(
            lambda: self._cached(("resources", document_id), lambda: self._client.resources(document_id)),
            "attachments",
            [],
        )
        related = self._attempt(
            lambda: self._cached(
                ("documents", document.source_code, None),
                lambda: self._client.documents(
                    source=document.source_code, limit=self._settings.section_page_size
                ),
            ).items,
            "related stories",
            [],
        )
        return ArticlePage(
            document=document,
            source=source_for(document.source_code, sources),
            paragraphs=paragraphs(document.text),
            resources=tuple(resources or ()),
            related=tuple(doc for doc in (related or []) if doc.id != document.id)[:_RELATED_ITEMS],
            sources=sources,
            generated_at=self._clock(),
        )

    def status_desk(self, run_id: str | None = None) -> StatusDesk:
        """Crawl operations: recent runs, one run's detail, and credit history."""
        sources = self._sources([])
        runs = self._recent_runs()
        chosen = run_id or (runs[0].run_id if runs else None)
        selected = self._cached(("run", chosen), lambda: self._client.run(chosen)) if chosen else None
        usage = self._attempt(lambda: self._cached(("credits",), self._client.credits), "credits", [])
        return StatusDesk(
            health=crawl_health(runs, api_ready=self._ready()),
            selected=selected,
            credits=tuple(usage or ()),
            sources=sources,
            generated_at=self._clock(),
        )

    def connection_report(self) -> ConnectionReport:
        """Call an authenticated endpoint, uncached, and report exactly what happened."""
        url = self._settings.lexcrawl_api_url
        error: LexCrawlApiError | None = None
        try:
            self._client.sources()
        except LexCrawlApiError as failure:
            error = failure
        return ConnectionReport(
            api_host=urlsplit(url).netloc or url,
            url_configured=url != Settings.model_fields["lexcrawl_api_url"].default,
            token_configured=bool(self._settings.lexcrawl_api_token.get_secret_value()),
            reachable=error is None,
            error=str(error) if error else None,
            status_code=error.status_code if error else None,
        )

    # --- Helpers -----------------------------------------------------------

    def _sources(self, notices: list[str]) -> dict[str, Source]:
        """Sources keyed by code (empty, with a notice, when unavailable)."""
        listed = self._attempt(lambda: self._cached(("sources",), self._client.sources), "sources", notices)
        sources = {source.code: source for source in (listed or [])}
        if sources:
            assign_source_tones(sources)
        return sources

    def _archive(self) -> tuple[list[Document], bool]:
        """Every document, newest first, up to `insights_max_documents`; True when capped."""

        def load() -> tuple[list[Document], bool]:
            cap = self._settings.insights_max_documents
            documents: list[Document] = []
            cursor: str | None = None
            while len(documents) < cap:
                page = self._client.documents(limit=min(_API_PAGE_LIMIT, cap - len(documents)), cursor=cursor)
                documents.extend(page.items)
                if not page.has_more or not page.next_cursor:
                    return documents, False
                cursor = page.next_cursor
            return documents, True

        return self._cached(("archive",), load)

    def _recent_runs(self) -> list[Run]:
        return self._cached(
            ("runs",), lambda: self._client.runs(limit=self._settings.status_desk_runs)
        ).items

    def _ready(self) -> bool:
        return self._cached(("ready",), self._client.is_ready)

    def _cached[T](self, key: tuple[object, ...], produce: Callable[[], T]) -> T:
        return self._cache.get_or_set(key, produce)

    @staticmethod
    def _attempt[T](produce: Callable[[], T], label: str, notices: list[str]) -> T | None:
        """Run one panel's fetch; on API failure record a notice and return None."""
        try:
            return produce()
        except LexCrawlApiError as error:
            # $ Visitors see a generic notice; operators get the real cause in the server log.$
            LOGGER.warning("panel %r unavailable: %s (status=%s)", label, error, error.status_code)
            notices.append(f"{label.capitalize()} are temporarily unavailable.")
            return None


def _data_desk(
    corpus: Sequence[Document],
    capped: bool,
    sources: dict[str, Source],
    runs: Sequence[Run] | None,
    health: CrawlHealth | None,
    pending: int | None,
    *,
    now: datetime,
) -> DataDesk:
    """Assemble the front-page hero from the whole archive and recent runs."""
    coverage = coverage_stats(corpus, sources, now=now)
    publications = monthly_publications(corpus, sources, now=now)
    return DataDesk(
        coverage=coverage,
        corpus_capped=capped,
        shares=source_shares(coverage),
        publications=publications,
        publications_chart=publications_chart(publications),
        runs_chart=runs_chart(runs) if runs else None,
        insights=headline_insights(coverage, publications, health, pending=pending),
    )


def _lead_story(documents: Sequence[Document]) -> Document | None:
    """Prefer the newest document that has a summary; otherwise the newest overall."""
    for document in documents:
        if document.summary:
            return document
    return documents[0] if documents else None
