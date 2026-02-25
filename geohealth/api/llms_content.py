"""Content for /llms.txt and /llms-full.txt (llmstxt.org standard)."""

from __future__ import annotations

LLMS_TXT = """\
# GeoHealth Context API

> Census-tract-level geographic health intelligence API for the United States.
> Given a street address or lat/lng coordinates, returns demographics,
> CDC Social Vulnerability Index (SVI) themes, CDC PLACES health outcome
> measures, and an optional AI-generated clinical narrative for the
> surrounding census tract.

## Quick Start

- Base URL: `https://geohealth-api-production.up.railway.app`
- Auth: `X-API-Key` header required on `/v1/*` endpoints
- Rate limit: 60 requests/minute per key
- OpenAPI spec: [/openapi.json](/openapi.json)

## Endpoints

- [GET /v1/context](/docs#/context): Primary lookup — address or lat/lng to tract demographics, SVI, PLACES, and optional AI narrative
- [POST /v1/batch](/docs#/batch): Multi-address lookup (up to 50 concurrent)
- [GET /v1/nearby](/docs#/nearby): Find census tracts within N miles of a point
- [GET /v1/compare](/docs#/compare): Compare two tracts or tract vs state/national averages
- [GET /v1/dictionary](/docs#/dictionary): Field definitions with clinical interpretation guidance
- [GET /v1/stats](/docs#/stats): Data coverage by state

## Key Data Fields

- **Demographics (ACS)**: total_population, median_household_income, poverty_rate, uninsured_rate, unemployment_rate, median_age
- **Vulnerability (SVI)**: rpl_theme1 (socioeconomic), rpl_theme2 (household/disability), rpl_theme3 (minority/language), rpl_theme4 (housing/transportation), rpl_themes (overall) — all as 0-1 percentiles
- **Health Outcomes (PLACES)**: diabetes, obesity, mhlth (mental health), phlth (physical health), bphigh (high blood pressure), csmoking (smoking), casthma (asthma), chd (coronary heart disease), lpa (physical inactivity), binge (binge drinking), sleep (short sleep), checkup, dental, access2 (no insurance) — all as crude prevalence %
- **Composite**: sdoh_index (0-1 scale, higher = more vulnerable)

## MCP Server (for AI Agents)

```bash
pip install geohealth-api[mcp]
GEOHEALTH_API_KEY=your-key python -m geohealth.mcp
```

## Python SDK

```python
from geohealth.sdk import AsyncGeoHealthClient

async with AsyncGeoHealthClient(base_url, api_key="your-key") as client:
    result = await client.context(address="1234 Main St, Minneapolis, MN 55401")
    print(result.tract.poverty_rate, result.tract.sdoh_index)
```

## More

- [Full documentation with clinical context](/llms-full.txt)
- [Interactive API docs (Swagger)](/docs)
- [OpenAPI JSON schema](/openapi.json)
"""

