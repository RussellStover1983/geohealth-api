"""Tests for /llms.txt and /llms-full.txt endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_llms_txt_returns_plain_text(client):
    """GET /llms.txt returns 200 with text/plain content."""
    resp = await client.get("/llms.txt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_llms_txt_contains_key_info(client):
    """Concise llms.txt includes API name, endpoints, and data fields."""
    resp = await client.get("/llms.txt")
    text = resp.text
    assert "GeoHealth" in text
    assert "/v1/context" in text
    assert "poverty_rate" in text
    assert "sdoh_index" in text
    assert "MCP" in text


@pytest.mark.asyncio
async def test_llms_full_txt_returns_plain_text(client):
    """GET /llms-full.txt returns 200 with text/plain content."""
    resp = await client.get("/llms-full.txt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


@pytest.mark.asyncio
async def test_llms_full_txt_contains_clinical_context(client):
    """Full reference includes clinical interpretation and all endpoints."""
    resp = await client.get("/llms-full.txt")
    text = resp.text
    assert "clinical" in text.lower()
    assert "/v1/context" in text
    assert "/v1/batch" in text
    assert "/v1/nearby" in text
    assert "/v1/compare" in text
    assert "/v1/dictionary" in text
    assert "SVI" in text
    assert "PLACES" in text
    assert "claude_desktop_config" in text


@pytest.mark.asyncio
async def test_llms_txt_no_auth_required(client):
    """llms.txt endpoints are public — no auth needed."""
    # These should return 200 even without an API key, regardless of auth settings
    from unittest.mock import patch
    with (
        patch("geohealth.config.settings.auth_enabled", True),
        patch("geohealth.config.settings.api_keys", "valid-key"),
    ):
        resp_short = await client.get("/llms.txt")
        resp_full = await client.get("/llms-full.txt")
    assert resp_short.status_code == 200
    assert resp_full.status_code == 200
