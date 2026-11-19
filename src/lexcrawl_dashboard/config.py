"""Runtime configuration, read from environment variables (and an optional `.env`)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated dashboard settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    site_title: str = "Lexcrawl-Dashboard"
    site_tagline: str = "Legal & regulatory updates, as they are crawled"

    # LexCrawl API connection. The token stays on the server and is never sent to browsers.
    lexcrawl_api_url: str = "http://localhost:8000"
    lexcrawl_api_token: SecretStr = SecretStr("")
    # Free hosts can take ~20 s to wake a sleeping API, so the default is generous.
    api_timeout_seconds: float = Field(default=30.0, gt=0)

    # How long API responses are reused before the next page view refetches them.
    cache_ttl_seconds: float = Field(default=60.0, ge=0)

    front_page_documents: int = Field(default=60, ge=1, le=200)
    # Upper bound on documents paged in for archive-wide figures (keeps cold loads bounded).
    insights_max_documents: int = Field(default=1000, ge=1, le=20_000)
    section_page_size: int = Field(default=24, ge=1, le=200)
    status_desk_runs: int = Field(default=20, ge=1, le=200)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
