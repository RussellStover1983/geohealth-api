# API Reference

Base URL: `https://geohealth-api-production.up.railway.app`

All `/v1/*` endpoints require an `X-API-Key` header. System endpoints (`/health`, `/metrics`) are public.

---

## GET /v1/context — Primary Lookup

Look up health context for an address or coordinates. This is the main endpoint.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `address` | string | One of address or lat/lng | US street address |
| `lat` | float | One of address or lat/lng | Latitude (-90 to 90) |
| `lng` | float | One of address or lat/lng | Longitude (-180 to 180) |
| `narrative` | bool | No | Include AI-generated clinical summary (default: `false`) |

### Examples

=== "curl (address)"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/context?address=1234+Main+St,+Minneapolis,+MN+55401"
    ```

=== "curl (coordinates + narrative)"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/context?lat=44.9778&lng=-93.265&narrative=true"
    ```

### Response

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
    "svi_themes": { "rpl_theme1": 0.35, "rpl_theme2": 0.42, "rpl_theme3": 0.61, "rpl_theme4": 0.28, "rpl_themes": 0.44 },
    "places_measures": { "diabetes": 9.1, "obesity": 28.4, "mhlth": 14.7, "...": "..." },
    "sdoh_index": 0.41
  },
  "narrative": "This census tract in Hennepin County..."
}
```

---

## POST /v1/batch — Multi-Address Lookup

Look up multiple addresses in a single request. Up to 50 addresses per request. Counts as a single rate-limit hit.

### Request Body

```json
{
  "addresses": [
    "1234 Main St, Minneapolis, MN",
    "456 Oak Ave, St Paul, MN"
  ]
}
```

### Example

```bash
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"addresses":["1234 Main St, Minneapolis, MN","456 Oak Ave, St Paul, MN"]}' \
  "https://geohealth-api-production.up.railway.app/v1/batch"
```

### Response

```json
{
  "results": [
    {
      "address": "1234 Main St, Minneapolis, MN",
      "location": { "lat": 44.9778, "lng": -93.265, "matched_address": "..." },
      "tract": { "geoid": "27053026200", "...": "..." },
      "error": null
    },
    {
      "address": "456 Oak Ave, St Paul, MN",
      "location": { "lat": 44.9537, "lng": -93.09, "matched_address": "..." },
      "tract": { "geoid": "27123004500", "...": "..." },
      "error": null
    }
  ]
}
```

!!! note
    Individual addresses that fail geocoding will have `tract: null` and an `error` message, without failing the entire batch.

---

## GET /v1/nearby — Spatial Radius Search

Find census tracts within a given radius of a point.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lat` | float | Yes | — | Latitude |
| `lng` | float | Yes | — | Longitude |
| `radius` | float | No | 5 | Radius in miles |
| `limit` | int | No | 25 | Maximum tracts to return |
| `offset` | int | No | 0 | Pagination offset |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/nearby?lat=44.9778&lng=-93.265&radius=5&limit=10"
```

### Response

```json
{
  "center": { "lat": 44.9778, "lng": -93.265 },
  "radius_miles": 5.0,
  "total": 42,
  "tracts": [
    {
      "geoid": "27053026200",
      "distance_miles": 0.3,
      "total_population": 4521,
      "poverty_rate": 11.3,
      "sdoh_index": 0.41,
      "...": "..."
    }
  ]
}
```

---

## GET /v1/compare — Tract Comparison

Compare two tracts side-by-side, or compare a tract against state or national averages.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `geoid1` | string | Yes | 11-digit GEOID of the first tract |
| `geoid2` | string | Conditional | 11-digit GEOID of the second tract (required if no `compare_to`) |
| `compare_to` | string | Conditional | `"state"` or `"national"` (required if no `geoid2`) |

### Examples

=== "Two tracts"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/compare?geoid1=27053026200&geoid2=27053026300"
    ```

=== "Tract vs. state average"

    ```bash
    curl -H "X-API-Key: your-key" \
      "https://geohealth-api-production.up.railway.app/v1/compare?geoid1=27053026200&compare_to=state"
    ```

### Response

```json
{
  "tract1": { "geoid": "27053026200", "poverty_rate": 11.3, "...": "..." },
  "tract2": { "geoid": "27053026300", "poverty_rate": 18.7, "...": "..." },
  "differences": {
    "poverty_rate": 7.4,
    "sdoh_index": 0.15,
    "...": "..."
  }
}
```

---

## GET /v1/dictionary — Data Dictionary

Returns structured metadata about every field, grouped by category. Includes data type, source, clinical relevance, and interpretation guidance.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category: `demographics`, `vulnerability`, `health_outcomes`, or `composite` |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/dictionary?category=health_outcomes"
```

### Response

```json
{
  "total_fields": 14,
  "categories": [
    {
      "category": "health_outcomes",
      "description": "CDC PLACES health outcome measures...",
      "source": "CDC PLACES",
      "fields": [
        {
          "name": "places_measures.diabetes",
          "type": "float",
          "source": "PLACES",
          "category": "health_outcomes",
          "description": "Crude prevalence of diagnosed diabetes among adults aged 18+.",
          "clinical_relevance": "Prevalence above 12% indicates a high-burden area...",
          "unit": "%",
          "typical_range": "5-25",
          "example_value": 9.1
        }
      ]
    }
  ]
}
```

See the [Data Dictionary](data-dictionary.md) page for the full field reference with clinical thresholds.

---

## GET /v1/stats — Data Coverage

Returns per-state tract counts showing which states have data loaded.

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/stats"
```

### Response

```json
{
  "total_tracts": 1505,
  "states": [
    { "state_fips": "27", "state_name": "Minnesota", "tract_count": 1505 }
  ]
}
```

---

## System Endpoints

These endpoints do not require authentication.

### GET /health

Health check for the API and database.

```bash
curl https://geohealth-api-production.up.railway.app/health
```

```json
{
  "status": "ok",
  "database": "connected",
  "detail": null,
  "cache_size": 128,
  "cache_hit_rate": 0.85,
  "rate_limiter_active_keys": 3,
  "uptime_seconds": 86400
}
```

### GET /metrics

Application metrics including request counters, latency percentiles, cache stats, and geocoder stats.

```bash
curl https://geohealth-api-production.up.railway.app/metrics
```

### GET /llms.txt

Agent-readable API overview following the [llmstxt.org](https://llmstxt.org) standard. Useful for AI agents that need to understand what the API does.

### GET /llms-full.txt

Full agent-readable reference with clinical context, field definitions, SDK examples, and MCP setup.
