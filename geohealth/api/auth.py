"""API key authentication dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from geohealth.config import settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _valid_keys() -> set[str]:
    """Parse comma-separated API_KEYS setting into a set."""
    if not settings.api_keys:
        return set()
    return {k.strip() for k in settings.api_keys.split(",") if k.strip()}


async def require_api_key(
    api_key: str | None = Security(_header),
) -> str:
    """Validate the X-API-Key header.

    When auth is disabled (default), returns ``"__anonymous__"`` so callers
    always receive a key string for rate-limiting purposes.
    """
    if not settings.auth_enabled:
        return "__anonymous__"

    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    if api_key not in _valid_keys():
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
