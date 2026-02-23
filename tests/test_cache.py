import time
from unittest.mock import patch

from geohealth.services.cache import TTLCache, make_cache_key


class TestTTLCache:
    def test_get_set(self):
        cache = TTLCache(maxsize=10, ttl=60)
        cache.set("k1", {"data": 1})
        assert cache.get("k1") == {"data": 1}

    def test_miss_returns_none(self):
        cache = TTLCache(maxsize=10, ttl=60)
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        cache = TTLCache(maxsize=10, ttl=1)
        cache.set("k1", "value")
        assert cache.get("k1") == "value"

        # Advance monotonic clock past TTL
        with patch("geohealth.services.cache.time") as mock_time:
            # First call in set already happened; simulate expiry on get
            mock_time.monotonic.return_value = time.monotonic() + 2
            assert cache.get("k1") is None

    def test_lru_eviction(self):
        cache = TTLCache(maxsize=2, ttl=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")  # should evict k1 (LRU)
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"
        assert cache.get("k3") == "v3"

    def test_access_refreshes_lru(self):
        cache = TTLCache(maxsize=2, ttl=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        # Access k1 to make it most recently used
        cache.get("k1")
        # Insert k3 — should evict k2 (now LRU), not k1
        cache.set("k3", "v3")
        assert cache.get("k1") == "v1"
        assert cache.get("k2") is None
        assert cache.get("k3") == "v3"

    def test_clear(self):
        cache = TTLCache(maxsize=10, ttl=60)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0
        assert cache.get("k1") is None

    def test_size_property(self):
        cache = TTLCache(maxsize=10, ttl=60)
        assert cache.size == 0
        cache.set("k1", "v1")
        assert cache.size == 1

    def test_overwrite_existing_key(self):
        cache = TTLCache(maxsize=10, ttl=60)
        cache.set("k1", "old")
        cache.set("k1", "new")
        assert cache.get("k1") == "new"
        assert cache.size == 1


class TestMakeCacheKey:
    def test_rounds_to_4_decimals(self):
        key = make_cache_key(44.97781234, -93.26501234)
        assert key == "44.9778,-93.265"

    def test_different_coords_different_keys(self):
        k1 = make_cache_key(44.9778, -93.265)
        k2 = make_cache_key(44.9779, -93.265)
        assert k1 != k2

    def test_nearby_coords_same_key(self):
        # Within ~11m should round to the same value
        k1 = make_cache_key(44.97780001, -93.26500001)
        k2 = make_cache_key(44.97780009, -93.26500009)
        assert k1 == k2
