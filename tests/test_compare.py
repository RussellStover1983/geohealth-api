"""Tests for GET /v1/compare endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from geohealth.services.rate_limiter import rate_limiter


def _make_mock_tract(geoid="27053001100", name="Census Tract 11", state_fips="27"):
    tract = MagicMock()
    tract.geoid = geoid
    tract.state_fips = state_fips
    tract.county_fips = "053"
    tract.tract_code = "001100"
    tract.name = name
    tract.total_population = 4500
    tract.median_household_income = 52000.0
    tract.poverty_rate = 18.5
    tract.uninsured_rate = 12.3
    tract.unemployment_rate = 7.1
    tract.median_age = 34.2
    tract.sdoh_index = 0.72
    return tract


def _make_mock_tract_b(geoid="27053002200", name="Census Tract 22"):
    tract = MagicMock()
    tract.geoid = geoid
    tract.state_fips = "27"
    tract.county_fips = "053"
    tract.tract_code = "002200"
    tract.name = name
    tract.total_population = 6000
    tract.median_household_income = 65000.0
    tract.poverty_rate = 10.2
    tract.uninsured_rate = 8.1
    tract.unemployment_rate = 4.5
    tract.median_age = 38.0
    tract.sdoh_index = 0.45
    return tract


def _mock_session_for_tracts(*tracts):
    """Build a mock session that returns tracts in order for sequential execute calls."""
    session = AsyncMock()
    results = []
    for t in tracts:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = t
        results.append(mock_result)
    session.execute.side_effect = results
    return session


def _mock_session_tract_then_avg(tract, avg_values):
    """Build a mock session: first call returns tract, second returns avg row."""
    session = AsyncMock()

    tract_result = MagicMock()
    tract_result.scalar_one_or_none.return_value = tract

    avg_row = MagicMock()
    for field, val in avg_values.items():
        setattr(avg_row, field, val)
    avg_result = MagicMock()
    avg_result.one.return_value = avg_row

    session.execute.side_effect = [tract_result, avg_result]
    return session


@pytest.mark.asyncio
async def test_compare_missing_geoid1(client):
    """Missing geoid1 → 422."""
    resp = await client.get("/v1/compare")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_compare_neither_geoid2_nor_compare_to(client):
    """Neither geoid2 nor compare_to → 400."""
    mock_session = _mock_session_for_tracts(_make_mock_tract())

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={"geoid1": "27053001100"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Provide either" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_both_geoid2_and_compare_to(client):
    """Both geoid2 and compare_to → 400."""
    mock_session = _mock_session_for_tracts(_make_mock_tract())

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "geoid2": "27053002200",
            "compare_to": "state",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "not both" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_invalid_compare_to(client):
    """Invalid compare_to value → 400."""
    mock_session = _mock_session_for_tracts(_make_mock_tract())

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "compare_to": "invalid",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "'compare_to' must be" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_tract_vs_county(client):
    """Tract vs county average comparison."""
    tract_a = _make_mock_tract()
    avg_values = {
        "total_population": 4800.0,
        "median_household_income": 54000.0,
        "poverty_rate": 14.0,
        "uninsured_rate": 9.5,
        "unemployment_rate": 5.5,
        "median_age": 35.0,
        "sdoh_index": 0.55,
    }
    mock_session = _mock_session_tract_then_avg(tract_a, avg_values)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "compare_to": "county",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["a"]["type"] == "tract"
    assert body["b"]["type"] == "county_average"
    assert "County 27053" in body["b"]["label"]
    # poverty_rate diff: 18.5 - 14.0 = 4.5
    assert body["differences"]["poverty_rate"] == pytest.approx(4.5, abs=0.01)


@pytest.mark.asyncio
async def test_compare_geoid1_not_found(client):
    """Tract A not found → 404."""
    mock_session = _mock_session_for_tracts(None)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "compare_to": "state",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_geoid2_not_found(client):
    """Tract B not found → 404."""
    mock_session = _mock_session_for_tracts(_make_mock_tract(), None)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "geoid2": "27053002200",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert "27053002200" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_compare_tract_vs_tract(client):
    """Tract vs tract comparison returns correct differences."""
    tract_a = _make_mock_tract()
    tract_b = _make_mock_tract_b()
    mock_session = _mock_session_for_tracts(tract_a, tract_b)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "geoid2": "27053002200",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["a"]["type"] == "tract"
    assert body["a"]["geoid"] == "27053001100"
    assert body["b"]["type"] == "tract"
    assert body["b"]["geoid"] == "27053002200"
    # poverty_rate diff: 18.5 - 10.2 = 8.3
    assert body["differences"]["poverty_rate"] == pytest.approx(8.3, abs=0.01)
    # sdoh_index diff: 0.72 - 0.45 = 0.27
    assert body["differences"]["sdoh_index"] == pytest.approx(0.27, abs=0.01)


@pytest.mark.asyncio
async def test_compare_tract_vs_state(client):
    """Tract vs state average comparison."""
    tract_a = _make_mock_tract()
    avg_values = {
        "total_population": 5000.0,
        "median_household_income": 55000.0,
        "poverty_rate": 15.0,
        "uninsured_rate": 10.0,
        "unemployment_rate": 5.0,
        "median_age": 36.0,
        "sdoh_index": 0.5,
    }
    mock_session = _mock_session_tract_then_avg(tract_a, avg_values)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "compare_to": "state",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["a"]["type"] == "tract"
    assert body["b"]["type"] == "state_average"
    assert "State 27" in body["b"]["label"]
    # poverty_rate diff: 18.5 - 15.0 = 3.5
    assert body["differences"]["poverty_rate"] == pytest.approx(3.5, abs=0.01)


@pytest.mark.asyncio
async def test_compare_tract_vs_national(client):
    """Tract vs national average comparison."""
    tract_a = _make_mock_tract()
    avg_values = {
        "total_population": 4800.0,
        "median_household_income": 58000.0,
        "poverty_rate": 13.0,
        "uninsured_rate": 9.0,
        "unemployment_rate": 4.0,
        "median_age": 37.0,
        "sdoh_index": 0.48,
    }
    mock_session = _mock_session_tract_then_avg(tract_a, avg_values)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "compare_to": "national",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["b"]["type"] == "national_average"
    assert body["b"]["label"] == "National average"


@pytest.mark.asyncio
async def test_compare_null_fields_handled(client):
    """Null numeric fields produce null differences, not errors."""
    tract_a = _make_mock_tract()
    tract_a.sdoh_index = None
    tract_b = _make_mock_tract_b()
    tract_b.median_age = None
    mock_session = _mock_session_for_tracts(tract_a, tract_b)

    from geohealth.api.dependencies import get_db
    from geohealth.api.main import app

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        resp = await client.get("/v1/compare", params={
            "geoid1": "27053001100",
            "geoid2": "27053002200",
        })
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["differences"]["sdoh_index"] is None
    assert body["differences"]["median_age"] is None
    # Fields where both have values should still compute
    assert body["differences"]["poverty_rate"] is not None


@pytest.mark.asyncio
async def test_compare_rate_limit(client):
    """Exceeding rate limit → 429."""
    rate_limiter._max_requests = 1
    try:
        mock_session = _mock_session_for_tracts(_make_mock_tract(), _make_mock_tract_b())

        from geohealth.api.dependencies import get_db
        from geohealth.api.main import app

        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            # First request consumes the limit
            await client.get("/v1/compare", params={
                "geoid1": "27053001100",
                "geoid2": "27053002200",
            })
            # Reset mock for second call
            mock_session2 = _mock_session_for_tracts(_make_mock_tract(), _make_mock_tract_b())
            app.dependency_overrides[get_db] = lambda: mock_session2
            # Second should be rate-limited
            resp = await client.get("/v1/compare", params={
                "geoid1": "27053001100",
                "geoid2": "27053002200",
            })
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 429
    finally:
        rate_limiter._max_requests = 60
