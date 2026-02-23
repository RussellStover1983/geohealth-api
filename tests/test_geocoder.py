from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from geohealth.services.geocoder import GeocodedLocation, geocode


CENSUS_RESPONSE = {
    "result": {
        "addressMatches": [
            {
                "coordinates": {"x": -93.2650, "y": 44.9778},
                "matchedAddress": "1234 MAIN ST, MINNEAPOLIS, MN, 55401",
                "geographies": {
                    "Census Tracts": [
                        {"STATE": "27", "COUNTY": "053", "TRACT": "001100"}
                    ]
                },
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_geocode_census_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = CENSUS_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("geohealth.services.geocoder.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get.return_value = mock_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        loc = await geocode("1234 Main St, Minneapolis, MN 55401")

    assert isinstance(loc, GeocodedLocation)
    assert loc.lat == pytest.approx(44.9778)
    assert loc.lng == pytest.approx(-93.2650)
    assert loc.state_fips == "27"
    assert loc.county_fips == "053"
    assert loc.tract_fips == "001100"


@pytest.mark.asyncio
async def test_geocode_falls_back_to_nominatim():
    """When Census geocoder raises, Nominatim is tried."""
    nominatim_response = MagicMock()
    nominatim_response.json.return_value = [
        {"lat": "44.9778", "lon": "-93.2650", "display_name": "Minneapolis, MN"}
    ]
    nominatim_response.raise_for_status = MagicMock()

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Census down")
        return nominatim_response

    with patch("geohealth.services.geocoder.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = mock_get
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        loc = await geocode("1234 Main St, Minneapolis, MN")

    assert loc.lat == pytest.approx(44.9778)
    assert loc.state_fips is None  # Nominatim doesn't return FIPS
