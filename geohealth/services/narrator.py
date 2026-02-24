from __future__ import annotations

import logging

import anthropic

from geohealth.config import settings
from geohealth.services.metrics import metrics

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a public-health analyst. Given census-tract-level social determinants "
    "of health (SDOH) data, produce a concise 3–5 sentence plain-text summary suitable "
    "for clinicians and community health workers.\n\n"
    "Interpret the SDOH composite index (0–1 scale, higher = more disadvantage), "
    "CDC SVI theme percentile rankings (0–1, higher = more vulnerable), and "
    "CDC PLACES health measures (prevalences as percentages).\n\n"
    "Do NOT provide medical advice or treatment recommendations. "
    "Focus on community-level context that may inform care decisions."
)


def _build_user_message(tract_data: dict) -> str:
    """Format tract data into a labeled prompt for the LLM."""
    sections: list[str] = []

    # Identity
    if tract_data.get("geoid"):
        sections.append(f"Census Tract: {tract_data['geoid']}")
    if tract_data.get("name"):
        sections.append(f"Name: {tract_data['name']}")

    # Demographics
    demo_lines: list[str] = []
    for key, label in [
        ("total_population", "Total Population"),
        ("median_household_income", "Median Household Income"),
        ("poverty_rate", "Poverty Rate"),
        ("uninsured_rate", "Uninsured Rate"),
        ("unemployment_rate", "Unemployment Rate"),
        ("median_age", "Median Age"),
    ]:
        if tract_data.get(key) is not None:
            demo_lines.append(f"  {label}: {tract_data[key]}")
    if demo_lines:
        sections.append("Demographics:\n" + "\n".join(demo_lines))

    # SDOH composite index
    if tract_data.get("sdoh_index") is not None:
        sections.append(f"SDOH Composite Index: {tract_data['sdoh_index']}")

    # SVI themes
    if tract_data.get("svi_themes"):
        svi_lines = [f"  {k}: {v}" for k, v in tract_data["svi_themes"].items()]
        sections.append("CDC SVI Theme Rankings:\n" + "\n".join(svi_lines))

    # PLACES measures
    if tract_data.get("places_measures"):
        places_lines = [f"  {k}: {v}" for k, v in tract_data["places_measures"].items()]
        sections.append("CDC PLACES Measures:\n" + "\n".join(places_lines))

    return "\n\n".join(sections)


async def generate_narrative(tract_data: dict) -> str | None:
    """Call Claude to generate a plain-language narrative for the tract data.

    Returns the narrative string, or None on any failure (missing key, API error, etc.).
    """
    if not settings.anthropic_api_key:
        logger.warning("Narrative requested but ANTHROPIC_API_KEY is not set")
        metrics.inc_narrative(False)
        return None

    user_message = _build_user_message(tract_data)
    if not user_message:
        metrics.inc_narrative(False)
        return None

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.narrative_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        metrics.inc_narrative(True)
        return response.content[0].text
    except anthropic.AuthenticationError:
        logger.error("Anthropic authentication failed — check ANTHROPIC_API_KEY")
        metrics.inc_narrative(False)
        return None
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit exceeded")
        metrics.inc_narrative(False)
        return None
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        metrics.inc_narrative(False)
        return None
    except Exception as exc:
        logger.exception("Unexpected error generating narrative: %s", exc)
        metrics.inc_narrative(False)
        return None
