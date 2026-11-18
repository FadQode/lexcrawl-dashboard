"""Page routes. Each handler asks the service for a view model and renders one template."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lexcrawl_dashboard.service import DashboardService

router = APIRouter()


def get_service(request: Request) -> DashboardService:
    """The service built at startup."""
    service: DashboardService = request.app.state.service
    return service


def get_templates(request: Request) -> Jinja2Templates:
    """The template environment built at startup."""
    templates: Jinja2Templates = request.app.state.templates
    return templates


@router.get("/", response_class=HTMLResponse)
def front_page(
    request: Request,
    service: DashboardService = Depends(get_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    """The front page."""
    return templates.TemplateResponse(request, "index.html", {"page": service.front_page(), "nav": "home"})


@router.get("/sections/{source_code}", response_class=HTMLResponse)
def section(
    request: Request,
    source_code: str,
    cursor: str | None = Query(default=None, max_length=512),
    service: DashboardService = Depends(get_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    """One source's archive."""
    page = service.section(source_code, cursor=cursor)
    return templates.TemplateResponse(request, "section.html", {"page": page, "nav": source_code})


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def article(
    request: Request,
    document_id: int,
    service: DashboardService = Depends(get_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    """One document, read like an article."""
    page = service.article(document_id)
    return templates.TemplateResponse(request, "article.html", {"page": page, "nav": page.source.code})


@router.get("/status", response_class=HTMLResponse)
def status_desk(
    request: Request,
    run: str | None = Query(default=None, max_length=64),
    service: DashboardService = Depends(get_service),
    templates: Jinja2Templates = Depends(get_templates),
) -> HTMLResponse:
    """Crawl operations: run history, run detail, and credits."""
    page = service.status_desk(run)
    return templates.TemplateResponse(request, "status.html", {"page": page, "nav": "status"})


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Liveness check for hosting platforms (does not call the API)."""
    return {"status": "ok"}
