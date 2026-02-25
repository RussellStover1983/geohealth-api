# Quick Start

Get from zero to your first API call in 5 minutes.

## Base URL

```
https://geohealth-api-production.up.railway.app
```

## Authentication

All `/v1/*` endpoints require an API key via the `X-API-Key` header. Keys are validated using SHA-256 hashing — plaintext keys are never stored or logged.

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/context?address=..."
```

!!! note "Getting an API key"
    Contact the project maintainer to receive an API key. For local development, set `AUTH_ENABLED=false` to disable authentication.

## Your First Call

### By address

=== "curl"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"
    ```

=== "Python SDK"

    ```python
    from geohealth.sdk import GeoHealthClient

    with GeoHealthClient(
        "https://geohealth-api-production.up.railway.app",
        api_key="your-key",
    ) as client:
        result = client.context(address="1234 Main St, Minneapolis, MN 55401")
        print(result.tract.geoid, result.tract.poverty_rate)
    ```

### By coordinates (with AI narrative)

=== "curl"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/context?lat=44.9778&lng=-93.265&narrative=true"
    ```

=== "Python SDK"

    ```python
    from geohealth.sdk import AsyncGeoHealthClient

    async with AsyncGeoHealthClient(
        "https://geohealth-api-production.up.railway.app",
        api_key="your-key",
    ) as client:
        result = await client.context(lat=44.9778, lng=-93.265, narrative=True)
        print(result.narrative)
    ```

## Understanding the Response

```json
{
  "location": {
    "lat": 44.9778,
    "lng": -93.265,
    "matched_address": "1234 Main St, Minneapolis, MN 55401"
  },
  "tract": {
    "geoid": "27053026200",
    "state_fips": "27",
    "county_fips": "053",
    "tract_code": "026200",
    "total_population": 4521,
    "median_household_income": 72500.0,
    "poverty_rate": 11.3,
    "uninsured_rate": 5.8,
    "unemployment_rate": 4.2,
    "median_age": 34.7,
    "svi_themes": {
      "rpl_theme1": 0.35,
      "rpl_theme2": 0.42,
      "rpl_theme3": 0.61,
      "rpl_theme4": 0.28,
      "rpl_themes": 0.44
    },
    "places_measures": {
      "diabetes": 9.1,
      "obesity": 28.4,
      "mhlth": 14.7,
      "bphigh": 29.8,
      "csmoking": 15.1,
      "...": "14 measures total"
    },
    "sdoh_index": 0.41
  },
  "narrative": null
}
```

### Key fields to look at first

| Field | What it tells you | Watch for |
|-------|------------------|-----------|
| `poverty_rate` | % below federal poverty level | >20% = high-poverty area |
| `sdoh_index` | Composite vulnerability (0–1) | >0.6 = high vulnerability |
| `svi_themes.rpl_themes` | Overall SVI percentile (0–1) | >0.75 = top 25% most vulnerable |
| `uninsured_rate` | % without health insurance | >15% = significant access barriers |
| `places_measures.diabetes` | Diabetes prevalence % | >12% = high-burden area |

!!! tip "The `sdoh_index` is the best single triage metric"
    If you only look at one number, make it `sdoh_index`. It combines poverty, insurance, unemployment, and SVI into a single 0–1 score. Values above 0.6 warrant social needs screening.

## Rate Limiting

Every authenticated response includes rate-limit headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests per window (default: 60) |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Seconds until the window resets |

When the limit is exceeded, the API returns `429 Too Many Requests`.

## Error Handling

All errors return structured JSON:

```json
{"error": true, "status_code": 401, "detail": "Missing API key"}
```

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid parameters |
| 401 | Missing API key |
| 403 | Invalid API key |
| 404 | Census tract not found for the given location |
| 422 | Validation error (details in response body) |
| 429 | Rate limit exceeded (check `X-RateLimit-Reset` header) |

## Next Steps

- [**API Reference**](api-reference.md) — All 6 endpoints with full parameter docs
- [**Data Dictionary**](data-dictionary.md) — What every field means clinically
- [**Python SDK & MCP**](sdk.md) — Typed client library and AI agent integration
