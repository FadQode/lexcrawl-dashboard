"""Tests for the dashboard service (API mocked with respx)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
import respx

from lexcrawl_dashboard.client import LexCrawlClient, LexCrawlNotFoundError
from lexcrawl_dashboard.config import Settings
from lexcrawl_dashboard.service import DashboardService
from tests.fixtures import (
    API_URL,
    CREDITS,
    PENDING,
    SOURCES,
    TOKEN,
    document,
    document_detail,
    run,
    run_detail,
)

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def _page(items: list[object], cursor: str | None = None) -> dict[str, object]:
    return {"items": items, "next_cursor": cursor, "has_more": cursor is not None}


@pytest.fixture
def service() -> Iterator[DashboardService]:
    settings = Settings(lexcrawl_api_url=API_URL, cache_ttl_seconds=0)
    with LexCrawlClient(API_URL, TOKEN) as client:
        yield DashboardService(client, settings, clock=lambda: NOW)


def _mock_front_page_api() -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    respx.get(f"{API_URL}/documents").mock(
        return_value=httpx.Response(
            200,
            json=_page(
                [document(1, summary=None), document(2), document(3, source="commerce_reports")]
                + [document(n) for n in range(4, 9)]
            ),
        )
    )
    respx.get(f"{API_URL}/runs").mock(return_value=httpx.Response(200, json=_page([run("r1")])))
    respx.get(f"{API_URL}/readyz").mock(return_value=httpx.Response(200, json={"status": "ready"}))
    respx.get(f"{API_URL}/analytics/credits").mock(return_value=httpx.Response(200, json=CREDITS))
    respx.get(f"{API_URL}/analytics/pending").mock(return_value=httpx.Response(200, json=PENDING))


@respx.mock
def test_front_page_assembles_every_panel(service: DashboardService) -> None:
    _mock_front_page_api()
    page = service.front_page()
    assert page.lead is not None and page.lead.id == 2  # $ newest document that has a summary$
    assert page.lead not in page.top_stories and len(page.top_stories) == 4
    assert [section.source.code for section in page.sections] == ["cba_news_releases", "commerce_reports"]
    assert len(page.sections[0].documents) == 5
    assert page.coverage is not None and page.coverage.window_size == 8
    assert page.health is not None and page.health.state == "ok"
    assert page.credits is not None and page.credits.this_month == 42
    assert page.pending_count == 1 and not page.pending_capped
    assert page.notices == ()


@respx.mock
def test_front_page_survives_a_failing_panel(service: DashboardService) -> None:
    _mock_front_page_api()
    respx.get(f"{API_URL}/analytics/credits").mock(return_value=httpx.Response(500))
    page = service.front_page()
    assert page.credits is None
    assert page.lead is not None
    assert page.notices == ("Credits are temporarily unavailable.",)


@respx.mock
def test_archive_pages_through_every_document(service: DashboardService) -> None:
    _mock_front_page_api()
    route = respx.get(f"{API_URL}/documents").mock(
        side_effect=[
            httpx.Response(200, json=_page([document(1), document(2)], cursor="p2")),
            httpx.Response(200, json=_page([document(3)])),
        ]
    )
    page = service.front_page()
    assert route.call_count == 2
    assert route.calls[1].request.url.params["cursor"] == "p2"
    assert page.coverage is not None and page.coverage.window_size == 3
    assert page.corpus_capped is False


@respx.mock
def test_archive_stops_at_the_configured_cap() -> None:
    _mock_front_page_api()
    route = respx.get(f"{API_URL}/documents").mock(
        return_value=httpx.Response(200, json=_page([document(1), document(2)], cursor="more"))
    )
    settings = Settings(lexcrawl_api_url=API_URL, cache_ttl_seconds=0, insights_max_documents=2)
    with LexCrawlClient(API_URL, TOKEN) as client:
        page = DashboardService(client, settings, clock=lambda: NOW).front_page()
    assert route.call_count == 1 and route.calls[0].request.url.params["limit"] == "2"
    assert page.corpus_capped is True


@respx.mock
def test_section_paginates(service: DashboardService) -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    route = respx.get(f"{API_URL}/documents").mock(
        return_value=httpx.Response(200, json=_page([document(1)], cursor="next"))
    )
    page = service.section("cba_news_releases", cursor="c1")
    assert page.source.name == "CBA news releases" and page.next_cursor == "next"
    assert route.calls.last.request.url.params["cursor"] == "c1"


@respx.mock
def test_article_includes_paragraphs_and_related(service: DashboardService) -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    respx.get(f"{API_URL}/documents/7").mock(return_value=httpx.Response(200, json=document_detail(7)))
    respx.get(f"{API_URL}/documents/7/resources").mock(return_value=httpx.Response(500))
    respx.get(f"{API_URL}/documents").mock(
        return_value=httpx.Response(200, json=_page([document(7), document(8)]))
    )
    page = service.article(7)
    assert page.paragraphs == ("First paragraph.", "Second paragraph.")
    assert page.resources == ()  # $ attachments failed, the article still renders$
    assert [doc.id for doc in page.related] == [8]


@respx.mock
def test_missing_article_raises_not_found(service: DashboardService) -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    respx.get(f"{API_URL}/documents/404").mock(return_value=httpx.Response(404))
    with pytest.raises(LexCrawlNotFoundError):
        service.article(404)


@respx.mock
def test_status_desk_defaults_to_the_latest_run(service: DashboardService) -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    respx.get(f"{API_URL}/runs").mock(return_value=httpx.Response(200, json=_page([run("r2"), run("r1")])))
    respx.get(f"{API_URL}/runs/r2").mock(return_value=httpx.Response(200, json=run_detail("r2")))
    respx.get(f"{API_URL}/readyz").mock(return_value=httpx.Response(200))
    respx.get(f"{API_URL}/analytics/credits").mock(return_value=httpx.Response(200, json=CREDITS))
    desk = service.status_desk()
    assert desk.selected is not None and desk.selected.item.run_id == "r2"
    assert len(desk.health.recent_runs) == 2 and len(desk.credits) == 2
