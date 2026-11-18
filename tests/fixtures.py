"""Canned LexCrawl API payloads shared by the tests."""

from __future__ import annotations

from typing import Any

API_URL = "http://api.test"
TOKEN = "test-token"


def document(doc_id: int, source: str = "cba_news_releases", **overrides: Any) -> dict[str, Any]:
    """A document list item as the API returns it."""
    payload: dict[str, Any] = {
        "id": doc_id,
        "source_code": source,
        "identity_key": f"{source}:url:https://example.test/{doc_id}",
        "source_url": f"https://example.test/{doc_id}",
        "title": f"Document {doc_id}",
        "language": "en",
        "document_type": "news",
        "summary": f"Summary of document {doc_id}.",
        "image_url": None,
        "published_at": f"2026-11-{10 + doc_id % 9:02d}",
        "published_year": 2026,
        "published_month": 11,
        "published_precision": "day",
        "extraction_status": "complete",
        "content_hash": "abc",
        "topics": ["banking"],
        "first_seen_at": "2026-11-16T08:00:00Z",
        "last_seen_at": "2026-11-17T08:00:00Z",
    }
    payload.update(overrides)
    return payload


def document_detail(doc_id: int, **overrides: Any) -> dict[str, Any]:
    """A document detail including text."""
    payload = document(doc_id)
    payload.update(
        {
            "native_id": None,
            "published_date_raw": "Nov 17, 2026",
            "extraction_error": None,
            "text": "TEXT-BEGIN\nFirst paragraph.\n\nSecond paragraph.",
        }
    )
    payload.update(overrides)
    return payload


SOURCES: list[dict[str, Any]] = [
    {"id": 1, "code": "uae_legislation_news", "name": "UAE Legislation news",
     "base_url": "https://uaelegislation.gov.ae", "is_active": True},
    {"id": 2, "code": "cba_news_releases", "name": "CBA news releases",
     "base_url": "https://cba.ca", "is_active": True},
    {"id": 3, "code": "commerce_reports", "name": "U.S. Department of Commerce reports",
     "base_url": "https://www.commerce.gov", "is_active": True},
]


def run(run_id: str, status: str = "success", started: str = "2026-11-18T07:00:00Z") -> dict[str, Any]:
    """A run list item."""
    return {
        "id": 1,
        "run_id": run_id,
        "trigger_type": "api",
        "status": status,
        "started_at": started,
        "finished_at": "2026-11-18T07:05:00Z",
        "duration_ms": 300_000,
        "credits_spent": 3,
    }


def run_detail(run_id: str, status: str = "success") -> dict[str, Any]:
    """A run detail with one source and one error."""
    return {
        "item": run(run_id, status),
        "sources": [
            {
                "source_code": "cba_news_releases", "status": status, "check_outcome": "new_data",
                "discovered_count": 35, "inserted_count": 2, "updated_count": 1, "skipped_count": 32,
                "failed_count": 0, "resource_count": 0, "pending_count": 0, "credits_used": 0,
                "pagination_complete": True, "metrics_known": True, "detail": "ok",
                "started_at": "2026-11-18T07:00:00Z", "finished_at": "2026-11-18T07:01:00Z",
            }
        ],
        "errors": [
            {"stage": "detail", "error_type": "FetchError", "message": "timeout",
             "occurred_at": "2026-11-18T07:00:30Z", "document_id": None}
        ],
        "errors_total": 1,
    }


CREDITS: list[dict[str, Any]] = [
    {"month": "2026-11-01T00:00:00Z", "source": "commerce_reports", "credits_used": 42, "executions": 6,
     "avg_credits_per_execution": 7.0},
    {"month": "2026-10-01T00:00:00Z", "source": "commerce_reports", "credits_used": 30, "executions": 5,
     "avg_credits_per_execution": 6.0},
]

PENDING: list[dict[str, Any]] = [
    {"source": "commerce_reports", "document_id": 9, "identity_key": "commerce_reports:url:x",
     "status": "failed", "attempts": 2, "last_error": "thin page", "last_seen_at": "2026-11-17T08:00:00Z"},
]
