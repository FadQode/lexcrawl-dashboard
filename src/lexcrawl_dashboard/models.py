"""Typed views of the LexCrawl API responses the dashboard consumes.

Only the fields the dashboard uses are required; unknown fields are ignored so the API
can add fields without breaking the dashboard.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Base model: immutable, tolerant of extra fields."""

    model_config = ConfigDict(frozen=True, extra="ignore")


class Page[T](ApiModel):
    """One keyset-paginated page."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class Source(ApiModel):
    """A crawled source (a "section" of the paper)."""

    code: str
    name: str
    base_url: str | None = None
    is_active: bool = True


class Document(ApiModel):
    """Document metadata, as returned by list endpoints (no text)."""

    id: int
    source_code: str
    source_url: str
    title: str
    language: str
    document_type: str | None = None
    summary: str | None = None
    image_url: str | None = None
    published_at: date | None = None
    published_year: int | None = None
    published_month: int | None = None
    published_precision: str = "unknown"
    extraction_status: str | None = None
    topics: list[str] = []
    first_seen_at: datetime
    last_seen_at: datetime


class DocumentDetail(Document):
    """A single document including its extracted text."""

    published_date_raw: str | None = None
    extraction_error: str | None = None
    text: str | None = None


class Resource(ApiModel):
    """An attachment (usually a PDF) belonging to a document."""

    id: int
    title: str
    url: str | None = None
    kind: str
    status: str
    error: str | None = None


class Run(ApiModel):
    """One crawl run."""

    run_id: str
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    credits_spent: int = 0


class RunSource(ApiModel):
    """Per-source metrics within a run."""

    source_code: str
    status: str
    check_outcome: str
    discovered_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    credits_used: int = 0
    detail: str | None = None


class RunError(ApiModel):
    """One error recorded during a run."""

    stage: str
    error_type: str
    message: str
    occurred_at: datetime


class RunDetail(ApiModel):
    """A run with its per-source metrics and errors."""

    item: Run
    sources: list[RunSource] = []
    errors: list[RunError] = []
    errors_total: int = 0


class CreditUsage(ApiModel):
    """Provider credits spent by one source in one month."""

    month: datetime
    source: str
    credits_used: int
    executions: int


class PendingDocument(ApiModel):
    """A document still waiting for another extraction attempt."""

    source: str
    document_id: int
    identity_key: str
    status: str | None = None
    attempts: int = 0
    last_error: str | None = None
