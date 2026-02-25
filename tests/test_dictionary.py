"""Tests for GET /v1/dictionary endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_dictionary_returns_all_categories(client):
    """Default request returns all categories with field definitions."""
    resp = await client.get("/v1/dictionary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_fields"] > 0
    categories = body["categories"]
    assert len(categories) >= 4
    cat_names = {c["category"] for c in categories}
    assert {"demographics", "vulnerability", "health_outcomes", "composite"} == cat_names


@pytest.mark.asyncio
async def test_dictionary_field_structure(client):
    """Every field has the required metadata keys."""
    resp = await client.get("/v1/dictionary")
    assert resp.status_code == 200
    for cat in resp.json()["categories"]:
        assert "category" in cat
        assert "description" in cat
        assert "source" in cat
        for field in cat["fields"]:
            assert "name" in field
            assert "type" in field
            assert "source" in field
            assert "category" in field
            assert "description" in field
            assert "clinical_relevance" in field
            assert len(field["clinical_relevance"]) > 20


@pytest.mark.asyncio
async def test_dictionary_filter_demographics(client):
    """?category=demographics returns only demographic fields."""
    resp = await client.get("/v1/dictionary", params={"category": "demographics"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["categories"]) == 1
    assert body["categories"][0]["category"] == "demographics"
    assert body["total_fields"] == len(body["categories"][0]["fields"])


@pytest.mark.asyncio
async def test_dictionary_filter_health_outcomes(client):
    """?category=health_outcomes returns only PLACES fields."""
    resp = await client.get("/v1/dictionary", params={"category": "health_outcomes"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["categories"]) == 1
    assert body["categories"][0]["category"] == "health_outcomes"
    for field in body["categories"][0]["fields"]:
        assert field["source"] == "PLACES"


@pytest.mark.asyncio
async def test_dictionary_filter_unknown_category(client):
    """Unknown category returns empty list with zero fields."""
    resp = await client.get("/v1/dictionary", params={"category": "nonexistent"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_fields"] == 0
    assert body["categories"] == []


@pytest.mark.asyncio
async def test_dictionary_total_fields_count(client):
    """total_fields equals sum of all category field counts."""
    resp = await client.get("/v1/dictionary")
    body = resp.json()
    expected = sum(len(c["fields"]) for c in body["categories"])
    assert body["total_fields"] == expected


@pytest.mark.asyncio
async def test_dictionary_auth_required_when_enabled(client):
    """Returns 401 when auth is enabled and no key is provided."""
    with (
        patch("geohealth.config.settings.auth_enabled", True),
        patch("geohealth.config.settings.api_keys", "valid-key"),
    ):
        resp = await client.get("/v1/dictionary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dictionary_composite_has_sdoh_index(client):
    """Composite category contains the sdoh_index field."""
    resp = await client.get("/v1/dictionary", params={"category": "composite"})
    body = resp.json()
    fields = body["categories"][0]["fields"]
    names = [f["name"] for f in fields]
    assert "sdoh_index" in names
