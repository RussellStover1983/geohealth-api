# GeoHealth API — Project Summary for UI Planning

## What This Project Is

A **census-tract-level geographic health intelligence API**. You give it a street address or lat/lng coordinates, and it returns a rich profile of the surrounding census tract: demographics, social vulnerability, health outcomes, environmental data, historical trends, and optionally an AI-generated narrative summary.

**Target users**: Healthcare organizations, public health researchers, community health workers, and developers building health equity tools.

**Current state**: Backend API is fully built and deployed. There is **no frontend UI** — only the auto-generated Swagger/ReDoc API docs and a static MkDocs documentation site.

---

## Live URLs

| What | URL |
|------|-----|
| **API (production)** | `https://geohealth-api-production.up.railway.app` |
| **Swagger UI (auto-generated)** | `https://geohealth-api-production.up.railway.app/docs` |
| **ReDoc** | `https://geohealth-api-production.up.railway.app/redoc` |
| **OpenAPI JSON schema** | `https://geohealth-api-production.up.railway.app/openapi.json` |
| **Documentation site** | `https://russellstover1983.github.io/geohealth-api/` |
| **Health check** | `https://geohealth-api-production.up.railway.app/health` |
| **Metrics** | `https://geohealth-api-production.up.railway.app/metrics` |
| **GitHub repo** | `https://github.com/RussellStover1983/geohealth-api` |
| **PyPI package** | `https://pypi.org/project/geohealth-api/` |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend framework** | Python 3.11+ / FastAPI |
| **Database** | PostgreSQL 16 + PostGIS 3.4 (spatial queries) |
| **ORM** | SQLAlchemy 2.0 async (asyncpg driver) |
| **Validation** | Pydantic v2 |
| **Migrations** | Alembic |
| **HTTP client** | httpx (for geocoding, webhooks) |
| **AI narratives** | Anthropic Claude API |
| **Deployment** | Railway (Docker, Gunicorn + Uvicorn workers) |
| **Docs site** | MkDocs + Material theme → GitHub Pages |
| **CI/CD** | GitHub Actions (lint, test, Docker build, docs deploy) |
| **Package** | Published on PyPI as `geohealth-api` |

---

## Data Coverage

**4 US states loaded** (6,784 census tracts total):
- Georgia (FIPS 13)
- Kansas (FIPS 20)
- Minnesota (FIPS 27)
- Missouri (FIPS 29)

The ETL pipeline supports loading any/all US states. Each tract has:
- **TIGER/Line geometry** (polygon boundaries for spatial queries)
- **ACS demographics** (population, income, poverty, insurance, unemployment, age)
- **CDC SVI** (Social Vulnerability Index — 4 themes + overall percentile)
- **CDC PLACES** (14 health outcome measures — diabetes, obesity, mental health, etc.)
- **EPA EJScreen** (11 environmental indicators — air quality, toxics, lead paint, etc.)
- **Historical trends** (multi-year ACS snapshots, 2018–2022)
- **Composite SDOH index** (computed 0–1 vulnerability score)

---

## API Endpoints (Complete List)

### Public (no auth required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Database connectivity + cache/rate-limiter stats |
| GET | `/metrics` | Request counters, latency percentiles, cache hit rates |
| GET | `/llms.txt` | Agent-readable API overview (llmstxt.org standard) |
| GET | `/llms-full.txt` | Full agent reference with clinical context |

### Authenticated (requires `X-API-Key` header)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/context` | **Primary endpoint** — address or lat/lng → full tract profile + optional AI narrative |
| POST | `/v1/batch` | Multi-address lookup (up to 50 addresses) |
| GET | `/v1/nearby` | Spatial radius search — tracts within N miles of a point |
| GET | `/v1/compare` | Compare two tracts, or tract vs county/state/national averages |
| GET | `/v1/trends` | Historical trend data (multi-year ACS with change metrics) |
| GET | `/v1/demographics/compare` | Tract vs county/state/national with percentile rankings |
| GET | `/v1/stats` | Per-state tract counts |
| GET | `/v1/dictionary` | Data dictionary — field definitions with clinical context |
| POST | `/v1/webhooks` | Create webhook subscription |
| GET | `/v1/webhooks` | List webhook subscriptions |
| GET | `/v1/webhooks/{id}` | Get webhook subscription details |
| DELETE | `/v1/webhooks/{id}` | Delete webhook subscription |

