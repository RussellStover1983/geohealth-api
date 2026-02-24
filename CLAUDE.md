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

# Migrations (requires running PostGIS)
alembic upgrade head                                  # Apply all migrations
alembic revision --autogenerate -m "description"      # Generate new migration
alembic stamp head                                    # Mark existing DB as current (for DBs created by create_all)
alembic history                                       # Show migration history
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

### Schema Migrations

Alembic manages schema evolution. Migrations live in `geohealth/migrations/versions/`. On startup, `alembic upgrade head` runs automatically unless `RUN_MIGRATIONS=false` (tests set this). The `env.py` reads `database_url_sync` from pydantic-settings and filters out the PostGIS `spatial_ref_sys` table during autogenerate.

For existing databases created by the old `create_all`, run `alembic stamp head` once to mark them as current.

### OpenAPI Documentation

The API is self-documenting via OpenAPI 3.1:
- **Swagger UI** at `/docs` — interactive endpoint explorer with try-it-out
- **ReDoc** at `/redoc` — clean reference documentation
- **OpenAPI JSON** at `/openapi.json` — machine-readable schema

Documentation lives in the code: Pydantic model `Field(description=...)` and `json_schema_extra` examples drive the schema; FastAPI route decorators provide `summary`, `description`, and per-status-code `responses`. The `_DESCRIPTION` and `_OPENAPI_TAGS` constants in `main.py` supply the top-level API description and tag groupings.

### Python SDK

Typed client library in `geohealth/sdk/` wrapping every API endpoint:

```
geohealth/sdk/
├── __init__.py      # Re-exports public API
├── models.py        # RateLimitInfo frozen dataclass
├── exceptions.py    # GeoHealthError hierarchy (Auth, RateLimit, NotFound, Validation)
└── client.py        # AsyncGeoHealthClient + GeoHealthClient
```

Both clients accept `base_url`, `api_key`, `timeout`, and a `_transport` parameter for testing. Methods return typed Pydantic models from `geohealth.api.schemas`. The `last_rate_limit` attribute is updated after every request. Tests use `httpx.MockTransport` — no server or patching needed.

### JSONB Data Source Pattern

Each external data source gets its own JSONB column (e.g., `svi_themes`, `places_measures`). This means:
- **New data source** (e.g., `epa_data JSONB`) → one `alembic revision --autogenerate` migration
- **New metric within existing source** (e.g., adding `"pm25": 8.2` to `places_measures`) → no migration needed
- **New computed index** (e.g., `env_index Float`) → one migration

Existing fixed ACS columns (`poverty_rate`, etc.) stay as-is for backward compatibility. `TractDataModel` has `extra = "allow"` so new JSONB fields flow through the API automatically.

### Observability

**Request correlation**: Every request gets an `X-Request-ID` header (client-sent IDs are echoed; otherwise a UUID is generated). The ID is stored in a `contextvars.ContextVar` and automatically included in all log lines.

**Structured logging** (`logging_config.py`): Two formatters (`JSONFormatter` for log aggregators, `TextFormatter` for humans) selected via `LOG_FORMAT`. Both include the request ID. `setup_logging()` is called once at startup in the lifespan handler.

**Application metrics** (`services/metrics.py`): Thread-safe `MetricsCollector` singleton tracks request counters, status code distribution, cache hit/miss rates, geocoder source success/failure, narrative success/failure, and latency percentiles (p50/p90/p95/p99). Exposed via `GET /metrics`. No external dependencies — uses only stdlib `threading` and `time`.

**Instrumented services**: Cache (`get()` → hit/miss), geocoder (`geocode()` → census/nominatim/failure), narrator (`generate_narrative()` → success/failure).

**Enhanced `/health`**: Returns cache size/hit-rate, rate limiter active keys, and uptime when healthy. Degraded response stays unchanged for backward compatibility.

### Deployment

The API deploys to **Railway** using the existing multi-stage Dockerfile. Railway configuration lives in `railway.toml`. The Dockerfile CMD uses shell form with `${PORT:-8000}` so Railway can inject its dynamic port while local `docker compose` falls back to 8000. PostGIS runs as a custom Docker service on Railway (their managed Postgres lacks PostGIS binaries). See the README's "Deployment (Railway)" section for full setup instructions.

## Testing Patterns

Tests use **no live database** — everything is mocked via `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`).

- **pytest-asyncio** with `asyncio_mode = "auto"` — async test functions are auto-detected
- **`client` fixture** in `conftest.py` — `httpx.AsyncClient` with `ASGITransport(app=app)`
- **Autouse fixtures** clear rate limiter and reset metrics before/after every test
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
| GET | `/metrics` | No | Application metrics (counters, latency percentiles, cache stats) |

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
| `RUN_MIGRATIONS` | `true` | Set `false` in tests to skip Alembic on startup |
| `LOG_FORMAT` | `text` | `text` for human-readable, `json` for structured JSON |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push to master and on PRs:

1. **lint** — installs ruff, runs `ruff check geohealth/ tests/`
2. **test** — installs `.[dev]`, runs `pytest --tb=short -q` with `RUN_MIGRATIONS=false`
3. **docker** — (push to master only, after lint+test pass) builds multi-stage Docker image and pushes to GHCR with `sha-<commit>` and `latest` tags, using GitHub Actions build cache

### Docker Production Setup

- **Multi-stage build** — builder stage compiles deps into `/opt/venv`, runtime stage copies only the venv + app code with minimal system packages (`libpq5`, `curl`)
- **Gunicorn + Uvicorn workers** — `gunicorn --worker-class uvicorn.workers.UvicornWorker --workers 2` (configured in `Dockerfile` CMD)
- **Non-root user** — runs as `appuser`
- **Health checks** — `docker-compose.yml` includes health checks for both `db` (pg_isready) and `api` (curl /health)
- **Restart policy** — `restart: unless-stopped` on both services
