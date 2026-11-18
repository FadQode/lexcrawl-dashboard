"""End-to-end page tests: real app and templates, API mocked with respx."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from lexcrawl_dashboard.client import LexCrawlClient
from lexcrawl_dashboard.config import Settings
from lexcrawl_dashboard.web.app import create_app
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


def _page(items: list[object]) -> dict[str, object]:
    return {"items": items, "next_cursor": None, "has_more": False}


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API_URL, assert_all_called=False) as router:
        router.get("/sources").mock(return_value=httpx.Response(200, json=SOURCES))
        router.get("/documents").mock(
            return_value=httpx.Response(
                200, json=_page([document(1), document(2, source="commerce_reports", language="ar")])
            )
        )
        router.get("/documents/1").mock(return_value=httpx.Response(200, json=document_detail(1)))
        router.get("/documents/1/resources").mock(
            return_value=httpx.Response(
                200, json=[{"id": 1, "document_id": 1, "title": "Report PDF", "url": "https://x.test/a.pdf",
                            "kind": "pdf", "status": "complete", "extraction_status": None,
                            "content_hash": None, "error": None}]
            )
        )
        router.get("/documents/999").mock(return_value=httpx.Response(404))
        router.get("/runs").mock(return_value=httpx.Response(200, json=_page([run("r1")])))
        router.get("/runs/r1").mock(return_value=httpx.Response(200, json=run_detail("r1")))
        router.get("/readyz").mock(return_value=httpx.Response(200, json={"status": "ready"}))
        router.get("/analytics/credits").mock(return_value=httpx.Response(200, json=CREDITS))
        router.get("/analytics/pending").mock(return_value=httpx.Response(200, json=PENDING))
        yield router


@pytest.fixture
def browser(api: respx.MockRouter) -> Iterator[TestClient]:
    settings = Settings(lexcrawl_api_url=API_URL, cache_ttl_seconds=0)
    with (
        LexCrawlClient(API_URL, TOKEN) as client,
        TestClient(create_app(settings, client=client)) as test_client,
    ):
        yield test_client


def test_front_page_renders_news_and_dashboard(browser: TestClient) -> None:
    response = browser.get("/")
    assert response.status_code == 200
    html = response.text
    assert "<title>Lexcrawl-Dashboard</title>" in html
    for expected in ("Document 1", "Crawl health", "Coverage", "Provider credits", "CBA news releases"):
        assert expected in html


def test_section_article_and_status_pages(browser: TestClient) -> None:
    assert "CBA news releases" in browser.get("/sections/cba_news_releases").text
    article = browser.get("/documents/1")
    assert article.status_code == 200
    assert "First paragraph." in article.text and "Report PDF" in article.text
    status = browser.get("/status")
    assert status.status_code == 200 and "timeout" in status.text


def test_missing_document_is_a_404_page(browser: TestClient) -> None:
    response = browser.get("/documents/999")
    assert response.status_code == 404 and "Story not found" in response.text


def test_api_outage_shows_an_offline_page(browser: TestClient, api: respx.MockRouter) -> None:
    api.get("/documents/1").mock(side_effect=httpx.ConnectError("down"))
    response = browser.get("/documents/1")
    assert response.status_code == 503 and "offline" in response.text


def test_front_page_degrades_instead_of_failing(browser: TestClient, api: respx.MockRouter) -> None:
    api.get("/analytics/credits").mock(return_value=httpx.Response(500))
    response = browser.get("/")
    assert response.status_code == 200
    assert "Credits are temporarily unavailable." in response.text


def test_token_never_reaches_the_browser(browser: TestClient) -> None:
    for path in ("/", "/documents/1", "/status"):
        assert TOKEN not in browser.get(path).text


def test_healthz_and_static_assets(browser: TestClient) -> None:
    assert browser.get("/healthz").json() == {"status": "ok"}
    assert browser.get("/static/css/site.css").status_code == 200