### Key Query Parameters for `/v1/context`
- `address` — street address string (geocoded via Census Bureau → Nominatim fallback)
- `lat` + `lng` — direct coordinates (skip geocoding)
- `narrative=true` — include AI-generated summary from Claude
- `state_fips` — hint to narrow spatial search

### Key Query Parameters for `/v1/nearby`
- `lat` + `lng` — center point
- `radius` — miles (default 5)
- `limit` + `offset` — pagination

---

## Data Model (What the API Returns)

### Core Tract Profile (`/v1/context` response)
```json
{
  "location": {
    "lat": 38.627,
    "lng": -90.199,
    "matched_address": "100 N Broadway, St Louis, MO 63102"
  },
  "tract": {
    "geoid": "29510101100",
    "state_fips": "29",
    "county_fips": "510",
    "tract_code": "101100",
    "name": "Census Tract 1011, St. Louis city, MO",
    "total_population": 4521,
    "median_household_income": 72500.0,
    "poverty_rate": 11.3,
    "uninsured_rate": 5.8,
    "unemployment_rate": 4.2,
    "median_age": 34.7,
    "sdoh_index": 0.41,
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
      "bphigh": 29.5,
      "casthma": 9.8,
      "chd": 5.2,
      "csmoking": 15.1,
      "access2": 8.4,
      "checkup": 73.2,
      "dental": 60.1,
      "sleep": 35.2,
      "lpa": 22.3,
      "binge": 18.6
    },
    "epa_data": {
      "pm25": 8.2,
      "ozone": 42.1,
      "diesel_pm": 0.31,
      "air_toxics_cancer_risk": 28.0,
      "respiratory_hazard_index": 0.42,
      "traffic_proximity": 150.0,
      "lead_paint_pct": 0.42,
      "superfund_proximity": 0.15,
      "rmp_proximity": 0.58,
      "hazardous_waste_proximity": 1.2,
      "wastewater_discharge": 12.5,
      "_source": "ejscreen_api"
    }
  },
  "narrative": "This census tract in St. Louis shows moderate social vulnerability..."
}
```

### Trend Data (`/v1/trends` response)
```json
{
  "geoid": "27053026200",
  "name": "Census Tract 262, Hennepin County, MN",
  "years": [
    {"year": 2018, "poverty_rate": 15.2, "median_household_income": 58000, ...},
    {"year": 2019, "poverty_rate": 14.1, ...},
    {"year": 2020, "poverty_rate": 13.8, ...},
    {"year": 2021, "poverty_rate": 12.5, ...},
    {"year": 2022, "poverty_rate": 11.3, ...}
  ],
  "changes": [
    {"metric": "poverty_rate", "earliest_year": 2018, "latest_year": 2022,
     "earliest_value": 15.2, "latest_value": 11.3,
     "absolute_change": -3.9, "percent_change": -25.66}
  ]
}
```

### Demographic Comparison (`/v1/demographics/compare` response)
```json
{
  "geoid": "27053026200",
  "rankings": [
    {"metric": "poverty_rate", "value": 11.3,
     "county_percentile": 45.2, "state_percentile": 52.1, "national_percentile": 38.7},
    {"metric": "median_household_income", "value": 72500,
     "county_percentile": 62.3, "state_percentile": 71.4, "national_percentile": 68.9}
  ],
  "averages": [
    {"metric": "poverty_rate", "tract_value": 11.3,
     "county_avg": 13.8, "state_avg": 11.9, "national_avg": 12.6}
  ]
}
```

