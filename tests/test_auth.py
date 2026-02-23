"""Tests for API key authentication, rate limiting, and their integration."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.api.dependencies import get_db
from geohealth.api.main import app
from geohealth.services.rate_limiter import SlidingWindowRateLimiter, rate_limiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db_override():
    """Return a mock async DB session suitable for dependency override."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    return mock_session


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_needs_no_auth(client):
    """The /health endpoint should be accessible without any API key."""
    mock_session = AsyncMock()
    mock_session.execute.return_value = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        with patch("geohealth.config.settings.auth_enabled", True), \
             patch("geohealth.config.settings.api_keys", "test-key"):
            resp = await client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


@pytest.mark.asyncio
async def test_auth_disabled_allows_all(client):
    """/v1/context should work without a key when auth is disabled (default)."""
    with patch("geohealth.config.settings.auth_enabled", False), \
         patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo, \
         patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract:
        mock_geo.return_value = MagicMock(
            lat=44.0, lng=-93.0, matched_address="test",
            state_fips="27", county_fips="053", tract_fips="001100",
        )
        mock_tract.return_value = None
        resp = await client.get("/v1/context", params={"address": "test"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_key_returns_401(client):
    """When auth is enabled, a request with no X-API-Key header should get 401."""
    with patch("geohealth.config.settings.auth_enabled", True), \
         patch("geohealth.config.settings.api_keys", "valid-key"):
        resp = await client.get("/v1/context", params={"address": "test"})
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_key_returns_403(client):
    """When auth is enabled, a request with a wrong key should get 403."""
    with patch("geohealth.config.settings.auth_enabled", True), \
         patch("geohealth.config.settings.api_keys", "valid-key"):
        resp = await client.get(
            "/v1/context",
            params={"address": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert resp.status_code == 403
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_valid_key_succeeds(client):
    """When auth is enabled, a request with a valid key should be accepted."""
    with patch("geohealth.config.settings.auth_enabled", True), \
         patch("geohealth.config.settings.api_keys", "valid-key"), \
         patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo, \
         patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract:
        mock_geo.return_value = MagicMock(
            lat=44.0, lng=-93.0, matched_address="test",
            state_fips="27", county_fips="053", tract_fips="001100",
        )
        mock_tract.return_value = None
        resp = await client.get(
            "/v1/context",
            params={"address": "test"},
            headers={"X-API-Key": "valid-key"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stats_also_protected(client):
    """The /v1/stats endpoint should also require auth when enabled."""
    with patch("geohealth.config.settings.auth_enabled", True), \
         patch("geohealth.config.settings.api_keys", "valid-key"):
        resp = await client.get("/v1/stats")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestSlidingWindowRateLimiter:
    def test_allows_under_limit(self):
        rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            allowed, _ = rl.is_allowed("key-a")
            assert allowed is True

    def test_blocks_over_limit(self):
        rl = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("key-a")
        rl.is_allowed("key-a")
        allowed, headers = rl.is_allowed("key-a")
        assert allowed is False
        assert headers["X-RateLimit-Remaining"] == "0"

    def test_different_keys_independent(self):
        rl = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        allowed_a, _ = rl.is_allowed("key-a")
        allowed_b, _ = rl.is_allowed("key-b")
        assert allowed_a is True
        assert allowed_b is True

    def test_window_expiry(self):
        rl = SlidingWindowRateLimiter(max_requests=1, window_seconds=1)
        allowed, _ = rl.is_allowed("key-a")
        assert allowed is True

        # Simulate window passing — capture real time before patching
        future = time.monotonic() + 2
        with patch("geohealth.services.rate_limiter.time.monotonic", return_value=future):
            allowed, _ = rl.is_allowed("key-a")
            assert allowed is True

    def test_headers_info(self):
        rl = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
        _, headers = rl.is_allowed("key-a")
        assert headers["X-RateLimit-Limit"] == "5"
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_clear_resets_state(self):
        rl = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        rl.is_allowed("key-a")
        allowed, _ = rl.is_allowed("key-a")
        assert allowed is False

        rl.clear()
        allowed, _ = rl.is_allowed("key-a")
        assert allowed is True


# ---------------------------------------------------------------------------
# Integration: rate limit returns 429 with headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client):
    """Exceeding the rate limit should return 429 with X-RateLimit-* headers."""
    # Use a very low limit
    rate_limiter._max_requests = 2
    try:
        app.dependency_overrides[get_db] = _mock_db_override
        with patch("geohealth.config.settings.auth_enabled", False):
            # First two requests consume the limit
            for _ in range(2):
                resp = await client.get("/v1/stats")
                assert resp.status_code == 200
                assert "X-RateLimit-Limit" in resp.headers

            # Third request should be rate-limited
            resp = await client.get("/v1/stats")
            assert resp.status_code == 429
            assert "X-RateLimit-Limit" in resp.headers
            assert resp.json()["detail"] == "Rate limit exceeded"
    finally:
        rate_limiter._max_requests = 60
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Key hashing tests
# ---------------------------------------------------------------------------


class TestKeyHashing:
    def test_hash_key_deterministic(self):
        from geohealth.api.auth import _hash_key

        h1 = _hash_key("my-secret")
        h2 = _hash_key("my-secret")
        assert h1 == h2
        assert len(h1) == 64

    def test_plaintext_key_is_hashed(self):
        """Plaintext keys in API_KEYS are hashed for comparison."""
        from geohealth.api.auth import _hash_key, _valid_key_hashes

        with patch("geohealth.config.settings.api_keys", "plain-key"):
            hashes = _valid_key_hashes()
        assert _hash_key("plain-key") in hashes

    def test_prehashed_key_used_directly(self):
        """A 64-char hex string in API_KEYS is treated as pre-hashed."""
        from geohealth.api.auth import _hash_key, _valid_key_hashes

        pre_hashed = _hash_key("my-secret")
        with patch("geohealth.config.settings.api_keys", pre_hashed):
            hashes = _valid_key_hashes()
        assert pre_hashed in hashes

    @pytest.mark.asyncio
    async def test_auth_works_with_hashed_key_env(self, client):
        """Auth succeeds when API_KEYS contains the SHA-256 hash of the submitted key."""
        from geohealth.api.auth import _hash_key

        pre_hashed = _hash_key("valid-key")
        with patch("geohealth.config.settings.auth_enabled", True), \
             patch("geohealth.config.settings.api_keys", pre_hashed), \
             patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock) as mock_geo, \
             patch("geohealth.api.routes.context.lookup_tract", new_callable=AsyncMock) as mock_tract:
            mock_geo.return_value = MagicMock(
                lat=44.0, lng=-93.0, matched_address="test",
                state_fips="27", county_fips="053", tract_fips="001100",
            )
            mock_tract.return_value = None
            resp = await client.get(
                "/v1/context",
                params={"address": "test"},
                headers={"X-API-Key": "valid-key"},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_require_api_key_returns_hash(self):
        """require_api_key should return the hashed key, not the plaintext."""
        from geohealth.api.auth import _hash_key, require_api_key

        with patch("geohealth.config.settings.auth_enabled", True), \
             patch("geohealth.config.settings.api_keys", "valid-key"):
            result = await require_api_key(api_key="valid-key")
        assert result == _hash_key("valid-key")
        assert result != "valid-key"
