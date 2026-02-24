"""Thread-safe in-memory application metrics collector."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    """Collects counters and latency samples for observability.

    Thread-safe via a single ``threading.Lock``.  The latency list is
    bounded at ``_MAX_LATENCY_SAMPLES``; when exceeded it is halved by
    keeping only the most-recent entries.
    """

    _MAX_LATENCY_SAMPLES: int = field(default=10_000, repr=False)

    # Counters
    total_requests: int = field(default=0, init=False)
    status_codes: dict[int, int] = field(default_factory=dict, init=False)
    cache_hits: int = field(default=0, init=False)
    cache_misses: int = field(default=0, init=False)
    geocoder_census_ok: int = field(default=0, init=False)
    geocoder_nominatim_ok: int = field(default=0, init=False)
    geocoder_failures: int = field(default=0, init=False)
    narrative_ok: int = field(default=0, init=False)
    narrative_failures: int = field(default=0, init=False)
    auth_failures: int = field(default=0, init=False)

    # Latency samples (milliseconds)
    _latencies: list[float] = field(default_factory=list, init=False, repr=False)

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _start_time: float = field(default_factory=time.monotonic, init=False, repr=False)

    # -- Counter helpers ---------------------------------------------------

    def inc_request(self, status_code: int) -> None:
        with self._lock:
            self.total_requests += 1
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

    def inc_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def inc_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def inc_geocoder(self, source: str) -> None:
        with self._lock:
            if source == "census":
                self.geocoder_census_ok += 1
            elif source == "nominatim":
                self.geocoder_nominatim_ok += 1
            else:
                self.geocoder_failures += 1

    def inc_narrative(self, success: bool) -> None:
        with self._lock:
            if success:
                self.narrative_ok += 1
            else:
                self.narrative_failures += 1

    def inc_auth_failure(self) -> None:
        with self._lock:
            self.auth_failures += 1

    # -- Latency -----------------------------------------------------------

    def record_latency(self, ms: float) -> None:
        with self._lock:
            self._latencies.append(ms)
            if len(self._latencies) > self._MAX_LATENCY_SAMPLES:
                # Keep only the most-recent half
                half = self._MAX_LATENCY_SAMPLES // 2
                self._latencies = self._latencies[-half:]

    def get_latency_percentiles(self) -> dict[str, float]:
        with self._lock:
            return self._percentiles_unlocked()

    def _percentiles_unlocked(self) -> dict[str, float]:
        """Compute p50/p90/p95/p99 — caller must hold ``_lock``."""
        if not self._latencies:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
        s = sorted(self._latencies)
        n = len(s)
        return {
            "p50": round(s[int(n * 0.50)], 2),
            "p90": round(s[int(min(n * 0.90, n - 1))], 2),
            "p95": round(s[int(min(n * 0.95, n - 1))], 2),
            "p99": round(s[int(min(n * 0.99, n - 1))], 2),
        }

    # -- Snapshot / reset --------------------------------------------------

    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self._start_time, 2)

    def snapshot(self) -> dict:
        with self._lock:
            total = self.cache_hits + self.cache_misses
            hit_rate = round(self.cache_hits / total, 4) if total else 0.0
            return {
                "uptime_seconds": round(time.monotonic() - self._start_time, 2),
                "total_requests": self.total_requests,
                "status_codes": dict(self.status_codes),
                "cache": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_rate": hit_rate,
                },
                "geocoder": {
                    "census_ok": self.geocoder_census_ok,
                    "nominatim_ok": self.geocoder_nominatim_ok,
                    "failures": self.geocoder_failures,
                },
                "narrative": {
                    "ok": self.narrative_ok,
                    "failures": self.narrative_failures,
                },
                "auth_failures": self.auth_failures,
                "latency_ms": self._percentiles_unlocked(),
            }

    def reset(self) -> None:
        with self._lock:
            self.total_requests = 0
            self.status_codes.clear()
            self.cache_hits = 0
            self.cache_misses = 0
            self.geocoder_census_ok = 0
            self.geocoder_nominatim_ok = 0
            self.geocoder_failures = 0
            self.narrative_ok = 0
            self.narrative_failures = 0
            self.auth_failures = 0
            self._latencies.clear()
            self._start_time = time.monotonic()


# Module-level singleton
metrics = MetricsCollector()
