# Lexcrawl-Dashboard

A news-style dashboard for the [LexCrawl](https://github.com/FadQode/lecrawl) API. The latest
legal and regulatory documents are laid out like a newspaper front page, with crawl health,
coverage, and provider-credit figures in the side rail.

## Pages

| Path | What it shows |
|---|---|
| `/` | Front page: "Latest" ticker, lead story, top stories, one block per source, and a dashboard rail (crawl health, coverage, credits, pending retries) |
| `/sections/{source}` | One source's archive, newest first, with "Older stories" paging |
| `/documents/{id}` | A document read as an article: full text, attachments, record facts, related stories |
| `/status` | Status desk: recent runs, one run's per-source metrics and errors, credit history |
| `/healthz` | Liveness check for hosting platforms |

Arabic documents render right-to-left. Light and dark themes follow the visitor's system setting.

## Run locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then set LEXCRAWL_API_URL and LEXCRAWL_API_TOKEN
uv run lexcrawl-dashboard
```

Open http://localhost:8080.

## Configuration

All settings are environment variables (or entries in `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `LEXCRAWL_API_URL` | `http://localhost:8000` | Base URL of the LexCrawl API |
| `LEXCRAWL_API_TOKEN` | *(empty)* | The API's bearer token. Used server-side only; never sent to browsers |
| `API_TIMEOUT_SECONDS` | `30` | How long to wait for the API (free hosts can take ~20 s to wake) |
| `CACHE_TTL_SECONDS` | `60` | How long API responses are reused across page views (`0` disables) |
| `FRONT_PAGE_DOCUMENTS` | `60` | Documents loaded for the front page and its figures |
| `SECTION_PAGE_SIZE` | `24` | Documents per section page |
| `STATUS_DESK_RUNS` | `20` | Runs shown on the status desk and used for health figures |
| `SITE_TITLE` / `SITE_TAGLINE` | `Lexcrawl-Dashboard` / … | Branding |
| `PORT` | `8080` | Listening port (set by most hosts) |

## Deploy

**Docker (SnapDeploy, Render, Koyeb, any VPS).** The image runs as a non-root user, listens on
`$PORT`, and has a `/healthz` healthcheck:

```bash
docker build -t lexcrawl-dashboard .
docker run -p 8080:8080 -e LEXCRAWL_API_URL=https://your-api.example -e LEXCRAWL_API_TOKEN=... lexcrawl-dashboard
```

**Vercel.** Import the repository; Vercel serves the `app` object in `app.py`. Set
`LEXCRAWL_API_URL` and `LEXCRAWL_API_TOKEN` as environment variables.

If the API sleeps when idle (free tiers), the first page view after a quiet period waits for it
to wake; later views are served from the cache.

## Architecture

```
src/lexcrawl_dashboard/
  config.py      settings (pydantic-settings)
  models.py      typed views of API responses
  client.py      the only module that talks HTTP to LexCrawl; all failures -> LexCrawlApiError
  cache.py       thread-safe TTL cache shared by page views
  insights.py    pure functions: coverage, crawl health, credit figures, paragraph splitting
  viewmodels.py  page-ready dataclasses consumed by templates
  service.py     fetch + cache + assemble one view model per page; panels fail independently
  web/
    app.py        FastAPI factory, error pages, static files
    routes.py     one thin handler per page
    formatting.py Jinja filters (dates, numbers, status colours)
    templates/    base layout, macros, pages, front-page panels
    static/css/   the newspaper stylesheet
```

Dependencies point one way: `web` → `service` → `client` / `insights` → `models`. Templates contain
no logic beyond loops and conditionals; all figures are computed in `insights.py` and tested there.

**Adding a page:** add a view model in `viewmodels.py`, a method in `service.py`, a handler in
`web/routes.py`, and a template. **Adding a source:** nothing to change; sections come from the
API's `/sources`.

## Development

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

Tests mock the API with `respx`, so they need no network or running LexCrawl instance. CI runs
all three checks on every push.
