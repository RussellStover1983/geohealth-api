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

Census-tract-level geographic health intelligence API + interactive frontend explorer.

**Stack**: Python 3.11+ / FastAPI / PostgreSQL 16 + PostGIS 3.4 / SQLAlchemy 2.0 async / Pydantic v2
**Frontend**: Next.js 14 / TypeScript / Tailwind CSS / MapLibre GL / Zustand — deployed on Vercel
**Live**: API `https://geohealth-api-production.up.railway.app` | Frontend `https://geohealth-api.vercel.app` | Docs `https://russellstover1983.github.io/geohealth-api/` | PyPI `pip install geohealth-api`
**Data**: GA (13), KS (20), MN (27), MO (29) — 6,784 census tracts. ETL supports all 50 states + DC.

For detailed architecture, endpoint tables, file listings, and deployment config, see `ARCHITECTURE.md`.

## Commands

```bash
# Dev server (requires running PostGIS — see docker compose up -d db)
uvicorn geohealth.api.main:app --reload

# Full stack (API + DB)
docker compose up --build

# Tests — no live DB required, everything is mocked
pytest                             # All tests (~197)
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

# Frontend (geohealth-ui/)
cd geohealth-ui
pnpm install                      # Install deps
pnpm dev                          # Dev server on localhost:3000
pnpm build                        # Production build (verify before push)

# DPC Market Fit API (dpc-market-fit/) — separate FastAPI app
cd dpc-market-fit
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload     # Dev server
python -m pytest                               # All DPC tests (~75)
python -m pytest tests/test_scoring.py -v      # Single module
```

## Frontend (`geohealth-ui/`)

**Stack**: Next.js 14 (App Router) + TypeScript + Tailwind CSS 3.4 + shadcn/ui + MapLibre GL + Recharts + Zustand + Framer Motion
**Package manager**: pnpm

| File | Description |
|------|-------------|
| `components/map/MapContainer.tsx` | Main map with choropleth rendering, tract click selection |
| `components/panels/SearchPanel.tsx` | Address search with autocomplete dropdown |
| `components/panels/LayerPanel.tsx` | SDOH metric layer switcher |
| `components/panels/TractDetailPanel.tsx` | Slide-out panel with tract details |
| `lib/api/client.ts` | API client wrapping all backend endpoints |
| `lib/api/hooks.ts` | React hooks (context lookup, nearby, trends, autocomplete) |
| `lib/api/types.ts` | TypeScript types mirroring backend Pydantic models |
| `lib/store.ts` | Zustand store (viewport, active layer, selected tract, UI state) |
| `lib/map/styles.ts` | Choropleth color scales and metric configs |
| `app/api/autocomplete/route.ts` | Server-side Nominatim proxy for address suggestions |
| `app/api/geohealth/[...path]/route.ts` | API proxy to backend (avoids CORS) |

## DPC Market Fit API (`dpc-market-fit/`)

Standalone FastAPI app evaluating geographic viability for Direct Primary Care practices. **Not** part of the main `geohealth` package — has its own `requirements.txt`, `Dockerfile`, and test suite.

**Scoring dimensions** (each 0-100): Demand, Affordability, Supply Gap, Employer, Competition
**Data sources**: Census ACS, CDC PLACES, CDC SVI, NPPES NPI, HRSA HPSA, Census CBP
**States loaded**: GA, KS, MN, MO (same as main API)

| Path | Description |
|------|-------------|
| `app/main.py` | FastAPI entry point with routers for each dimension + composite score |
| `app/services/scoring.py` | Scoring engine — all 5 dimensions with data completeness tracking |
| `app/services/geocoder.py` | Census Bureau geocoder (shared pattern with main API) |
| `app/routers/` | Endpoint modules: `demand`, `supply`, `employer`, `competition`, `market_fit`, `providers` |
| `app/data/` | CSV data files (NPI tract counts, provider lookups per state) |
| `tests/` | All mocked, run with `cd dpc-market-fit && python -m pytest` |

**Deployment**: Railway service `dpc-market-fit`, deployed via `railway up --service dpc-market-fit --path-as-root dpc-market-fit`
**Live**: `https://dpc-market-fit-production.up.railway.app`
**Frontend integration**: Proxy at `geohealth-ui/app/api/dpc/[...path]/route.ts`, hook `useMarketFit()` in `lib/api/hooks.ts`, types at bottom of `lib/api/types.ts`

## Data Dependencies

