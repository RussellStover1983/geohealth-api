# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Autonomy

You have FULL autonomy to complete tasks end-to-end without stopping to ask for permission. Specifically:

- **DO NOT ask for permission to search the web.** If you need a library, documentation, or any reference material — just search for it. Do not stop and ask "should I search for X?" Just do it.
- **DO NOT ask for permission to create, modify, or delete files.** You are working in your own project directory. Create whatever files you need, overwrite them, restructure them, delete temp files — whatever it takes. This is your workspace.
- **DO NOT ask for permission to install packages.** If you need a dependency — install it immediately and keep moving.
- **DO NOT stop to present partial work and ask "should I continue?"** Yes, you should continue. Always. Build the entire thing from start to finish in one session.
- **DO NOT ask clarifying questions unless the task is truly blocked.** If something is ambiguous, make a reasonable decision, document it in a comment, and keep building.
- **DO ask to test against real data/screenshots once something is fully built and working.** That's the one time you should stop and check in.

## Project

Census-tract-level geographic health intelligence API. Given an address or coordinates, returns demographics, social vulnerability indices, health outcome measures, and an optional AI-generated narrative for the surrounding census tract.

**Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 + PostGIS 3.4 / SQLAlchemy 2.0 async (asyncpg) / Pydantic v2

**Live deployments**:
- API: `https://geohealth-api-production.up.railway.app`
- Docs: `https://russellstover1983.github.io/geohealth-api/`
- PyPI: `pip install geohealth-api` (v0.1.1)

**Data loaded**: Minnesota (27), Kansas (20), Missouri (29) — 3,988 census tracts total.

## Commands

