"""Tests for the startup configuration warnings and failure logging."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from lexcrawl_dashboard.config import Settings
from lexcrawl_dashboard.web.app import warn_on_suspicious_config


def test_missing_url_and_token_are_reported(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(_env_file=None, lexcrawl_api_token=SecretStr(""))  # type: ignore[call-arg]
    with caplog.at_level(logging.WARNING):
        problems = warn_on_suspicious_config(settings)
    assert len(problems) == 2
    assert "LEXCRAWL_API_URL is not set" in caplog.text
    assert "LEXCRAWL_API_TOKEN is not set" in caplog.text


def test_complete_config_is_quiet() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        lexcrawl_api_url="https://api.example",
        lexcrawl_api_token=SecretStr("secret"),
    )
    assert warn_on_suspicious_config(settings) == []