- **NPPES NPI registry**: `C:\dev\shared\data\nppes\raw\npidata_pfile_*.csv` — used by dpc-market-fit ETL for provider tract counts
- **NPPES derived files**: `C:\dev\shared\data\nppes\derived\providers_XX.csv`, `npi_tract_counts.csv` — pre-computed by `shared/scripts/extract_state_providers.py`
- **HRSA HPSA**: `C:\dev\shared\data\hrsa\hpsa_primary_care.csv` — used by dpc-market-fit for supply gap scoring
- **CDC SVI/PLACES**: fetched via APIs, cached in PostGIS
- **Census TIGER/ACS**: fetched via APIs, loaded into PostGIS by ETL loaders

## Rules (enforce automatically — never ask)

- Every new Python module MUST start with `from __future__ import annotations`. Add it yourself if missing.
- If you see `BaseHTTPMiddleware` anywhere, refactor to pure ASGI immediately. Do not ask.
- Every route MUST declare a `response_model`. Add it yourself.
- All exceptions MUST return `{"error": true, "status_code": N, "detail": "..."}`. Implement it yourself.
- API keys are SHA-256 hashed before comparison. Never log or store plaintext keys.
- All DB access via SQLAlchemy ORM — never raw SQL (except PostGIS extension setup and health check).
- All settings via pydantic-settings in `config.py`. Never hardcode config values.
- Ruff: line-length 99, target py311. Fix lint errors yourself after every change.
- Tests use mocks only — never connect to a real database. Use `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`).
- `conftest.py` sets `os.environ["RUN_MIGRATIONS"] = "false"` BEFORE any app import. Never move this below the import.
- New JSONB data sources get their own column on `tract_profiles`. New metrics within an existing source need no migration.
- `TractDataModel` has `extra = "allow"` — new JSONB fields flow through the API automatically.

## Workflows (complete all steps — do not stop partway)

**Adding/modifying an API endpoint:**
1. Implement the route in `geohealth/api/routes/`
2. Add/update Pydantic models in `geohealth/api/schemas.py`
3. Add/update tests in `tests/`
4. Update `docs/api-reference.md`
5. Update TypeScript types in `geohealth-ui/lib/api/types.ts` if the response shape changed
6. Run `pytest` — fix any failures
7. Run `ruff check geohealth/ tests/` — fix any lint errors

**Modifying DB models:**
1. Update `geohealth/db/models.py`
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Update `geohealth/services/tract_serializer.py` if serialization changed
4. Update `docs/data-dictionary.md`
5. Run `pytest` — fix any failures

**Adding a new data source:**
1. Create ETL loader in `geohealth/etl/` following existing patterns
2. Add JSONB column to `geohealth/db/models.py`
3. Generate migration: `alembic revision --autogenerate -m "add X data"`
4. Update `geohealth/services/tract_serializer.py` to include the new field
5. Update `docs/data-dictionary.md` with field definitions
6. Run `pytest` — fix any failures

**DPC Market Fit changes:**
1. Make changes in `dpc-market-fit/`
2. Run `cd dpc-market-fit && python -m pytest` — fix any failures
3. DPC uses the same `from __future__ import annotations` rule as main API
4. If response shapes changed, update `geohealth-ui/lib/api/types.ts` (DPC types at bottom)

**Frontend changes:**
1. Make the change in `geohealth-ui/`
2. Run `pnpm build` to verify — fix any errors
3. If API types changed, update `geohealth-ui/lib/api/types.ts` first

**Any Python change:**
1. Run `ruff check geohealth/ tests/` and fix issues
2. Run `pytest` and fix failures
3. Do NOT report lint or test failures to me — just fix them

## Error Recovery (handle these yourself — do not stop to report)

- Tests fail after your change: read the traceback, fix it, re-run. Repeat up to 3 times before asking.
- Ruff lint errors: fix them immediately.
- Package install fails: check version constraints, try alternatives.
- Alembic migration fails: read the error, fix the migration, retry.
- Import errors: check the module path, fix it.
- Frontend build fails: read the error output, fix it, rebuild.
- Only ask me for help if you have made 3 genuine attempts to fix the problem yourself.

## Definition of Done

A task is NOT complete until ALL of these pass:
1. The code works (tested manually or via pytest)
2. All existing tests still pass (`pytest` for main API, `cd dpc-market-fit && python -m pytest` for DPC)
3. Lint is clean (`ruff check geohealth/ tests/`)
4. If frontend was touched: `pnpm build` succeeds
5. Any new public API endpoint has tests
6. Any new/changed main API endpoint is documented in `docs/api-reference.md`
