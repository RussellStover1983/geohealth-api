# GeoHealth Context API

Census-tract-level geographic health intelligence API. Given an address or coordinates, returns demographics, social vulnerability indices, health outcome measures, and an optional AI-generated narrative for the surrounding census tract.

## Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (async ASGI)
- **Database**: PostgreSQL 16 + PostGIS 3.4
- **ORM**: SQLAlchemy 2.0 async (asyncpg driver)
- **Validation**: Pydantic v2, pydantic-settings
- **AI**: Anthropic Claude API (narrative generation)
- **HTTP Client**: httpx (async geocoder calls)
- **ETL**: geopandas, shapely, fiona, pandas (optional `[etl]` extra)

## Project Structure

```
geohealth/
├── config.py                  # pydantic-settings (reads .env)
├── api/
│   ├── main.py                # FastAPI app, lifespan, CORS, middleware
│   ├── auth.py                # API key auth (SHA-256 hashing)
│   ├── dependencies.py        # get_db session dependency
│   ├── exception_handlers.py  # Structured JSON error responses
│   ├── middleware.py           # Request logging (pure ASGI)
│   ├── schemas.py             # Pydantic response models
│   └── routes/
│       ├── context.py         # GET /v1/context — primary endpoint
│       ├── batch.py           # POST /v1/batch — multi-address lookup
│       ├── nearby.py          # GET /v1/nearby — spatial radius search
│       ├── compare.py         # GET /v1/compare — tract comparison
│       └── stats.py           # GET /v1/stats — loading statistics
├── db/
│   ├── models.py              # TractProfile ORM model (Base)
│   └── session.py             # async engine + session factory
├── services/
│   ├── cache.py               # LRU + TTL in-memory cache
│   ├── geocoder.py            # Census → Nominatim fallback chain
│   ├── narrator.py            # Claude narrative generation
│   ├── rate_limiter.py        # Sliding-window per-key rate limiter
│   ├── tract_lookup.py        # PostGIS spatial lookup
│   └── tract_serializer.py    # ORM → dict conversion
└── etl/
    ├── load_all.py            # Orchestrator (python -m geohealth.etl.load_all)
    ├── load_tiger.py          # TIGER/Line shapefiles → geometry
    ├── load_acs.py            # ACS demographics
    ├── load_svi.py            # CDC/ATSDR Social Vulnerability Index
    ├── load_places.py         # CDC PLACES health measures
    ├── compute_sdoh_index.py  # Composite SDOH index
    └── utils.py               # ALL_STATE_FIPS, shared helpers

tests/                         # pytest + pytest-asyncio (91 tests)
```

## Commands

```bash
# Development
docker compose up -d db            # Start PostgreSQL+PostGIS
uvicorn geohealth.api.main:app --reload  # Dev server on :8000

# Full stack (API + DB)
docker compose up --build

# Tests
pytest                             # Run all tests
pytest tests/test_context.py -v    # Single module

# Data loading (requires [etl] extra)
pip install -e ".[etl]"
python -m geohealth.etl.load_all --state 27         # Single state (MN)
python -m geohealth.etl.load_all --state all         # All states
python -m geohealth.etl.load_all --state all --resume  # Resume interrupted load

# Linting
ruff check geohealth/ tests/
```

## Conventions

- **`from __future__ import annotations`** at the top of every module
- **Pure ASGI middleware** — never use `BaseHTTPMiddleware` (see `middleware.py`)
- **Structured JSON errors** — all exceptions return `{"error": true, "status_code": N, "detail": "..."}`
- **ORM-only queries** — all DB access via SQLAlchemy ORM with parameterized queries, never raw SQL strings (except PostGIS extension setup and health check)
- **SHA-256 key hashing** — API keys are hashed before comparison; rate limiter buckets keyed by hash, not plaintext
- **Pydantic response models** — every route declares `response_model` for OpenAPI schema generation
- **Config via environment** — all settings in `config.py` via `pydantic-settings`, overridden by `.env` or env vars

## Architecture Patterns

### Dependency Injection
FastAPI `Depends()` for DB sessions (`get_db`), API key auth (`require_api_key`). Routes declare dependencies as function parameters.