```bash
# Dev server (requires running PostGIS — see docker compose up -d db)
uvicorn geohealth.api.main:app --reload

# Full stack (API + DB)
docker compose up --build

# Tests — no live DB required, everything is mocked
pytest                             # All 192 tests
pytest tests/test_context.py -v    # Single module
pytest -k test_auth                # Pattern match

# Linting
ruff check geohealth/ tests/      # line-length=99, target py311

# Install
pip install -e ".[dev]"           # Core + test deps
pip install -e ".[dev,etl]"       # Include ETL deps (geopandas, shapely, etc.)
pip install -e ".[mcp]"          # MCP server for Claude agents

# Data loading
python -m geohealth.etl.load_all --state 27         # Single state
python -m geohealth.etl.load_all --state all --resume  # All states, resumable

# Additional ETL loaders (run after load_all)
python -m geohealth.etl.load_trends --state 27      # Multi-year ACS trend data (2018-2022)
python -m geohealth.etl.load_epa --state 27          # EPA EJScreen environmental data

# Migrations (requires running PostGIS)
alembic upgrade head                                  # Apply all migrations
alembic revision --autogenerate -m "description"      # Generate new migration
alembic stamp head                                    # Mark existing DB as current (for DBs created by create_all)
alembic history                                       # Show migration history

# Docs site (local preview)
pip install mkdocs-material
mkdocs serve                      # http://localhost:8000
mkdocs build --strict             # Build to site/ directory
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

**Known issue**: The ETL's `ensure_table()` calls `alembic upgrade head`, which triggers `fileConfig(alembic.ini)` and resets the root logger to WARN level. This suppresses all subsequent ETL log output. The ETL still runs correctly — it just produces no visible output. Use `logging.basicConfig(force=True)` after `ensure_table` to restore logging.

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

Each external data source gets its own JSONB column (`svi_themes`, `places_measures`, `epa_data`, `trends`). This means:
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

### MCP Server (Agent Integration)

The `geohealth/mcp/` package wraps every API endpoint as native tools for Claude Desktop, Claude Code, and other MCP-compatible agents. Built with the `mcp` Python SDK (FastMCP).

```
geohealth/mcp/
├── __init__.py      # Lazy import of mcp server instance
├── server.py        # FastMCP tool definitions + lifespan
└── __main__.py      # python -m geohealth.mcp entry point
```

The MCP server calls the deployed API via `AsyncGeoHealthClient` (the existing SDK) — it does not access the database directly. Credentials come from `GEOHEALTH_BASE_URL` and `GEOHEALTH_API_KEY` env vars. Eight tools: `lookup_health_context`, `batch_health_lookup`, `find_nearby_tracts`, `compare_tracts`, `get_tract_trends`, `compare_demographics`, `get_data_dictionary`, `get_tract_statistics`.

The `mcp` dependency is optional (`pip install -e ".[mcp]"`). Tests use `pytest.importorskip` to skip MCP tests when the package isn't installed.

### Agent Discoverability

- **`/llms.txt`** — Concise agent-readable API overview (llmstxt.org standard)
- **`/llms-full.txt`** — Full reference with clinical context, field definitions, SDK examples, and MCP setup
- **`/v1/dictionary`** — Structured data dictionary endpoint with clinical interpretation guidance per field

Content is defined in `geohealth/api/llms_content.py` (string constants) and `geohealth/api/routes/dictionary.py` (static field definitions). The dictionary requires auth; the llms.txt files are public.

### Historical Trends

The `trends` JSONB column on `tract_profiles` stores year-keyed ACS snapshots (e.g., `{"2018": {"poverty_rate": 20.1, ...}, "2019": {...}}`). The `GET /v1/trends?geoid=...` endpoint returns all available years sorted ascending, plus computed change metrics (absolute change, percent change) between earliest and latest data points. The current ACS year (2022) is always included as the latest snapshot from the fixed ORM columns.

ETL: `python -m geohealth.etl.load_trends --state 27 --start-year 2018 --end-year 2022`

### Environmental Data (EPA EJScreen)

The `epa_data` JSONB column stores EPA EJScreen environmental indicators per tract. Keys include `pm25`, `ozone`, `diesel_pm`, `air_toxics_cancer_risk`, `respiratory_hazard_index`, `traffic_proximity`, `lead_paint_pct`, `superfund_proximity`, `rmp_proximity`, `hazardous_waste_proximity`, `wastewater_discharge`. The field is included in the standard context response via `tract_to_dict`.

ETL: `python -m geohealth.etl.load_epa --state 27`. Tries the EJScreen Socrata API first; falls back to generating estimated values correlated with existing SVI/poverty data.

### Demographic Comparison with Rankings

`GET /v1/demographics/compare?geoid=...` returns a comprehensive comparison of a tract against county, state, and national averages. For each of 7 metrics, it computes:
- **Averages**: tract value vs county/state/national mean
- **Percentile rankings**: where the tract falls within county/state/national distributions (0-100)

Percentiles are computed via batch SQL aggregation — 3 queries (county/state/national) using `func.count(case(...))` instead of 43+ individual queries.

### Webhook Subscriptions

CRUD endpoints at `/v1/webhooks` let authenticated users register callback URLs for event notifications. Subscriptions are stored in the `webhook_subscriptions` table (PostgreSQL), scoped to the owning API key hash.

**Events**: `data.updated` (ETL refreshes), `threshold.exceeded` (metric crosses threshold).

**Filters**: Optional `state_fips` list, `geoids` list, and `thresholds` dict (metric + operator + value).

**Delivery**: `services/webhooks.py` dispatches events via `httpx.AsyncClient` with exponential backoff retry (2^attempt seconds, up to `WEBHOOK_MAX_RETRIES` attempts). Retries only on 5xx errors and network exceptions; 4xx errors fail immediately. Payloads include event type, timestamp, and data. If a `secret` is set, an `X-Webhook-Signature` HMAC-SHA256 header is included for verification.

**ETL integration**: `load_all.py` fires `data.updated` events to all active webhook subscribers after each state completes successfully.

**Limits**: `WEBHOOK_MAX_PER_KEY` (default 10) active subscriptions per API key.

### Documentation Site (GitHub Pages)

MkDocs + Material theme deployed to GitHub Pages. Five pages: Home, Quick Start, API Reference, Data Dictionary, Python SDK & MCP.

```
mkdocs.yml           # Site config (theme, nav, extensions)
docs/
├── index.md         # Landing page — clinical value proposition
├── quickstart.md    # First call in 5 minutes
├── api-reference.md # All endpoints with parameters, examples, responses
├── data-dictionary.md # 37 fields with clinical thresholds (including EPA)
└── sdk.md           # Python SDK + MCP server setup
```

Auto-deploys via `.github/workflows/docs.yml` on push to master when `docs/` or `mkdocs.yml` change. The `site/` build output is gitignored.

### Deployment

The API deploys to **Railway** (Pro plan, $5/month) using the existing multi-stage Dockerfile. Railway configuration lives in `railway.toml`. The Dockerfile CMD uses shell form with `${PORT:-8000}` so Railway can inject its dynamic port while local `docker compose` falls back to 8000. PostGIS runs as a custom Docker service on Railway (their managed Postgres lacks PostGIS binaries). See the README's "Deployment (Railway)" section for full setup instructions.

**Important**: Set `PGDATA=/var/lib/postgresql/data/pgdata` on the PostGIS service to avoid the `lost+found` volume conflict.

## Testing Patterns

Tests use **no live database** — everything is mocked via `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`).

- **pytest-asyncio** with `asyncio_mode = "auto"` — async test functions are auto-detected
- **`client` fixture** in `conftest.py` — `httpx.AsyncClient` with `ASGITransport(app=app)`
- **Autouse fixtures** clear rate limiter and reset metrics before/after every test
- **Dependency override pattern**: `app.dependency_overrides[dep] = mock` in try/finally blocks
- **Service mocking**: `patch("geohealth.api.routes.context.geocode", new_callable=AsyncMock)`
- **Module-level env override**: `conftest.py` sets `os.environ["RUN_MIGRATIONS"] = "false"` *before* any app import — moving it below the import breaks startup (Alembic tries to connect to a DB)
- Cache must be cleared between tests that test caching behavior

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | DB connectivity check |
| GET | `/v1/context` | Yes | Primary lookup — address or lat/lng → tract data + optional narrative |
| POST | `/v1/batch` | Yes | Multi-address lookup (up to `BATCH_MAX_SIZE`) |
| GET | `/v1/nearby` | Yes | Spatial radius search — tracts within N miles |
| GET | `/v1/compare` | Yes | Compare two tracts or tract vs county/state/national averages |
| GET | `/v1/trends` | Yes | Historical trend data — multi-year ACS with change metrics |
| GET | `/v1/demographics/compare` | Yes | Demographic rankings — tract vs county/state/national with percentiles |
| POST | `/v1/webhooks` | Yes | Create webhook subscription |
| GET | `/v1/webhooks` | Yes | List webhook subscriptions |
| GET | `/v1/webhooks/{id}` | Yes | Get webhook subscription details |
| DELETE | `/v1/webhooks/{id}` | Yes | Delete webhook subscription |
| GET | `/v1/dictionary` | Yes | Data dictionary — field definitions with clinical context |
| GET | `/v1/stats` | Yes | Per-state tract counts |
| GET | `/metrics` | No | Application metrics (counters, latency percentiles, cache stats) |
| GET | `/llms.txt` | No | Agent-readable API overview (llmstxt.org) |
| GET | `/llms-full.txt` | No | Full agent-readable reference with clinical context |

## Key Configuration (env vars / .env)

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | — | `postgresql+asyncpg://...` |
| `DATABASE_URL_SYNC` | — | `postgresql://...` (for Alembic and ETL) |
| `AUTH_ENABLED` | `false` | Must be `true` in production |
| `API_KEYS` | — | Comma-separated; supports plaintext or pre-hashed SHA-256 hex |
| `CORS_ORIGINS` | `*` | Must restrict in production |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-key limit |
| `ANTHROPIC_API_KEY` | — | For narrative generation |
| `BATCH_MAX_SIZE` | `50` | Max addresses per batch request |
| `WEBHOOK_MAX_PER_KEY` | `10` | Max active webhook subscriptions per API key |
| `WEBHOOK_TIMEOUT` | `10` | Webhook delivery timeout in seconds |
| `WEBHOOK_MAX_RETRIES` | `3` | Max delivery retry attempts |
| `RUN_MIGRATIONS` | `true` | Set `false` in tests to skip Alembic on startup |
| `LOG_FORMAT` | `text` | `text` for human-readable, `json` for structured JSON |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |

