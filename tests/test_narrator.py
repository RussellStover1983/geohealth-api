from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from geohealth.services.narrator import _build_user_message, generate_narrative

FULL_TRACT = {
    "geoid": "27053001100",
    "state_fips": "27",
    "county_fips": "053",
    "tract_code": "001100",
    "name": "Census Tract 11, Hennepin County",
    "total_population": 4500,
    "median_household_income": 52000,
    "poverty_rate": 18.5,
    "uninsured_rate": 12.3,
    "unemployment_rate": 7.1,
    "median_age": 34.2,
    "svi_themes": {
        "socioeconomic_status": 0.78,
        "household_disability": 0.55,
        "minority_language": 0.62,
        "housing_transportation": 0.71,
    },
    "places_measures": {
        "diabetes": 12.1,
        "obesity": 35.4,
        "mental_health": 18.7,
    },
    "sdoh_index": 0.72,
}

MINIMAL_TRACT = {
    "geoid": "27053001100",
    "state_fips": "27",
    "county_fips": "053",
    "tract_code": "001100",
}

PARTIAL_TRACT = {
    "geoid": "27053001100",
    "name": "Census Tract 11",
    "total_population": 4500,
    "poverty_rate": 18.5,
    "sdoh_index": 0.72,
}


# ---------------------------------------------------------------------------
# _build_user_message tests
# ---------------------------------------------------------------------------

class TestBuildUserMessage:
    def test_full_data(self):
        msg = _build_user_message(FULL_TRACT)
        assert "Census Tract: 27053001100" in msg
        assert "Total Population: 4500" in msg
        assert "Poverty Rate: 18.5" in msg
        assert "SDOH Composite Index: 0.72" in msg
        assert "socioeconomic_status: 0.78" in msg
        assert "diabetes: 12.1" in msg

    def test_minimal_data(self):
        msg = _build_user_message(MINIMAL_TRACT)
        assert "Census Tract: 27053001100" in msg
        # No demographics section when all values are None/missing
        assert "Demographics:" not in msg
        assert "SDOH Composite Index" not in msg

    def test_partial_data(self):
        msg = _build_user_message(PARTIAL_TRACT)
        assert "Census Tract: 27053001100" in msg
        assert "Total Population: 4500" in msg
        assert "Poverty Rate: 18.5" in msg
        assert "SDOH Composite Index: 0.72" in msg
        # Fields not present should not appear
        assert "Uninsured Rate" not in msg
        assert "CDC SVI" not in msg

    def test_empty_dict(self):
        msg = _build_user_message({})
        assert msg == ""


# ---------------------------------------------------------------------------
# generate_narrative tests
# ---------------------------------------------------------------------------

class TestGenerateNarrative:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_text = "This tract shows elevated socioeconomic vulnerability."
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=mock_text)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with (
            patch("geohealth.services.narrator.settings") as mock_settings,
            patch("geohealth.services.narrator.anthropic") as mock_anthropic,
        ):
            mock_settings.anthropic_api_key = "sk-test-key"
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            mock_settings.narrative_max_tokens = 1024
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic.RateLimitError = anthropic.RateLimitError
            mock_anthropic.APIError = anthropic.APIError

            result = await generate_narrative(FULL_TRACT)

        assert result == mock_text
        mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch("geohealth.services.narrator.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""

            result = await generate_narrative(FULL_TRACT)

        assert result is None

    @pytest.mark.asyncio
    async def test_api_error(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.APIStatusError(
                message="Server error",
                response=MagicMock(status_code=500),
                body=None,
            )
        )

        with (
            patch("geohealth.services.narrator.settings") as mock_settings,
            patch("geohealth.services.narrator.anthropic") as mock_anthropic,
        ):
            mock_settings.anthropic_api_key = "sk-test-key"
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            mock_settings.narrative_max_tokens = 1024
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic.RateLimitError = anthropic.RateLimitError
            mock_anthropic.APIError = anthropic.APIError

            result = await generate_narrative(FULL_TRACT)

        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limit(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None,
            )
        )

        with (
            patch("geohealth.services.narrator.settings") as mock_settings,
            patch("geohealth.services.narrator.anthropic") as mock_anthropic,
        ):
            mock_settings.anthropic_api_key = "sk-test-key"
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            mock_settings.narrative_max_tokens = 1024
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            mock_anthropic.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic.RateLimitError = anthropic.RateLimitError
            mock_anthropic.APIError = anthropic.APIError

            result = await generate_narrative(FULL_TRACT)

        assert result is None
