"""Thread-safe LRU + TTL in-memory cache."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from app.config import settings


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
                return None
            value, expires_at = self._data[key]
            if time.monotonic() > expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
            elif len(self._data) >= self._maxsize:
                self._data.popitem(last=False)
            self._data[key] = (value, time.monotonic() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)


# Module-level singletons
geocode_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
acs_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
places_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
svi_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
npi_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
hpsa_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
cbp_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl)