## CI/CD

GitHub Actions workflows (`.github/workflows/`):

### `ci.yml` — runs on push to master and on PRs
1. **lint** — installs ruff, runs `ruff check geohealth/ tests/`
2. **test** — installs `.[dev]`, runs `pytest --tb=short -q` with `RUN_MIGRATIONS=false`
3. **docker** — (push to master only, after lint+test pass) builds multi-stage Docker image and pushes to GHCR with `sha-<commit>` and `latest` tags, using GitHub Actions build cache

### `docs.yml` — runs on push to master when `docs/` or `mkdocs.yml` change
1. **build** — installs `mkdocs-material`, builds with `--strict`
2. **deploy** — uploads to GitHub Pages via `actions/deploy-pages`

Also supports `workflow_dispatch` for manual triggers.

### Docker Production Setup

- **Multi-stage build** — builder stage compiles deps into `/opt/venv`, runtime stage copies only the venv + app code with minimal system packages (`libpq5`, `curl`)
- **Gunicorn + Uvicorn workers** — `gunicorn --worker-class uvicorn.workers.UvicornWorker --workers 2` (configured in `Dockerfile` CMD)
- **Non-root user** — runs as `appuser`
- **Health checks** — `docker-compose.yml` includes health checks for both `db` (pg_isready) and `api` (curl /health)
- **Restart policy** — `restart: unless-stopped` on both services

