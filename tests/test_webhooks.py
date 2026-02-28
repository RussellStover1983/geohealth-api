"""Tests for /v1/webhooks — CRUD webhook subscriptions."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app


def _make_mock_webhook(
    id_=1, url="https://example.com/hook", events=None, filters=None, active=True,
):
    sub = MagicMock()
    sub.id = id_
    sub.url = url
    sub.api_key_hash = "__anonymous__"
    sub.events = events or ["data.updated"]
    sub.filters = filters
    sub.secret = None
    sub.active = active
    sub.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    sub.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return sub


def _mock_session_for_create(existing_count=0):
    """Mock session for webhook creation: count query + add + commit + refresh."""
    session = AsyncMock()

    # First execute: count existing webhooks
    count_result = MagicMock()
    count_result.scalars.return_value.all.return_value = [None] * existing_count
    session.execute.return_value = count_result

    # session.add is sync on AsyncSession — use MagicMock to avoid coroutine warning
    session.add = MagicMock()

    async def _refresh(obj):
        obj.id = 1
        obj.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


def _mock_session_for_list(webhooks):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = webhooks
    session.execute.return_value = mock_result
    return session


def _mock_session_for_get(webhook):
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = webhook
    session.execute.return_value = mock_result
    return session


# --- POST /v1/webhooks ---


@pytest.mark.asyncio
async def test_create_webhook(client):
    """Successfully create a webhook subscription."""
    mock_session = _mock_session_for_create(existing_count=0)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["data.updated"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["url"] == "https://example.com/hook"
    assert body["events"] == ["data.updated"]
    assert body["active"] is True


@pytest.mark.asyncio
async def test_create_webhook_invalid_event(client):
    """Invalid event type returns 400."""
    mock_session = _mock_session_for_create()

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["invalid.event"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Invalid event types" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_webhook_limit_exceeded(client):
    """Exceeding per-key webhook limit returns 400."""
    mock_session = _mock_session_for_create(existing_count=10)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["data.updated"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Maximum" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_webhook_with_filters(client):
    """Create webhook with filters and secret."""
    mock_session = _mock_session_for_create(existing_count=0)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["data.updated", "threshold.exceeded"],
                "filters": {
                    "state_fips": ["27"],
                    "thresholds": {"poverty_rate": {"operator": ">", "value": 20}},
                },
                "secret": "mysecretkey",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert set(body["events"]) == {"data.updated", "threshold.exceeded"}


# --- GET /v1/webhooks ---


@pytest.mark.asyncio
async def test_list_webhooks(client):
    """List returns all webhooks for the authenticated key."""
    webhooks = [
        _make_mock_webhook(id_=1, url="https://a.com/hook"),
        _make_mock_webhook(id_=2, url="https://b.com/hook"),
    ]
    mock_session = _mock_session_for_list(webhooks)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/webhooks")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["webhooks"]) == 2


@pytest.mark.asyncio
async def test_list_webhooks_empty(client):
    """List returns empty when no webhooks exist."""
    mock_session = _mock_session_for_list([])

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/webhooks")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --- GET /v1/webhooks/{id} ---


@pytest.mark.asyncio
async def test_get_webhook(client):
    """Get a specific webhook by ID."""
    webhook = _make_mock_webhook(id_=1)
    mock_session = _mock_session_for_get(webhook)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/webhooks/1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_get_webhook_not_found(client):
    """404 when webhook does not exist."""
    mock_session = _mock_session_for_get(None)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/webhooks/999")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


# --- DELETE /v1/webhooks/{id} ---


@pytest.mark.asyncio
async def test_delete_webhook(client):
    """Delete a webhook returns 204."""
    webhook = _make_mock_webhook(id_=1)
    mock_session = _mock_session_for_get(webhook)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.delete("/v1/webhooks/1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    mock_session.delete.assert_called_once_with(webhook)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client):
    """Delete non-existent webhook returns 404."""
    mock_session = _mock_session_for_get(None)

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.delete("/v1/webhooks/999")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


# --- Webhook dispatch service ---


@pytest.mark.asyncio
async def test_webhook_dispatch():
    """Dispatch delivers to matching subscriptions."""
    from geohealth.services.webhooks import dispatch_event

    sub = _make_mock_webhook(id_=1, events=["data.updated"])

    with patch("geohealth.services.webhooks.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await dispatch_event(
            "data.updated",
            {"geoid": "27053001100", "state_fips": "27"},
            [sub],
        )

    assert result["delivered"] == 1
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_webhook_dispatch_filters():
    """Dispatch respects subscription filters."""
    from geohealth.services.webhooks import dispatch_event

    sub = _make_mock_webhook(
        id_=1,
        events=["data.updated"],
        filters={"state_fips": ["06"]},  # California only
    )

    with patch("geohealth.services.webhooks.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await dispatch_event(
            "data.updated",
            {"geoid": "27053001100", "state_fips": "27"},  # Minnesota
            [sub],
        )

    # Should not deliver because state filter doesn't match
    assert result["delivered"] == 0
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_webhook_dispatch_inactive():
    """Dispatch skips inactive subscriptions."""
    from geohealth.services.webhooks import dispatch_event

    sub = _make_mock_webhook(id_=1, events=["data.updated"], active=False)

    result = await dispatch_event(
        "data.updated",
        {"geoid": "27053001100"},
        [sub],
    )

    assert result["delivered"] == 0
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_webhook_dispatch_delivery_failure():
    """Dispatch counts failed deliveries."""
    from geohealth.services.webhooks import dispatch_event

    sub = _make_mock_webhook(id_=1, events=["data.updated"])

    with patch("geohealth.services.webhooks.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await dispatch_event(
            "data.updated",
            {"geoid": "27053001100"},
            [sub],
        )

    assert result["delivered"] == 0
    assert result["failed"] == 1