---

## Database Schema

### `tract_profiles` table
| Column | Type | Description |
|--------|------|-------------|
| `geoid` | String(11), PK | 11-digit FIPS (state+county+tract) |
| `state_fips` | String(2) | State FIPS code (indexed) |
| `county_fips` | String(3) | County FIPS code |
| `tract_code` | String(6) | Tract code |
| `name` | Text | Human-readable name |
| `geom` | PostGIS MultiPolygon | Tract boundary geometry (GIST indexed) |
| `total_population` | Integer | ACS population |
| `median_household_income` | Float | ACS income |
| `poverty_rate` | Float | ACS poverty % |
| `uninsured_rate` | Float | ACS uninsured % |
| `unemployment_rate` | Float | ACS unemployment % |
| `median_age` | Float | ACS median age |
| `svi_themes` | JSONB | CDC SVI percentiles (4 themes + overall) |
| `places_measures` | JSONB | CDC PLACES health measures (14 indicators) |
| `sdoh_index` | Float | Composite vulnerability score (0–1) |
| `trends` | JSONB | Year-keyed historical ACS snapshots |
| `epa_data` | JSONB | EPA EJScreen environmental indicators |

### `webhook_subscriptions` table
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer, PK | Auto-increment ID |
| `url` | Text | Callback URL |
| `api_key_hash` | String(64) | SHA-256 hash of owning API key |
| `events` | JSONB | Subscribed event types |
| `filters` | JSONB | Optional filters (state, geoid, thresholds) |
| `secret` | String(64) | HMAC signing secret |
| `active` | Boolean | Active flag |
| `created_at` | DateTime(tz) | Creation timestamp |
| `updated_at` | DateTime(tz) | Last update timestamp |

---

## Authentication & Rate Limiting

- **Auth**: API key via `X-API-Key` header. Keys are SHA-256 hashed before comparison. Anonymous access allowed when `AUTH_ENABLED=false`.
- **Rate limiting**: Sliding window, 60 requests per 60 seconds per key. Returns `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers.
- **CORS**: Currently `*` (open). Should be restricted for production frontend.

---

## Existing Frontend Assets

There is **no custom frontend UI**. What exists today:

1. **Swagger UI** (`/docs`) — auto-generated by FastAPI, interactive API explorer
2. **ReDoc** (`/redoc`) — auto-generated clean reference docs
3. **MkDocs documentation site** — 5 static pages (Home, Quick Start, API Reference, Data Dictionary, SDK)
4. **CORS is enabled** — the API is ready to accept cross-origin requests from a frontend

---

## Architecture Highlights Relevant to UI

- **CORS already configured** — frontend can call the API directly
- **Pydantic response models** — every endpoint has a typed, documented JSON schema
- **OpenAPI 3.1 spec** — can auto-generate TypeScript types from `/openapi.json`
- **Geocoding built in** — frontend just sends an address string, API handles geocoding
- **AI narratives** — set `narrative=true` to get a plain-English summary from Claude
- **Spatial queries** — nearby search, radius queries already built
- **Batch support** — submit up to 50 addresses at once
- **Comparison endpoints** — tract vs tract, tract vs averages, with percentile rankings
- **Trend data** — historical time series ready for charting
- **Data dictionary** — structured field metadata available at `/v1/dictionary`
- **Webhooks** — real-time notifications when data updates or thresholds are exceeded

---

## What a Frontend Could Visualize

Based on the data available from the API:

1. **Map view** — search by address, show tract boundaries on a map, color-code by any metric
2. **Tract profile dashboard** — demographics, SVI gauges, health outcome bars, EPA indicators
3. **Comparison view** — side-by-side tract comparison or tract vs county/state/national
4. **Trend charts** — line charts showing 2018–2022 demographic trends
5. **Nearby explorer** — radius search showing surrounding tracts ranked by distance
6. **Demographic rankings** — percentile bars showing where a tract falls relative to county/state/nation
7. **Batch analysis** — upload a list of addresses, get back a table/map of results
8. **AI narrative panel** — display the Claude-generated plain-English summary
9. **Environmental overlay** — EPA data (air quality, toxics, lead paint) on the map
10. **Data dictionary/help** — in-app reference for what each metric means

---

## CORS & API Integration Notes

- The API returns JSON for all endpoints
- Errors are structured: `{"error": true, "status_code": N, "detail": "..."}`
- Rate limit info comes back in response headers
- The API base URL is `https://geohealth-api-production.up.railway.app`
- Auth header: `X-API-Key: <your-key>`
- The OpenAPI spec at `/openapi.json` can generate TypeScript client code automatically

