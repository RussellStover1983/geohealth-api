"""API key authentication dependency with SHA-256 hashing."""

from __future__ import annotations

import hashlib
import logging

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from geohealth.config import settings

logger = logging.getLogger("geohealth.auth")

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
    valid = _valid_key_hashes()
    # Temporary debug logging (remove after Railway auth verified)
    logger.warning(
        "AUTH REQUEST: received_key=%r (len=%d), hashed=%s, "
        "valid_hashes=%d, match=%s",
        api_key[:4] + "..." if len(api_key) > 4 else api_key,
        len(api_key),
        hashed[:16],
        len(valid),
        hashed in valid,
    )
    if hashed not in valid:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return hashed
