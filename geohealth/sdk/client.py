"""Async and sync HTTP clients for the GeoHealth API."""

from __future__ import annotations

from typing import Any

import httpx

from geohealth.api.schemas import (
    BatchResponse,
    CompareResponse,
    ContextResponse,
    DictionaryResponse,
    HealthResponse,
    NearbyResponse,
    StatsResponse,
)
from geohealth.sdk.exceptions import (
    AuthenticationError,
    GeoHealthError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from geohealth.sdk.models import RateLimitInfo

# Maps HTTP status codes to exception classes.
_STATUS_MAP: dict[int, type[GeoHealthError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthenticationError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
}


def _build_exception(
    status_code: int,
    detail: str,
    rate_limit_info: RateLimitInfo | None,
) -> GeoHealthError:
    """Construct the appropriate exception for *status_code*."""
    exc_cls = _STATUS_MAP.get(status_code, GeoHealthError)
    if exc_cls is RateLimitError:
        return RateLimitError(status_code, detail, rate_limit_info)
    return exc_cls(status_code, detail)


def _parse_detail(response: httpx.Response) -> str:
    """Extract the ``detail`` field from a JSON error body."""
    try:
        body = response.json()
        return body.get("detail", response.text)
    except Exception:
        return response.text


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class AsyncGeoHealthClient:
    """Async client for the GeoHealth API (backed by ``httpx.AsyncClient``)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        *,
        _transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key is not None:
            headers["X-API-Key"] = api_key
        kwargs: dict[str, Any] = {
            "base_url": base_url,
            "headers": headers,
            "timeout": timeout,
        }
        if _transport is not None:
            kwargs["transport"] = _transport
        self._client = httpx.AsyncClient(**kwargs)
        self.last_rate_limit: RateLimitInfo | None = None

    # -- context manager -----------------------------------------------------

    async def __aenter__(self) -> AsyncGeoHealthClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # -- internal ------------------------------------------------------------

    def _handle_response(self, response: httpx.Response) -> None:
        self.last_rate_limit = RateLimitInfo.from_headers(response.headers)
        if response.status_code >= 400:
            detail = _parse_detail(response)
            raise _build_exception(
                response.status_code, detail, self.last_rate_limit,
            )

    # -- public methods ------------------------------------------------------

    async def health(self) -> HealthResponse:
        resp = await self._client.get("/health")
        self._handle_response(resp)
        return HealthResponse.model_validate(resp.json())

    async def context(
        self,
        *,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        narrative: bool = False,
    ) -> ContextResponse:
        params: dict[str, Any] = {}
        if address is not None:
            params["address"] = address
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if narrative:
            params["narrative"] = "true"
        resp = await self._client.get("/v1/context", params=params)
        self._handle_response(resp)
        return ContextResponse.model_validate(resp.json())

    async def batch(self, addresses: list[str]) -> BatchResponse:
        resp = await self._client.post("/v1/batch", json={"addresses": addresses})
        self._handle_response(resp)
        return BatchResponse.model_validate(resp.json())

    async def nearby(
        self,
        *,
        lat: float,
        lng: float,
        radius: float = 5.0,
        limit: int = 25,
        offset: int = 0,
    ) -> NearbyResponse:
        params: dict[str, Any] = {
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "limit": limit,
            "offset": offset,
        }
        resp = await self._client.get("/v1/nearby", params=params)
        self._handle_response(resp)
        return NearbyResponse.model_validate(resp.json())

    async def compare(
        self,
        *,
        geoid1: str,
        geoid2: str | None = None,
        compare_to: str | None = None,
    ) -> CompareResponse:
        params: dict[str, Any] = {"geoid1": geoid1}
        if geoid2 is not None:
            params["geoid2"] = geoid2
        if compare_to is not None:
            params["compare_to"] = compare_to
        resp = await self._client.get("/v1/compare", params=params)
        self._handle_response(resp)
        return CompareResponse.model_validate(resp.json())

    async def stats(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> StatsResponse:
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        resp = await self._client.get("/v1/stats", params=params)
        self._handle_response(resp)
        return StatsResponse.model_validate(resp.json())

    async def dictionary(
        self,
        *,
        category: str | None = None,
    ) -> DictionaryResponse:
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        resp = await self._client.get("/v1/dictionary", params=params)
        self._handle_response(resp)
        return DictionaryResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------


class GeoHealthClient:
    """Synchronous client for the GeoHealth API (backed by ``httpx.Client``)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        *,
        _transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key is not None:
            headers["X-API-Key"] = api_key
        kwargs: dict[str, Any] = {
            "base_url": base_url,
            "headers": headers,
            "timeout": timeout,
        }
        if _transport is not None:
            kwargs["transport"] = _transport
        self._client = httpx.Client(**kwargs)
        self.last_rate_limit: RateLimitInfo | None = None

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> GeoHealthClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- internal ------------------------------------------------------------

    def _handle_response(self, response: httpx.Response) -> None:
        self.last_rate_limit = RateLimitInfo.from_headers(response.headers)
        if response.status_code >= 400:
            detail = _parse_detail(response)
            raise _build_exception(
                response.status_code, detail, self.last_rate_limit,
            )

    # -- public methods ------------------------------------------------------

    def health(self) -> HealthResponse:
        resp = self._client.get("/health")
        self._handle_response(resp)
        return HealthResponse.model_validate(resp.json())

    def context(
        self,
        *,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        narrative: bool = False,
    ) -> ContextResponse:
        params: dict[str, Any] = {}
        if address is not None:
            params["address"] = address
        if lat is not None:
            params["lat"] = lat
        if lng is not None:
            params["lng"] = lng
        if narrative:
            params["narrative"] = "true"
        resp = self._client.get("/v1/context", params=params)
        self._handle_response(resp)
        return ContextResponse.model_validate(resp.json())

    def batch(self, addresses: list[str]) -> BatchResponse:
        resp = self._client.post("/v1/batch", json={"addresses": addresses})
        self._handle_response(resp)
        return BatchResponse.model_validate(resp.json())

    def nearby(
        self,
        *,
        lat: float,
        lng: float,
        radius: float = 5.0,
        limit: int = 25,
        offset: int = 0,
    ) -> NearbyResponse:
        params: dict[str, Any] = {
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "limit": limit,
            "offset": offset,
        }
        resp = self._client.get("/v1/nearby", params=params)
        self._handle_response(resp)
        return NearbyResponse.model_validate(resp.json())

    def compare(
        self,
        *,
        geoid1: str,
        geoid2: str | None = None,
        compare_to: str | None = None,
    ) -> CompareResponse:
        params: dict[str, Any] = {"geoid1": geoid1}
        if geoid2 is not None:
            params["geoid2"] = geoid2
        if compare_to is not None:
            params["compare_to"] = compare_to
        resp = self._client.get("/v1/compare", params=params)
        self._handle_response(resp)
        return CompareResponse.model_validate(resp.json())

    def stats(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> StatsResponse:
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        resp = self._client.get("/v1/stats", params=params)
        self._handle_response(resp)
        return StatsResponse.model_validate(resp.json())

    def dictionary(
        self,
        *,
        category: str | None = None,
    ) -> DictionaryResponse:
        params: dict[str, Any] = {}
        if category is not None:
            params["category"] = category
        resp = self._client.get("/v1/dictionary", params=params)
        self._handle_response(resp)
        return DictionaryResponse.model_validate(resp.json())