---

## Project File Structure (Backend)

```
geohealth-api/
├── geohealth/
│   ├── api/
│   │   ├── main.py              # FastAPI app, lifespan, llms.txt routes
│   │   ├── schemas.py           # All Pydantic request/response models
│   │   ├── dependencies.py      # get_db, require_api_key
│   │   ├── middleware.py        # Request logging (pure ASGI)
│   │   ├── exception_handlers.py
│   │   ├── llms_content.py      # llms.txt content constants
│   │   └── routes/
│   │       ├── context.py       # GET /v1/context
│   │       ├── batch.py         # POST /v1/batch
│   │       ├── nearby.py        # GET /v1/nearby
│   │       ├── compare.py       # GET /v1/compare
│   │       ├── trends.py        # GET /v1/trends
│   │       ├── demographics.py  # GET /v1/demographics/compare
│   │       ├── webhooks.py      # CRUD /v1/webhooks
│   │       ├── stats.py         # GET /v1/stats
│   │       └── dictionary.py    # GET /v1/dictionary
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── session.py           # Async engine + session factory
│   ├── services/
│   │   ├── geocoder.py          # Census Bureau + Nominatim fallback
│   │   ├── tract_lookup.py      # PostGIS spatial query
│   │   ├── tract_serializer.py  # ORM → dict
│   │   ├── narrator.py          # Claude AI narrative generation
│   │   ├── cache.py             # LRU + TTL cache
│   │   ├── rate_limiter.py      # Sliding window rate limiter
│   │   ├── metrics.py           # Request/latency metrics
│   │   ├── webhooks.py          # Webhook dispatch
│   │   └── request_context.py   # Request ID via contextvars
│   ├── etl/                     # Data loading pipeline (6 loaders)
│   ├── migrations/              # Alembic schema migrations
│   ├── sdk/                     # Python SDK client library
│   └── mcp/                     # MCP server for Claude agents
├── tests/                       # 192 tests (all mocked, no DB needed)
├── docs/                        # MkDocs documentation site
├── pyproject.toml               # Package config
├── Dockerfile                   # Multi-stage production build
├── docker-compose.yml           # Local dev (API + PostGIS)
├── railway.toml                 # Railway deployment config
└── mkdocs.yml                   # Docs site config
```

---

## Key Considerations for UI Planning

1. **No existing frontend** — this is a greenfield UI project
2. **API is stable and deployed** — all endpoints are live and tested (192 tests)
3. **PostGIS geometry data exists** — tract boundaries are stored but not currently exposed as GeoJSON for map rendering (would need a new endpoint or adaptation)
4. **4 states loaded** — Georgia, Kansas, Minnesota, Missouri (6,784 tracts). Can expand to all 50 states.
5. **Auth is configurable** — can be disabled for development or enabled for production
6. **CORS is open** — ready for any frontend origin (should lock down for production)
7. **OpenAPI spec available** — can auto-generate typed API clients for TypeScript/JavaScript
8. **AI narratives available** — requires Anthropic API key configured on the backend
9. **Rate limits exist** — 60 req/min per key, batch endpoint helps reduce request count
10. **The documentation site already has GitHub Pages set up** — could serve a frontend from there or use a separate deployment
