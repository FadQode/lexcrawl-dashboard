"""Tests for the LexCrawl API client (HTTP mocked with respx)."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx

from lexcrawl_dashboard.client import LexCrawlApiError, LexCrawlClient, LexCrawlNotFoundError
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


@pytest.fixture
def client() -> Iterator[LexCrawlClient]:
    with LexCrawlClient(API_URL, TOKEN, timeout_seconds=5) as api:
        yield api


@respx.mock
def test_sends_bearer_token_and_parses_sources(client: LexCrawlClient) -> None:
    route = respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(200, json=SOURCES))
    sources = client.sources()
    assert [source.code for source in sources] == [
        "uae_legislation_news", "cba_news_releases", "commerce_reports"
    ]
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"


@respx.mock
def test_documents_pass_filters_and_drop_empty_params(client: LexCrawlClient) -> None:
    route = respx.get(f"{API_URL}/documents").mock(
        return_value=httpx.Response(200, json={"items": [document(1)], "next_cursor": "c2", "has_more": True})
    )
    page = client.documents(source="cba_news_releases", limit=10)
    assert page.has_more and page.next_cursor == "c2"
    assert page.items[0].title == "Document 1"
    params = route.calls.last.request.url.params
    assert params["source"] == "cba_news_releases" and params["limit"] == "10"
    assert "cursor" not in params


@respx.mock
def test_document_detail_runs_credits_and_pending(client: LexCrawlClient) -> None:
    respx.get(f"{API_URL}/documents/7").mock(return_value=httpx.Response(200, json=document_detail(7)))
    respx.get(f"{API_URL}/documents/7/resources").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{API_URL}/runs").mock(
        return_value=httpx.Response(200, json={"items": [run("r1")], "next_cursor": None, "has_more": False})
    )
    respx.get(f"{API_URL}/runs/r1").mock(return_value=httpx.Response(200, json=run_detail("r1")))
    respx.get(f"{API_URL}/analytics/credits").mock(return_value=httpx.Response(200, json=CREDITS))
    respx.get(f"{API_URL}/analytics/pending").mock(return_value=httpx.Response(200, json=PENDING))

    assert client.document(7).text is not None
    assert client.resources(7) == []
    assert client.runs().items[0].run_id == "r1"
    assert client.run("r1").errors_total == 1
    assert client.credits()[0].credits_used == 42
    assert client.pending()[0].attempts == 2


@respx.mock
def test_not_found_is_a_specific_error(client: LexCrawlClient) -> None:
    respx.get(f"{API_URL}/documents/404").mock(return_value=httpx.Response(404, json={"detail": "nope"}))
    with pytest.raises(LexCrawlNotFoundError):
        client.document(404)


@pytest.mark.parametrize("status", [401, 500, 503])
@respx.mock
def test_error_statuses_raise_api_error(client: LexCrawlClient, status: int) -> None:
    respx.get(f"{API_URL}/sources").mock(return_value=httpx.Response(status))
    with pytest.raises(LexCrawlApiError) as raised:
        client.sources()
    assert raised.value.status_code == status


@respx.mock
def test_unreachable_api_and_bad_shapes_raise_api_error(client: LexCrawlClient) -> None:
    respx.get(f"{API_URL}/sources").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(LexCrawlApiError):
        client.sources()
    respx.get(f"{API_URL}/analytics/credits").mock(return_value=httpx.Response(200, json=[{"bad": 1}]))
    with pytest.raises(LexCrawlApiError, match="unexpected"):
        client.credits()


@respx.mock
def test_is_ready(client: LexCrawlClient) -> None:
    respx.get(f"{API_URL}/readyz").mock(return_value=httpx.Response(200, json={"status": "ready"}))
    assert client.is_ready() is True
    respx.get(f"{API_URL}/readyz").mock(side_effect=httpx.ConnectError("down"))
    assert client.is_ready() is False
