# API Reference

Base URL: `https://geohealth-api-production.up.railway.app`

All `/v1/*` endpoints require an `X-API-Key` header. System endpoints (`/health`, `/metrics`) are public.

> For error response formats and troubleshooting, see [Error Handling](errors.md).

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
    "name": "Census Tract 262, Hennepin County, MN",
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
      "phlth": 12.3,
      "bphigh": 29.8,
      "casthma": 9.5,
      "chd": 5.9,
      "csmoking": 15.1,
      "access2": 7.2,
      "checkup": 74.6,
      "dental": 65.3,
      "sleep": 35.2,
      "lpa": 22.3,
      "binge": 18.6
    },
    "epa_data": {
      "pm25": 8.2,
      "ozone": 42.1,
      "diesel_pm": 0.31,
      "air_toxics_cancer_risk": 28.0,
      "respiratory_hazard_index": 0.38,
      "traffic_proximity": 140.5,
      "lead_paint_pct": 0.42,
      "superfund_proximity": 0.22,
      "rmp_proximity": 0.65,
      "hazardous_waste_proximity": 1.1,
      "wastewater_discharge": 4.7,
      "_source": "ejscreen_api"
    },
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
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {
      "address": "1234 Main St, Minneapolis, MN",
      "status": "ok",
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
        "name": "Census Tract 262, Hennepin County, MN",
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
          "phlth": 12.3,
          "bphigh": 29.8,
          "casthma": 9.5,
          "chd": 5.9,
          "csmoking": 15.1,
          "access2": 7.2,
          "checkup": 74.6,
          "dental": 65.3,
          "sleep": 35.2,
          "lpa": 22.3,
          "binge": 18.6
        },
        "epa_data": {
          "pm25": 8.2,
          "ozone": 42.1,
          "diesel_pm": 0.31,
          "air_toxics_cancer_risk": 28.0,
          "respiratory_hazard_index": 0.38,
          "traffic_proximity": 140.5,
          "lead_paint_pct": 0.42,
          "superfund_proximity": 0.22,
          "rmp_proximity": 0.65,
          "hazardous_waste_proximity": 1.1,
          "wastewater_discharge": 4.7,
          "_source": "ejscreen_api"
        },
        "sdoh_index": 0.41
      },
      "error": null
    },
    {
      "address": "456 Oak Ave, St Paul, MN",
      "status": "ok",
      "location": {
        "lat": 44.9537,
        "lng": -93.09,
        "matched_address": "456 Oak Ave, St Paul, MN 55101"
      },
      "tract": {
        "geoid": "27123004500",
        "state_fips": "27",
        "county_fips": "123",
        "tract_code": "004500",
        "name": "Census Tract 45, Ramsey County, MN",
        "total_population": 3842,
        "median_household_income": 58200.0,
        "poverty_rate": 16.7,
        "uninsured_rate": 8.1,
        "unemployment_rate": 5.9,
        "median_age": 31.2,
        "svi_themes": {
          "rpl_theme1": 0.52,
          "rpl_theme2": 0.48,
          "rpl_theme3": 0.73,
          "rpl_theme4": 0.41,
          "rpl_themes": 0.58
        },
        "places_measures": {
          "diabetes": 10.8,
          "obesity": 31.2,
          "mhlth": 16.4,
          "phlth": 13.9,
          "bphigh": 32.1,
          "casthma": 10.7,
          "chd": 6.4,
          "csmoking": 17.3,
          "access2": 9.1,
          "checkup": 71.2,
          "dental": 59.8,
          "sleep": 38.1,
          "lpa": 25.6,
          "binge": 19.4
        },
        "epa_data": {
          "pm25": 8.5,
          "ozone": 43.0,
          "diesel_pm": 0.28,
          "air_toxics_cancer_risk": 26.5,
          "respiratory_hazard_index": 0.35,
          "traffic_proximity": 120.3,
          "lead_paint_pct": 0.51,
          "superfund_proximity": 0.18,
          "rmp_proximity": 0.72,
          "hazardous_waste_proximity": 0.9,
          "wastewater_discharge": 3.8,
          "_source": "ejscreen_api"
        },
        "sdoh_index": 0.53
      },
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
  "count": 2,
  "total": 42,
  "offset": 0,
  "limit": 10,
  "tracts": [
    {
      "geoid": "27053026200",
      "name": "Census Tract 262, Hennepin County, MN",
      "distance_miles": 0.3,
      "total_population": 4521,
      "median_household_income": 72500.0,
      "poverty_rate": 11.3,
      "uninsured_rate": 5.8,
      "unemployment_rate": 4.2,
      "median_age": 34.7,
      "sdoh_index": 0.41
    },
    {
      "geoid": "27053026300",
      "name": "Census Tract 263, Hennepin County, MN",
      "distance_miles": 1.2,
      "total_population": 3876,
      "median_household_income": 61200.0,
      "poverty_rate": 14.9,
      "uninsured_rate": 7.3,
      "unemployment_rate": 5.1,
      "median_age": 32.4,
      "sdoh_index": 0.49
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
| `compare_to` | string | Conditional | `"county"`, `"state"`, or `"national"` (required if no `geoid2`) |

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
  "a": {
    "type": "tract",
    "geoid": "27053026200",
    "label": "Census Tract 262, Hennepin County, MN",
    "values": {
      "total_population": 4521.0,
      "median_household_income": 72500.0,
      "poverty_rate": 11.3,
      "uninsured_rate": 5.8,
      "unemployment_rate": 4.2,
      "median_age": 34.7,
      "sdoh_index": 0.41
    }
  },
  "b": {
    "type": "tract",
    "geoid": "27053026300",
    "label": "Census Tract 263, Hennepin County, MN",
    "values": {
      "total_population": 3876.0,
      "median_household_income": 61200.0,
      "poverty_rate": 14.9,
      "uninsured_rate": 7.3,
      "unemployment_rate": 5.1,
      "median_age": 32.4,
      "sdoh_index": 0.49
    }
  },
  "differences": {
    "total_population": 645.0,
    "median_household_income": 11300.0,
    "poverty_rate": -3.6,
    "uninsured_rate": -1.5,
    "unemployment_rate": -0.9,
    "median_age": 2.3,
    "sdoh_index": -0.08
  }
}
```

---

## GET /v1/trends — Historical Trends

Returns year-by-year ACS demographic snapshots for a census tract, with computed absolute and percent changes between the earliest and latest available years.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `geoid` | string | Yes | 11-digit tract GEOID |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/trends?geoid=27053026200"
```

### Response

```json
{
  "geoid": "27053026200",
  "name": "Census Tract 262",
  "years": [
    {
      "year": 2018,
      "total_population": 4200,
      "median_household_income": 64800.0,
      "poverty_rate": 14.1,
      "uninsured_rate": 7.6,
      "unemployment_rate": 5.3,
      "median_age": 33.1
    },
    {
      "year": 2022,
      "total_population": 4521,
      "median_household_income": 72500.0,
      "poverty_rate": 11.3,
      "uninsured_rate": 5.8,
      "unemployment_rate": 4.2,
      "median_age": 34.7
    }
  ],
  "changes": [
    {
      "metric": "total_population",
      "earliest_year": 2018,
      "latest_year": 2022,
      "earliest_value": 4200.0,
      "latest_value": 4521.0,
      "absolute_change": 321.0,
      "percent_change": 7.64
    },
    {
      "metric": "poverty_rate",
      "earliest_year": 2018,
      "latest_year": 2022,
      "earliest_value": 14.1,
      "latest_value": 11.3,
      "absolute_change": -2.8,
      "percent_change": -19.86
    },
    {
      "metric": "median_household_income",
      "earliest_year": 2018,
      "latest_year": 2022,
      "earliest_value": 64800.0,
      "latest_value": 72500.0,
      "absolute_change": 7700.0,
      "percent_change": 11.88
    }
  ]
}
```

!!! note
    Trend data must be loaded via the ETL pipeline (`python -m geohealth.etl.load_trends`). If no historical data exists, the response contains only the current-year snapshot.

---

## GET /v1/demographics/compare — Demographic Rankings

Compare a tract's demographics against county, state, and national averages with percentile rankings.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `geoid` | string | Yes | 11-digit tract GEOID |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/demographics/compare?geoid=27053026200"
```

### Response

```json
{
  "geoid": "27053026200",
  "name": "Census Tract 262",
  "state_fips": "27",
  "county_fips": "053",
  "rankings": [
    {
      "metric": "poverty_rate",
      "value": 11.3,
      "county_percentile": 45.2,
      "state_percentile": 52.1,
      "national_percentile": 38.7
    },
    {
      "metric": "uninsured_rate",
      "value": 5.8,
      "county_percentile": 32.4,
      "state_percentile": 41.6,
      "national_percentile": 22.1
    },
    {
      "metric": "median_household_income",
      "value": 72500.0,
      "county_percentile": 58.3,
      "state_percentile": 65.9,
      "national_percentile": 61.4
    }
  ],
  "averages": [
    {
      "metric": "poverty_rate",
      "tract_value": 11.3,
      "county_avg": 12.8,
      "state_avg": 10.1,
      "national_avg": 13.4
    },
    {
      "metric": "uninsured_rate",
      "tract_value": 5.8,
      "county_avg": 6.9,
      "state_avg": 5.3,
      "national_avg": 9.2
    },
    {
      "metric": "median_household_income",
      "tract_value": 72500.0,
      "county_avg": 78400.0,
      "state_avg": 68900.0,
      "national_avg": 65000.0
    }
  ]
}
```

---

## Webhooks — Event Subscriptions

Subscribe to notifications when tract data is updated via the ETL pipeline.

### POST /v1/webhooks — Create Subscription

```bash
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/hook","events":["data.updated"],"secret":"my-secret"}' \
  "https://geohealth-api-production.up.railway.app/v1/webhooks"
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Callback URL (HTTPS recommended) |
| `events` | array | Yes | Event types: `"data.updated"`, `"threshold.exceeded"` |
| `secret` | string | No | HMAC-SHA256 signing secret for payload verification |
| `filters` | object | No | Optional filters (`state_fips`, `geoids`, `thresholds`) |

### GET /v1/webhooks — List Subscriptions

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/webhooks"
```

### DELETE /v1/webhooks/{id} — Remove Subscription

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/webhooks/1"
```

---

## Webhook Payload Format

Every webhook delivery is a POST request to your callback URL with the following structure.

### Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Webhook-Signature` | `sha256=<hex>` (only if `secret` was set on the subscription) |

### Body

```json
{
  "event": "data.updated",
  "timestamp": "2026-03-06T12:00:00+00:00",
  "data": {
    "state_fips": "27",
    "geoid": "27053026200",
    "updated_fields": ["places_measures", "epa_data"]
  }
}
```

## Verifying Webhook Signatures

If you set a `secret` when creating the subscription, every delivery includes an `X-Webhook-Signature` header. Verify it to ensure the payload was not tampered with.

The signature is computed as: `HMAC-SHA256(secret, raw_request_body)` and sent in the format `sha256=<hex_digest>`.

### Python verification example

```python
import hashlib
import hmac

from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
WEBHOOK_SECRET = "my-secret"

@app.post("/hook")
async def handle_webhook(request: Request):
    body = await request.body()
    signature_header = request.headers.get("X-Webhook-Signature", "")

    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=400, detail="Missing signature")

    received_sig = signature_header.removeprefix("sha256=")
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    import json
    payload = json.loads(body)
    print(f"Received event: {payload['event']}")
    return {"ok": True}
```

### Node.js verification example

```javascript
const crypto = require("crypto");
const express = require("express");
const app = express();

const WEBHOOK_SECRET = "my-secret";

app.post("/hook", express.raw({ type: "application/json" }), (req, res) => {
  const signatureHeader = req.headers["x-webhook-signature"] || "";
  if (!signatureHeader.startsWith("sha256=")) {
    return res.status(400).json({ error: "Missing signature" });
  }

  const receivedSig = signatureHeader.slice("sha256=".length);
  const expectedSig = crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(req.body)
    .digest("hex");

  if (!crypto.timingSafeEqual(Buffer.from(receivedSig), Buffer.from(expectedSig))) {
    return res.status(403).json({ error: "Invalid signature" });
  }

  const payload = JSON.parse(req.body);
  console.log(`Received event: ${payload.event}`);
  res.json({ ok: true });
});

app.listen(5000, () => console.log("Listening on :5000"));
```

### curl testing example

```bash
# Compute the signature manually
BODY='{"event":"data.updated","timestamp":"2026-03-06T12:00:00+00:00","data":{"state_fips":"27"}}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "my-secret" | awk '{print $2}')

# Send a test webhook delivery
curl -X POST http://localhost:5000/hook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=$SIG" \
  -d "$BODY"
```

## Webhook Retry Behavior

- Deliveries that receive a 5xx response or a network error are retried.
- Retry schedule: exponential backoff (1s, 2s, 4s) up to 3 attempts.
- 4xx responses are **not** retried (indicates a problem with your endpoint).
- Delivery timeout: 10 seconds.

## Testing Webhooks Locally

Use a tunnel service like [ngrok](https://ngrok.com) to expose your local server:

```bash
# 1. Start your local webhook handler
python -m uvicorn my_app:app --port 5000

# 2. Expose it via ngrok
ngrok http 5000

# 3. Create a subscription using the ngrok URL
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"url":"https://abc123.ngrok.io/hook","events":["data.updated"],"secret":"my-secret"}' \
  "https://geohealth-api-production.up.railway.app/v1/webhooks"

# 4. Trigger a data.updated event (e.g., run an ETL load)
#    and inspect the request in your local server logs
```

---

## GET /v1/dictionary — Data Dictionary

Returns structured metadata about every field, grouped by category. Includes data type, source, clinical relevance, and interpretation guidance.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category: `demographics`, `vulnerability`, `health_outcomes`, `environmental`, `composite`, or `identity` |

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
  "total_states": 51,
  "total_tracts": 84415,
  "offset": 0,
  "limit": 50,
  "states": [
    { "state_fips": "01", "tract_count": 1437 },
    { "state_fips": "02", "tract_count": 177 },
    { "state_fips": "04", "tract_count": 1765 },
    "... all 50 states + DC ..."
  ]
}
```

---

## GET /v1/providers/geojson — Provider Map Data

Returns NPI providers as a GeoJSON FeatureCollection with Point geometries for map rendering. Uses bounding box filtering with a PostGIS spatial index.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bbox` | string | Yes | Bounding box: `west,south,east,north` (comma-separated floats) |
| `provider_type` | string | No | Filter: `all`, `pcp`, `fqhc`, `urgent_care`, `rural_health_clinic` (default: `all`) |
| `limit` | int | No | Max providers to return (default: 500, max: 2000) |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/providers/geojson?bbox=-95.0,38.5,-94.0,39.5&provider_type=pcp"
```

### Response

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [-94.583, 39.111]},
      "properties": {
        "npi": "1234567890",
        "provider_name": "Jane Smith",
        "credential": "MD",
        "primary_taxonomy": "207Q00000X",
        "taxonomy_description": "Family Medicine",
        "provider_type": "pcp",
        "practice_address": "123 Main St",
        "practice_city": "Kansas City",
        "practice_state": "MO",
        "practice_zip": "64108",
        "phone": "8165551234",
        "is_fqhc": false,
        "entity_type": "1"
      }
    }
  ]
}
```

---

## GET /v1/providers — Provider Search

Search for NPI providers by radius around a point or by census tract FIPS code. Returns a paginated JSON list.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lat` | float | One of lat/lng or tract_fips | Center latitude |
| `lng` | float | One of lat/lng or tract_fips | Center longitude |
| `radius` | float | No | Radius in miles (default: 5, max: 50) |
| `tract_fips` | string | One of lat/lng or tract_fips | 11-digit census tract FIPS |
| `provider_type` | string | No | Filter: `all`, `pcp`, `fqhc`, `urgent_care`, etc. (default: `all`) |
| `limit` | int | No | Max results (default: 50, max: 500) |
| `offset` | int | No | Pagination offset (default: 0) |

### Example

```bash
curl -H "X-API-Key: your-key" \
  "https://geohealth-api-production.up.railway.app/v1/providers?lat=39.1&lng=-94.5&radius=5&provider_type=pcp"
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
  "cache": {
    "size": 128,
    "max_size": 1024,
    "hit_rate": 0.85
  },
  "rate_limiter": {
    "active_keys": 3
  },
  "uptime_seconds": 86400.0
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