### Caching
Thread-safe LRU + TTL cache (`services/cache.py`). Cache key = coordinates rounded to 4 decimal places (~11m precision). Default: 4096 entries, 1-hour TTL. Configurable via `CACHE_MAXSIZE` / `CACHE_TTL`.

### Rate Limiting
Sliding-window per-key rate limiter (`services/rate_limiter.py`). Each request appends a timestamp; expired timestamps are pruned. Returns `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers on every response (including 429s). Default: 60 requests/60 seconds.

### Geocoder Fallback Chain
`Census Bureau → Nominatim`. Census geocoder returns FIPS codes for direct tract lookup (avoiding spatial query). Nominatim fallback when Census is unavailable.

### Table Creation
Uses `Base.metadata.create_all` in FastAPI lifespan (no Alembic migrations yet). Acceptable for current stage — Alembic should be added when schema changes need to be versioned.

## Database

### Schema: `tract_profiles`

| Column | Type | Notes |
|--------|------|-------|
| `geoid` (PK) | String(11) | FIPS: state(2) + county(3) + tract(6) |
| `state_fips` | String(2) | Indexed for stats aggregation |
| `county_fips` | String(3) | |
| `tract_code` | String(6) | |
| `name` | Text | Human-readable tract name |
| `geom` | MULTIPOLYGON (SRID 4326) | GIST spatial index |
| `total_population` | Integer | |
| `median_household_income` | Float | |
| `poverty_rate` | Float | |
| `uninsured_rate` | Float | |
| `unemployment_rate` | Float | |
| `median_age` | Float | |
| `svi_themes` | JSONB | CDC/ATSDR SVI theme scores |
| `places_measures` | JSONB | CDC PLACES health outcomes |
| `sdoh_index` | Float | Composite SDOH vulnerability index |

### Indexes
- **GIST** on `geom` — spatial queries (`ST_Contains`, `ST_DWithin`)
- **B-tree** on `state_fips` — stats aggregation, state-filtered queries

### Scaling Notes
- JSONB columns (`svi_themes`, `places_measures`) avoid schema migrations when new health metrics are added
- Connection pooling via asyncpg with SQLAlchemy default pool settings
- ~84,000 tracts nationwide — fits comfortably in a single PostgreSQL instance

## Security

### Authentication
- **Optional API key auth** (`AUTH_ENABLED` env var, default `false`)
- Keys sent via `X-API-Key` header, compared as SHA-256 hashes
- Supports both plaintext keys (hashed on the fly) and pre-hashed 64-char hex digests in `API_KEYS` config
- When auth is disabled, all requests are treated as `__anonymous__`
- **Production: set `AUTH_ENABLED=true` and configure `API_KEYS`**

### Rate Limiting
- Per-key sliding window (anonymous users share a single `__anonymous__` bucket)
- Rate limit headers exposed on all responses including 429s
- Batch endpoint (`POST /v1/batch`) counts as 1 rate-limit request regardless of address count — consider per-address limiting for abuse prevention

### CORS
- Default `CORS_ORIGINS=*` (wildcard) — **must be tightened for production**
- Set `CORS_ORIGINS` to comma-separated allowed origins in `.env` (e.g., `https://app.example.com`)

### Data Privacy
- Query parameters (addresses, API keys) are intentionally NOT logged by the request logging middleware
- Structured logs include only method, path, status code, and latency
- No PII stored in application logs

### Error Handling
- All exceptions return structured JSON — no stack traces or internal details leaked to clients
- Unhandled exceptions logged server-side with full traceback, client receives generic "Internal server error"
- 422 validation errors include field-level details (Pydantic errors array)

### Container Security
- Dockerfile uses non-root `appuser` for running the application
- Database credentials should be injected via environment variables, not hardcoded

### Endpoints Without Auth
- `GET /health` — intentionally unauthenticated (health checks must work without credentials)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (DB connectivity) |
| GET | `/v1/context` | Primary lookup — address or lat/lng → tract data + optional narrative |
| POST | `/v1/batch` | Batch address lookup (up to `BATCH_MAX_SIZE` addresses) |
| GET | `/v1/nearby` | Spatial radius search — tracts within N miles |
| GET | `/v1/compare` | Compare two tracts or tract vs state/national average |
| GET | `/v1/stats` | Loading statistics — per-state tract counts |