LLMS_FULL_TXT = """\
# GeoHealth Context API — Full Reference

> Census-tract-level geographic health intelligence API for the United States.
> Given a street address or lat/lng coordinates, returns demographics,
> CDC Social Vulnerability Index (SVI) themes, CDC PLACES health outcome
> measures, and an optional AI-generated clinical narrative for the
> surrounding census tract.

## When to Use This API

Use GeoHealth when building clinical tools that need to understand a patient's
neighborhood context. Social determinants of health (SDOH) — poverty, insurance
status, environmental factors — explain up to 80% of health outcomes. This API
provides that context at the census tract level (~4,000 people per tract).

Common use cases:
- Clinical risk models that incorporate neighborhood-level SDOH factors
- Patient intake workflows that flag social vulnerability
- Population health dashboards showing geographic health disparities
- Research cohort enrichment with standardized SDOH measures

## Authentication

All `/v1/*` endpoints require an API key via the `X-API-Key` header.
Keys are validated using SHA-256 hashing — plaintext keys are never stored.

```bash
curl -H "X-API-Key: your-key" "https://geohealth-api-production.up.railway.app/v1/context?address=..."
```

## Rate Limiting

60 requests per minute per API key (sliding window). Every response includes:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests left in current window
- `X-RateLimit-Reset`: Seconds until window resets

## Endpoints

### GET /v1/context — Primary Lookup

Look up health context for an address or coordinates.

```bash
# By address
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"

# By coordinates with AI narrative
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/context?lat=44.9778&lng=-93.265&narrative=true"
```

Parameters:
- `address` (string): US street address (mutually exclusive with lat/lng)
- `lat` (float): Latitude, -90 to 90
- `lng` (float): Longitude, -180 to 180
- `narrative` (bool): Include AI-generated clinical summary (default: false)

Returns: `{ location: {lat, lng, matched_address}, tract: {<all fields>}, narrative: string|null }`

### POST /v1/batch — Multi-Address Lookup

```bash
curl -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \\
  -d '{"addresses":["1234 Main St, Minneapolis, MN","456 Oak Ave, St Paul, MN"]}' \\
  "https://geohealth-api-production.up.railway.app/v1/batch"
```

Up to 50 addresses per request. Counts as a single rate-limit hit.

### GET /v1/nearby — Spatial Radius Search

```bash
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/nearby?lat=44.9778&lng=-93.265&radius=5&limit=10"
```

Parameters: `lat`, `lng`, `radius` (miles, default 5), `limit` (default 25), `offset`

### GET /v1/compare — Tract Comparison

```bash
# Two tracts
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/compare?geoid1=27053026200&geoid2=27053026300"

# Tract vs state average
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/compare?geoid1=27053026200&compare_to=state"
```

### GET /v1/dictionary — Data Dictionary

Returns structured metadata about every field with clinical interpretation.

```bash
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/dictionary"

# Filter by category
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/dictionary?category=health_outcomes"
```

Categories: demographics, vulnerability, health_outcomes, composite

### GET /v1/stats — Data Coverage

```bash
curl -H "X-API-Key: KEY" \\
  "https://geohealth-api-production.up.railway.app/v1/stats"
```

## Complete Data Field Reference

### Demographics (Source: American Community Survey)

| Field | Type | Unit | Clinical Threshold | Interpretation |
|-------|------|------|--------------------|----------------|
| total_population | int | persons | <1,000 = unreliable rates | Denominator for all rate metrics |
| median_household_income | float | dollars | <$30,000 = high risk | Predicts healthcare access and outcomes |
| poverty_rate | float | % | >20% = high-poverty | Strongest single predictor of poor health |
| uninsured_rate | float | % | >15% = access barriers | Directly impacts preventive care utilization |
| unemployment_rate | float | % | >10% = economic distress | Associated with depression and substance use |
| median_age | float | years | >45 = chronic disease risk | Indicates age-related service needs |

### Vulnerability (Source: CDC/ATSDR Social Vulnerability Index)

All SVI values are **national percentiles (0-1)**. Higher = more vulnerable.

| Field | Interpretation |
|-------|---------------|
| svi_themes.rpl_theme1 | Socioeconomic status: poverty + unemployment + no insurance + no diploma + housing cost burden |
| svi_themes.rpl_theme2 | Household composition & disability: aged 65+ / under 17 / disabled / single-parent households |
| svi_themes.rpl_theme3 | Minority status & language: racial/ethnic minorities + limited English proficiency |
| svi_themes.rpl_theme4 | Housing type & transportation: multi-unit / mobile homes / crowding / no vehicle / group quarters |
| svi_themes.rpl_themes | Overall composite across all 4 themes |

**Clinical rule of thumb**: SVI percentile above **0.75** = top 25% most vulnerable nationally.
These communities need intensive social needs screening and care coordination.

### Health Outcomes (Source: CDC PLACES)

All values are **crude prevalence percentages** among adults 18+, derived from
Behavioral Risk Factor Surveillance System (BRFSS) model-based estimates.

| Field | What It Measures | High-Burden Threshold |
|-------|-----------------|----------------------|
| places_measures.diabetes | Diagnosed diabetes | >12% |
| places_measures.obesity | BMI >= 30 | >35% |
| places_measures.mhlth | 14+ days mental distress/month | >16% |
| places_measures.phlth | 14+ days physical distress/month | >15% |
| places_measures.bphigh | Hypertension (high blood pressure) | >35% |
| places_measures.casthma | Current asthma | >10% |
| places_measures.chd | Coronary heart disease | >7% |
| places_measures.csmoking | Current smoking | >20% |
| places_measures.access2 | No health insurance (18-64) | >15% |
| places_measures.checkup | Annual checkup | <65% (low is bad) |
| places_measures.dental | Annual dental visit | <55% (low is bad) |
| places_measures.sleep | Short sleep (<7 hours) | >38% |
| places_measures.lpa | No leisure-time physical activity | >30% |
| places_measures.binge | Binge drinking | >20% |

### Composite Index

| Field | Scale | Interpretation |
|-------|-------|---------------|
| sdoh_index | 0-1 | Computed from poverty, uninsured, unemployment rates + SVI overall. Above 0.6 = high vulnerability. Best single triage metric for clinical risk assessment. |

## Python SDK

```python
from geohealth.sdk import AsyncGeoHealthClient

async with AsyncGeoHealthClient(
    "https://geohealth-api-production.up.railway.app",
    api_key="your-key",
) as client:
    # Primary lookup
    result = await client.context(address="1234 Main St, Minneapolis, MN 55401")
    print(result.tract.poverty_rate, result.tract.sdoh_index)
    print(result.tract.places_measures)  # dict of health outcomes

    # With AI narrative
    result = await client.context(lat=44.9778, lng=-93.265, narrative=True)
    print(result.narrative)

    # Nearby tracts
    nearby = await client.nearby(lat=44.9778, lng=-93.265, radius=3.0)
    for tract in nearby.tracts:
        print(tract.geoid, tract.distance_miles, tract.sdoh_index)

    # Data dictionary
    dictionary = await client.dictionary()
    for cat in dictionary.categories:
        for field in cat.fields:
            print(f"{field.name}: {field.clinical_relevance}")
```

## MCP Server (for AI Agents)

The GeoHealth MCP server exposes all API endpoints as native tools for
Claude Desktop, Claude Code, and other MCP-compatible agents.

### Install and run

```bash
pip install geohealth-api[mcp]
GEOHEALTH_API_KEY=your-key python -m geohealth.mcp
```

### Claude Desktop configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "geohealth": {
      "command": "python",
      "args": ["-m", "geohealth.mcp"],
      "env": {
        "GEOHEALTH_BASE_URL": "https://geohealth-api-production.up.railway.app",
        "GEOHEALTH_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| lookup_health_context | Primary lookup — address/coords to tract data |
| batch_health_lookup | Multi-address lookup |
| find_nearby_tracts | Spatial radius search |
| compare_tracts | Compare tracts or tract vs averages |
| get_data_dictionary | Field definitions with clinical context |
| get_tract_statistics | Data coverage by state |

## Error Handling

All errors return structured JSON: `{"error": true, "status_code": N, "detail": "..."}`

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid parameters |
| 401 | Missing API key |
| 403 | Invalid API key |
| 404 | Tract not found |
| 422 | Validation error (details in response) |
| 429 | Rate limit exceeded (check X-RateLimit-Reset header) |

## Additional Resources

- [OpenAPI JSON schema](/openapi.json) — machine-readable API specification
- [Interactive Swagger docs](/docs) — try endpoints in the browser
- [ReDoc reference](/redoc) — clean API reference documentation
- [GitHub repository](https://github.com/RussellStover1983/geohealth-api) — source code and issue tracker
"""
