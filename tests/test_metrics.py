"""Tests for the MetricsCollector."""

from __future__ import annotations

from geohealth.services.metrics import MetricsCollector


def _fresh() -> MetricsCollector:
    return MetricsCollector()


def test_inc_request():
    m = _fresh()
    m.inc_request(200)
    m.inc_request(200)
    m.inc_request(404)
    assert m.total_requests == 3
    assert m.status_codes == {200: 2, 404: 1}


def test_inc_cache_hit_miss():
    m = _fresh()
    m.inc_cache_hit()
    m.inc_cache_hit()
    m.inc_cache_miss()
    assert m.cache_hits == 2
    assert m.cache_misses == 1


def test_inc_geocoder_census():
    m = _fresh()
    m.inc_geocoder("census")
    assert m.geocoder_census_ok == 1


def test_inc_geocoder_nominatim():
    m = _fresh()
    m.inc_geocoder("nominatim")
    assert m.geocoder_nominatim_ok == 1


def test_inc_geocoder_failure():
    m = _fresh()
    m.inc_geocoder("failure")
    assert m.geocoder_failures == 1


def test_inc_narrative():
    m = _fresh()
    m.inc_narrative(True)
    m.inc_narrative(False)
    m.inc_narrative(False)
    assert m.narrative_ok == 1
    assert m.narrative_failures == 2


def test_inc_auth_failure():
    m = _fresh()
    m.inc_auth_failure()
    assert m.auth_failures == 1


def test_latency_percentiles_empty():
    m = _fresh()
    p = m.get_latency_percentiles()
    assert p == {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}


def test_latency_percentiles_populated():
    m = _fresh()
    for i in range(1, 101):
        m.record_latency(float(i))
    p = m.get_latency_percentiles()
    assert 50.0 <= p["p50"] <= 51.0
    assert p["p90"] >= 90.0
    assert p["p99"] >= 99.0


def test_snapshot_structure():
    m = _fresh()
    m.inc_request(200)
    m.inc_cache_hit()
    m.record_latency(10.5)
    s = m.snapshot()
    assert "uptime_seconds" in s
    assert s["total_requests"] == 1
    assert s["cache"]["hits"] == 1
    assert "latency_ms" in s
    assert "p50" in s["latency_ms"]


def test_reset():
    m = _fresh()
    m.inc_request(200)
    m.inc_cache_hit()
    m.record_latency(5.0)
    m.reset()
    assert m.total_requests == 0
    assert m.cache_hits == 0
    s = m.snapshot()
    assert s["total_requests"] == 0


def test_latency_bounding():
    m = MetricsCollector()
    # Exceed _MAX_LATENCY_SAMPLES
    for i in range(10_001):
        m.record_latency(float(i))
    # After bounding, should have _MAX_LATENCY_SAMPLES // 2 entries
    assert len(m._latencies) == 5_000
