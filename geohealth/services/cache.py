"""Thread-safe LRU + TTL response cache for context lookups."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from geohealth.config import settings
from geohealth.services.metrics import metrics


class TTLCache:
    """Thread-safe LRU cache with per-entry TTL expiration."""

    def __init__(self, maxsize: int = 4096, ttl: int = 3600):
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._data:
                metrics.inc_cache_miss()
                return None
            value, expires_at = self._data[key]
            if time.monotonic() > expires_at:
                del self._data[key]
                metrics.inc_cache_miss()
                return None
            # Refresh LRU position
            self._data.move_to_end(key)
            metrics.inc_cache_hit()
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
            elif len(self._data) >= self._maxsize:
                # Evict least-recently-used entry
                self._data.popitem(last=False)
            self._data[key] = (value, time.monotonic() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)


def make_cache_key(lat: float, lng: float) -> str:
    """Round coordinates to 4 decimal places (~11m precision) for cache keying."""
    return f"{round(lat, 4)},{round(lng, 4)}"


# Module-level singleton initialized from config
context_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
