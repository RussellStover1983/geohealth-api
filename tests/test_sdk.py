"""Tests for geohealth.sdk — async & sync clients, exceptions, rate-limit parsing."""

from __future__ import annotations

import json

import httpx
import pytest

from geohealth.api.schemas import (
    BatchResponse,
    CompareResponse,
    ContextResponse,
    HealthResponse,
    NearbyResponse,
    StatsResponse,
)
from geohealth.sdk import (
    AsyncGeoHealthClient,
    AuthenticationError,
    GeoHealthClient,
    GeoHealthError,
    NotFoundError,
    RateLimitError,
    RateLimitInfo,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RATE_HEADERS = {
    "x-ratelimit-limit": "60",
    "x-ratelimit-remaining": "59",
    "x-ratelimit-reset": "42",
}

_HEALTH_BODY = {"status": "ok", "database": "connected", "detail": None}

_CONTEXT_BODY = {
    "location": {"lat": 44.97, "lng": -93.26, "matched_address": "123 Main St"},
    "tract": {
        "geoid": "27053026200",
        "state_fips": "27",
        "county_fips": "053",
        "tract_code": "026200",
    },
    "narrative": None,
    "data": None,
}

_BATCH_BODY = {
    "total": 1,
    "succeeded": 1,
    "failed": 0,
    "results": [
        {
            "address": "123 Main St",
            "status": "ok",
            "location": {"lat": 44.97, "lng": -93.26, "matched_address": "123 Main St"},
            "tract": {
                "geoid": "27053026200",
                "state_fips": "27",
                "county_fips": "053",
                "tract_code": "026200",
            },
            "error": None,
        }
    ],
}

_NEARBY_BODY = {
    "center": {"lat": 44.97, "lng": -93.26},
    "radius_miles": 5.0,
    "count": 1,
    "total": 1,
    "offset": 0,
    "limit": 25,
    "tracts": [
        {
            "geoid": "27053026200",
            "name": "Tract 262",
            "distance_miles": 1.2,
            "total_population": 4500,
            "median_household_income": 72000.0,
            "poverty_rate": 11.0,
            "uninsured_rate": 5.0,
            "unemployment_rate": 4.0,
            "median_age": 34.0,
            "sdoh_index": 0.4,
        }
    ],
}

_COMPARE_BODY = {
    "a": {
        "type": "tract",
        "geoid": "27053026200",
        "label": "Tract 262",
        "values": {
            "total_population": 4500,
            "median_household_income": 72000.0,
            "poverty_rate": 11.0,
            "uninsured_rate": 5.0,
            "unemployment_rate": 4.0,
            "median_age": 34.0,
            "sdoh_index": 0.4,
        },
    },
    "b": {
        "type": "state_average",
        "geoid": None,
        "label": "State 27 average",
        "values": {
            "total_population": 4000,
            "median_household_income": 65000.0,
            "poverty_rate": 13.0,
            "uninsured_rate": 7.0,
            "unemployment_rate": 5.0,
            "median_age": 36.0,
            "sdoh_index": 0.5,
        },
    },
    "differences": {
        "total_population": 500,
        "median_household_income": 7000.0,
        "poverty_rate": -2.0,
        "uninsured_rate": -2.0,
        "unemployment_rate": -1.0,
        "median_age": -2.0,
        "sdoh_index": -0.1,
    },
}

_STATS_BODY = {
    "total_states": 1,
    "total_tracts": 100,
    "offset": 0,
    "limit": 50,
    "states": [{"state_fips": "27", "tract_count": 100}],
}


def _json_response(
    body: dict,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    hdrs = dict(_RATE_HEADERS)
    if headers:
        hdrs.update(headers)
    return httpx.Response(
        status_code,
        json=body,
        headers=hdrs,
    )


def _error_response(
    status_code: int,
    detail: str = "error",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    body = {"error": True, "status_code": status_code, "detail": detail}
    hdrs = dict(_RATE_HEADERS)
    if headers:
        hdrs.update(headers)
    return httpx.Response(status_code, json=body, headers=hdrs)


# ---------------------------------------------------------------------------
# RateLimitInfo
# ---------------------------------------------------------------------------


class TestRateLimitInfo:
    def test_from_headers_present(self):
        info = RateLimitInfo.from_headers(_RATE_HEADERS)
        assert info is not None
        assert info.limit == 60
        assert info.remaining == 59
        assert info.reset == 42

    def test_from_headers_absent(self):
        assert RateLimitInfo.from_headers({}) is None

    def test_from_headers_partial(self):
        assert RateLimitInfo.from_headers({"x-ratelimit-limit": "60"}) is None

    def test_frozen(self):
        info = RateLimitInfo(limit=60, remaining=59, reset=42)
        with pytest.raises(AttributeError):
            info.limit = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Async client — success paths
# ---------------------------------------------------------------------------


class TestAsyncClientSuccess:
    async def test_health(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            result = await c.health()
        assert isinstance(result, HealthResponse)
        assert result.status == "ok"

    async def test_context_by_address(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/context"
            assert "address" in str(request.url)
            return _json_response(_CONTEXT_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.context(address="123 Main St")
        assert isinstance(result, ContextResponse)
        assert result.location.lat == 44.97

    async def test_context_by_coords(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "lat=44.97" in str(request.url)
            assert "lng=-93.26" in str(request.url)
            return _json_response(_CONTEXT_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.context(lat=44.97, lng=-93.26)
        assert isinstance(result, ContextResponse)

    async def test_context_narrative_param(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "narrative=true" in str(request.url)
            return _json_response(_CONTEXT_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            await c.context(address="x", narrative=True)

    async def test_batch(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/batch"
            body = json.loads(request.content)
            assert body == {"addresses": ["123 Main St"]}
            return _json_response(_BATCH_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.batch(["123 Main St"])
        assert isinstance(result, BatchResponse)
        assert result.succeeded == 1

    async def test_nearby(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/nearby"
            url_str = str(request.url)
            assert "lat=44.97" in url_str
            assert "radius=3.0" in url_str
            return _json_response(_NEARBY_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.nearby(lat=44.97, lng=-93.26, radius=3.0)
        assert isinstance(result, NearbyResponse)
        assert result.tracts[0].geoid == "27053026200"

    async def test_compare(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/compare"
            url_str = str(request.url)
            assert "geoid1=27053026200" in url_str
            assert "compare_to=state" in url_str
            return _json_response(_COMPARE_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.compare(geoid1="27053026200", compare_to="state")
        assert isinstance(result, CompareResponse)
        assert result.a.geoid == "27053026200"

    async def test_stats(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/stats"
            return _json_response(_STATS_BODY)

        transport = httpx.MockTransport(handler)
        async with AsyncGeoHealthClient(
            "http://test", api_key="k", _transport=transport
        ) as c:
            result = await c.stats()
        assert isinstance(result, StatsResponse)
        assert result.total_tracts == 100


# ---------------------------------------------------------------------------
# Async client — error mapping
# ---------------------------------------------------------------------------


class TestAsyncClientErrors:
    async def test_401_raises_auth_error(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(401, "Missing API key")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(AuthenticationError) as exc_info:
                await c.health()
            assert exc_info.value.status_code == 401

    async def test_403_raises_auth_error(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(403, "Invalid API key")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(AuthenticationError) as exc_info:
                await c.health()
            assert exc_info.value.status_code == 403

    async def test_404_raises_not_found(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(404, "Not found")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(NotFoundError):
                await c.compare(geoid1="00000000000", geoid2="11111111111")

    async def test_429_raises_rate_limit(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(429, "Rate limit exceeded")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(RateLimitError) as exc_info:
                await c.context(address="x")
            assert exc_info.value.rate_limit_info is not None
            assert exc_info.value.rate_limit_info.limit == 60

    async def test_400_raises_validation(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(400, "Bad request")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(ValidationError):
                await c.context(address="x")

    async def test_422_raises_validation(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(422, "Unprocessable")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(ValidationError):
                await c.nearby(lat=44.97, lng=-93.26)

    async def test_500_raises_base_error(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(500, "Internal error")
        )
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(GeoHealthError) as exc_info:
                await c.health()
            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Async client — rate-limit tracking
# ---------------------------------------------------------------------------


class TestAsyncRateLimitTracking:
    async def test_last_rate_limit_set_on_success(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            assert c.last_rate_limit is None
            await c.health()
            assert c.last_rate_limit is not None
            assert c.last_rate_limit.remaining == 59

    async def test_last_rate_limit_none_without_headers(self):
        resp = httpx.Response(200, json=_HEALTH_BODY)
        transport = httpx.MockTransport(lambda req: resp)
        async with AsyncGeoHealthClient("http://test", _transport=transport) as c:
            await c.health()
            assert c.last_rate_limit is None


# ---------------------------------------------------------------------------
# Async client — context manager lifecycle
# ---------------------------------------------------------------------------


class TestAsyncLifecycle:
    async def test_context_manager(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        client = AsyncGeoHealthClient("http://test", _transport=transport)
        async with client as c:
            await c.health()
        assert client._client.is_closed

    async def test_explicit_close(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        client = AsyncGeoHealthClient("http://test", _transport=transport)
        await client.health()
        await client.close()
        assert client._client.is_closed


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------


class TestSyncClient:
    def test_health(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        with GeoHealthClient("http://test", _transport=transport) as c:
            result = c.health()
        assert isinstance(result, HealthResponse)
        assert result.status == "ok"

    def test_context(self):
        transport = httpx.MockTransport(lambda req: _json_response(_CONTEXT_BODY))
        with GeoHealthClient("http://test", api_key="k", _transport=transport) as c:
            result = c.context(address="123 Main St")
        assert isinstance(result, ContextResponse)

    def test_error_mapping(self):
        transport = httpx.MockTransport(
            lambda req: _error_response(403, "Forbidden")
        )
        with GeoHealthClient("http://test", _transport=transport) as c:
            with pytest.raises(AuthenticationError):
                c.health()

    def test_rate_limit_tracking(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        with GeoHealthClient("http://test", _transport=transport) as c:
            c.health()
            assert c.last_rate_limit is not None
            assert c.last_rate_limit.limit == 60

    def test_context_manager_lifecycle(self):
        transport = httpx.MockTransport(lambda req: _json_response(_HEALTH_BODY))
        client = GeoHealthClient("http://test", _transport=transport)
        with client as c:
            c.health()
        assert client._client.is_closed

    def test_api_key_header_sent(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("x-api-key") == "my-secret"
            return _json_response(_HEALTH_BODY)

        transport = httpx.MockTransport(handler)
        with GeoHealthClient(
            "http://test", api_key="my-secret", _transport=transport
        ) as c:
            c.health()
