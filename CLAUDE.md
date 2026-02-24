# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Census-tract-level geographic health intelligence API. Given an address or coordinates, returns demographics, social vulnerability indices, health outcome measures, and an optional AI-generated narrative for the surrounding census tract.

**Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 + PostGIS 3.4 / SQLAlchemy 2.0 async (asyncpg) / Pydantic v2

## Commands

```bash
# Dev server (requires running PostGIS — see docker compose up -d db)
uvicorn geohealth.api.main:app --reload

# Full stack (API + DB)
docker compose up --build

# Tests — no live DB required, everything is mocked
pytest                             # All 91 tests
pytest tests/test_context.py -v    # Single module
pytest -k test_auth                # Pattern match

# Linting
ruff check geohealth/ tests/      # line-length=99, target py311

# Install
pip install -e ".[dev]"           # Core + test deps
pip install -e ".[dev,etl]"       # Include ETL deps (geopandas, shapely, etc.)

# Data loading
python -m geohealth.etl.load_all --state 27         # Single state
python -m geohealth.etl.load_all --state all --resume  # All states, resumable
```

## Conventions

- **`from __future__ import annotations`** at the top of every module
- **Pure ASGI middleware** — never use `BaseHTTPMiddleware` (see `middleware.py`)
- **Structured JSON errors** — all exceptions return `{"error": true, "status_code": N, "detail": "..."}`
- **ORM-only queries** — all DB access via SQLAlchemy ORM, never raw SQL strings (except PostGIS extension setup and health check)
- **SHA-256 key hashing** — API keys hashed before comparison; rate limiter buckets keyed by hash, not plaintext
- **Pydantic response models** — every route declares `response_model`
- **Config via environment** — all settings in `config.py` via `pydantic-settings`, overridden by `.env`
- **Ruff** — line-length 99, target py311 (configured in `pyproject.toml`)

## Architecture

### Request Flow (example: `GET /v1/context?address=...`)

```
Request → ASGI Logging Middleware → CORS → Route Handler
  → require_api_key (Depends) → SHA-256 hash check or __anonymous__
  → rate_limiter.is_allowed(key_hash) → 429 if exceeded
  → geocode(address) → Census Bureau, fallback to Nominatim
  → Cache check (coords rounded to 4 decimal places)
  → lookup_tract(session, lat, lng, fips?) → PostGIS ST_Contains, fallback to FIPS GEOID lookup
  → tract_to_dict (ORM → dict serialization)
  → Cache store
  → generate_narrative(tract_data) if ?narrative=true → Anthropic Claude API (graceful None on failure)
  → ContextResponse (Pydantic model) with rate-limit + response-time headers
```

### Dependency Injection

Routes use `Depends()` for DB sessions (`get_db`) and auth (`require_api_key`). In tests, override with `app.dependency_overrides[get_db] = mock_fn` and clear in finally blocks.

### Geocoder Fallback Chain

Census Bureau geocoder → Nominatim. Census returns FIPS codes enabling direct GEOID lookup (no spatial query needed). Nominatim fallback provides only coordinates, requiring PostGIS `ST_Contains`.

### Caching

Thread-safe LRU + TTL cache (`services/cache.py`). Cache key = coordinates rounded to 4 decimal places (~11m). Defaults: 4096 entries, 1-hour TTL. Configurable via `CACHE_MAXSIZE` / `CACHE_TTL`.

### Rate Limiting

Sliding-window per-key rate limiter (`services/rate_limiter.py`). Thread-safe with `threading.Lock`. Returns `X-RateLimit-*` headers on every response including 429s. Default: 60 req/60s.

### Table Creation

`Base.metadata.create_all` in FastAPI lifespan — no Alembic migrations yet. Single table `tract_profiles` with GIST index on `geom` and B-tree on `state_fips`.

## Testing Patterns

Tests use **no live database** — everything is mocked via `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`).

- **pytest-asyncio** with `asyncio_mode = "auto"` — async test functions are auto-detected
- **`client` fixture** in `conftest.py` — `httpx.AsyncClient` with `ASGITransport(app=app)`
- **Autouse fixture** clears rate limiter before/after every test
- **Dependency override pattern**: `app.dependency_overrides[dep] = mock` in try/finally blocks
- **Service mocking**: `patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock)`
- Cache must be cleared between tests that test caching behavior

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | DB connectivity check |
| GET | `/v1/context` | Yes | Primary lookup — address or lat/lng → tract data + optional narrative |
| POST | `/v1/batch` | Yes | Multi-address lookup (up to `BATCH_MAX_SIZE`) |
| GET | `/v1/nearby` | Yes | Spatial radius search — tracts within N miles |
| GET | `/v1/compare` | Yes | Compare two tracts or tract vs averages |
| GET | `/v1/stats` | Yes | Per-state tract counts |

## Key Configuration (env vars / .env)

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | — | `postgresql+asyncpg://...` |
| `AUTH_ENABLED` | `false` | Must be `true` in production |
| `API_KEYS` | — | Comma-separated; supports plaintext or pre-hashed SHA-256 hex |
| `CORS_ORIGINS` | `*` | Must restrict in production |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-key limit |
| `ANTHROPIC_API_KEY` | — | For narrative generation |
| `BATCH_MAX_SIZE` | `50` | Max addresses per batch request |
