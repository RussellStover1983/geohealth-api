"""In-memory sliding-window rate limiter."""

from __future__ import annotations

import threading
import time
from collections import deque

from geohealth.config import settings


class SlidingWindowRateLimiter:
    """Thread-safe per-key sliding-window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> tuple[bool, dict[str, str]]:
        """Check whether *key* may proceed.

        Returns ``(allowed, headers)`` where *headers* is a dict of
        ``X-RateLimit-*`` headers to attach to the response.
        """
        now = time.monotonic()
        window_start = now - self._window

        with self._lock:
            dq = self._buckets.setdefault(key, deque())

            # Discard timestamps outside the current window
            while dq and dq[0] <= window_start:
                dq.popleft()

            remaining = max(self._max_requests - len(dq) - 1, 0)
            reset = int(self._window - (now - dq[0]) if dq else self._window)

            headers = {
                "X-RateLimit-Limit": str(self._max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset),
            }

            if len(dq) >= self._max_requests:
                return False, headers

            dq.append(now)
            return True, headers

    def clear(self) -> None:
        """Remove all tracked state (useful in tests)."""
        with self._lock:
            self._buckets.clear()


# Module-level singleton initialized from config
rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.rate_limit_per_minute,
    window_seconds=settings.rate_limit_window,
)
