"""Lightweight models used by the SDK client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RateLimitInfo:
    """Rate-limit metadata parsed from response headers."""

    limit: int
    remaining: int
    reset: int

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> RateLimitInfo | None:
        """Parse ``X-RateLimit-*`` headers, returning *None* if absent."""
        raw_limit = headers.get("x-ratelimit-limit")
        raw_remaining = headers.get("x-ratelimit-remaining")
        raw_reset = headers.get("x-ratelimit-reset")
        if raw_limit is None or raw_remaining is None or raw_reset is None:
            return None
        return cls(
            limit=int(raw_limit),
            remaining=int(raw_remaining),
            reset=int(raw_reset),
        )
