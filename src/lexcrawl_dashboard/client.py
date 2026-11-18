"""HTTP client for the LexCrawl API.

The only module that knows endpoint paths, query parameters, and authentication. Every
method returns validated models, and every failure surfaces as :class:`LexCrawlApiError`.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import TypeAdapter, ValidationError

from lexcrawl_dashboard.models import (
    CreditUsage,
    Document,
    DocumentDetail,
    Page,
    PendingDocument,
    Resource,
    Run,
    RunDetail,
    Source,
)


class LexCrawlApiError(Exception):
    """The API could not be reached or returned an unusable response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LexCrawlNotFoundError(LexCrawlApiError):
    """The requested resource does not exist (HTTP 404)."""


_SOURCES = TypeAdapter(list[Source])
_DOCUMENT_PAGE = TypeAdapter(Page[Document])
_DOCUMENT = TypeAdapter(DocumentDetail)
_RESOURCES = TypeAdapter(list[Resource])
_RUN_PAGE = TypeAdapter(Page[Run])
_RUN = TypeAdapter(RunDetail)
_CREDITS = TypeAdapter(list[CreditUsage])
_PENDING = TypeAdapter(list[PendingDocument])


class LexCrawlClient:
    """Read-only client for the LexCrawl API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        """Release the connection pool."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    # --- Endpoints ---------------------------------------------------------

    def is_ready(self) -> bool:
        """Report whether the API and its database are ready."""
        try:
            return self._http.get("/readyz").status_code == 200
        except httpx.HTTPError:
            return False

    def sources(self) -> list[Source]:
        """List the registered sources."""
        return self._fetch(_SOURCES, "/sources")

    def documents(
        self, *, source: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> Page[Document]:
        """List documents, newest first, optionally for one source."""
        return self._fetch(_DOCUMENT_PAGE, "/documents", {"source": source, "limit": limit, "cursor": cursor})

    def document(self, document_id: int) -> DocumentDetail:
        """Fetch one document including its text."""
        return self._fetch(_DOCUMENT, f"/documents/{document_id}")

    def resources(self, document_id: int) -> list[Resource]:
        """List a document's attachments."""
        return self._fetch(_RESOURCES, f"/documents/{document_id}/resources")

    def runs(self, *, limit: int = 20, cursor: str | None = None) -> Page[Run]:
        """List crawl runs, newest first."""
        return self._fetch(_RUN_PAGE, "/runs", {"limit": limit, "cursor": cursor})

    def run(self, run_id: str) -> RunDetail:
        """Fetch one run with its per-source metrics and errors."""
        return self._fetch(_RUN, f"/runs/{run_id}")

    def credits(self) -> list[CreditUsage]:
        """Monthly provider-credit usage per source."""
        return self._fetch(_CREDITS, "/analytics/credits")

    def pending(self, *, limit: int = 100) -> list[PendingDocument]:
        """Documents still waiting for another extraction attempt."""
        return self._fetch(_PENDING, "/analytics/pending", {"limit": limit})

    # --- Transport ---------------------------------------------------------

    def _fetch[T](self, adapter: TypeAdapter[T], path: str, params: dict[str, Any] | None = None) -> T:
        """GET a resource and validate it against the expected model."""
        payload = self._get(path, params)
        try:
            return adapter.validate_python(payload)
        except ValidationError as error:
            raise LexCrawlApiError(
                f"unexpected LexCrawl API response for {path} ({error.error_count()} problem(s))"
            ) from error

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a JSON resource, translating every failure into a LexCrawlApiError."""
        query = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            response = self._http.get(path, params=query)
        except httpx.TimeoutException as error:
            raise LexCrawlApiError(f"LexCrawl API timed out on {path}") from error
        except httpx.HTTPError as error:
            raise LexCrawlApiError(f"LexCrawl API is unreachable: {error}") from error
        if response.status_code == 404:
            raise LexCrawlNotFoundError(f"{path} was not found", status_code=404)
        if response.status_code in (401, 403):
            raise LexCrawlApiError("LexCrawl API rejected the token", status_code=response.status_code)
        if response.status_code >= 400:
            raise LexCrawlApiError(
                f"LexCrawl API returned {response.status_code} for {path}", status_code=response.status_code
            )
        try:
            return response.json()
        except ValueError as error:
            raise LexCrawlApiError(f"LexCrawl API returned non-JSON for {path}") from error