## Key Files

| File | Description |
|------|-------------|
| `geohealth/config.py` | All settings via pydantic-settings |
| `geohealth/api/main.py` | FastAPI app entry point, lifespan, llms.txt routes |
| `geohealth/api/routes/` | Endpoint modules (context, batch, nearby, compare, trends, demographics, webhooks, stats, dictionary) |
| `geohealth/api/schemas.py` | Pydantic request/response models |
| `geohealth/api/llms_content.py` | llms.txt / llms-full.txt content constants |
| `geohealth/services/` | Geocoder, tract lookup, cache, rate limiter, narrator, metrics, webhooks |
| `geohealth/services/tract_serializer.py` | ORM model → dict serialization (`tract_to_dict`) |
| `geohealth/services/request_context.py` | Request ID via contextvars (used by middleware + logging) |
| `geohealth/db/models.py` | `tract_profiles` + `webhook_subscriptions` tables (SQLAlchemy ORM) |
| `geohealth/db/session.py` | Async engine + session factory |
| `geohealth/etl/` | ETL pipeline (see listing below) |
| `geohealth/migrations/env.py` | Alembic config (uses `_get_sync_url()` fallback) |
| `geohealth/sdk/client.py` | Typed async + sync SDK clients |
| `geohealth/mcp/server.py` | MCP server wrapping API as tools for Claude agents |
| `mkdocs.yml` | MkDocs + Material theme config |
| `docs/` | Documentation site (5 pages) |
| `railway.toml` | Railway build/deploy config |
| `pyproject.toml` | Package metadata, deps, ruff + pytest config |

### ETL Pipeline

```
geohealth/etl/
├── load_tiger.py          # TIGER/Line shapefiles → tract geometries
├── load_acs.py            # ACS demographics (population, income, poverty, etc.)
├── load_svi.py            # CDC/ATSDR Social Vulnerability Index themes
├── load_places.py         # CDC PLACES health outcome measures
├── load_trends.py         # Multi-year ACS data (2018-2022) → trends JSONB column
├── load_epa.py            # EPA EJScreen environmental indicators → epa_data JSONB column
├── compute_sdoh_index.py  # Composite SDOH vulnerability index from loaded data
├── load_all.py            # Orchestrator — runs all loaders for a state
└── utils.py               # Shared ETL utilities
```
