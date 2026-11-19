"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lexcrawl_dashboard import __version__
from lexcrawl_dashboard.client import LexCrawlApiError, LexCrawlClient, LexCrawlNotFoundError
from lexcrawl_dashboard.config import Settings, get_settings
from lexcrawl_dashboard.service import DashboardService
from lexcrawl_dashboard.web.formatting import FILTERS
from lexcrawl_dashboard.web.routes import router

_WEB_DIR = Path(__file__).parent
_DEFAULT_API_URL = Settings.model_fields["lexcrawl_api_url"].default

LOGGER = logging.getLogger(__name__)


def warn_on_suspicious_config(settings: Settings) -> list[str]:
    """Log (and return) the misconfigurations that make every panel fail.

    Deployed copies most often break because the API URL or token was never set on the
    host, which silently falls back to localhost or an empty token.
    """
    problems: list[str] = []
    if settings.lexcrawl_api_url == _DEFAULT_API_URL:
        problems.append(f"LEXCRAWL_API_URL is not set; using the default {_DEFAULT_API_URL}")
    if not settings.lexcrawl_api_token.get_secret_value():
        problems.append("LEXCRAWL_API_TOKEN is not set; the API will answer 401")
    for problem in problems:
        LOGGER.warning("configuration: %s", problem)
    return problems


def build_templates(settings: Settings) -> Jinja2Templates:
    """Templates with the formatting filters and site-wide globals registered."""
    templates = Jinja2Templates(directory=_WEB_DIR / "templates")
    templates.env.filters.update(FILTERS)
    templates.env.globals.update(site_title=settings.site_title, site_tagline=settings.site_tagline,
                                 version=__version__)
    return templates


def create_app(settings: Settings | None = None, *, client: LexCrawlClient | None = None) -> FastAPI:
    """Build the dashboard app; `client` can be injected for tests."""
    resolved = settings or get_settings()
    templates = build_templates(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        warn_on_suspicious_config(resolved)
        api = client or LexCrawlClient(
            resolved.lexcrawl_api_url,
            resolved.lexcrawl_api_token.get_secret_value(),
            timeout_seconds=resolved.api_timeout_seconds,
        )
        app.state.service = DashboardService(api, resolved)
        app.state.templates = templates
        try:
            yield
        finally:
            if client is None:
                api.close()

    app = FastAPI(title=resolved.site_title, version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")
    app.include_router(router)

    @app.exception_handler(LexCrawlNotFoundError)
    async def not_found(request: Request, error: LexCrawlNotFoundError) -> HTMLResponse:
        return _error_page(request, 404, "Story not found",
                           "That page does not exist, or it has been removed from the archive.")

    @app.exception_handler(LexCrawlApiError)
    async def api_unavailable(request: Request, error: LexCrawlApiError) -> HTMLResponse:
        LOGGER.warning("page %s failed: %s (status=%s)", request.url.path, error, error.status_code)
        return _error_page(request, 503, "The newsroom is offline",
                           "The LexCrawl API could not be reached. Please try again in a minute.")

    def _error_page(request: Request, status: int, title: str, message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "error.html", {"title": title, "message": message, "status": status},
            status_code=status,
        )

    return app
