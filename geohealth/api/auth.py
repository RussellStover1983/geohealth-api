"""API key authentication dependency with SHA-256 hashing."""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from geohealth.config import settings

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(key: str) -> str:
    """Return the SHA-256 hex digest of a key."""
    return hashlib.sha256(key.encode()).hexdigest()


def _valid_key_hashes() -> set[str]:
    """Parse comma-separated API_KEYS setting into a set of hashes.

    64-character hex strings are treated as pre-hashed values.
    Shorter strings are hashed on the fly (backward compatible).
    """
    if not settings.api_keys:
        return set()
    hashes = set()
    for k in settings.api_keys.split(","):
        k = k.strip()
        if not k:
            continue
        if len(k) == 64:
            try:
                int(k, 16)
                hashes.add(k)
                continue
            except ValueError:
                pass
        hashes.add(_hash_key(k))
    return hashes


async def require_api_key(
    api_key: str | None = Security(_header),
) -> str:
    """Validate the X-API-Key header.

    When auth is disabled (default), returns ``"__anonymous__"`` so callers
    always receive a key string for rate-limiting purposes.

    Returns the hashed key (not plaintext) so rate limiter buckets are
    keyed by hash rather than raw secrets.
    """
    if not settings.auth_enabled:
        return "__anonymous__"

    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    hashed = _hash_key(api_key)
    if hashed not in _valid_key_hashes():
        raise HTTPException(status_code=403, detail="Invalid API key")

    return hashed
