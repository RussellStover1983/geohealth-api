# GeoHealth API: All 50 States + DC ETL Plan

## Objective

Load census tract data for all 50 US states + DC into the production Railway PostGIS database. Currently 4 states (GA, KS, MN, MO) with 6,784 tracts. Target: ~74,000 tracts across 51 jurisdictions.

**Excludes US territories** (AS, GU, MP, PR, VI) — Census ACS/PLACES coverage is inconsistent for territories. Can be added later as a follow-up.

---

## Prerequisites

Before running, the operator must ensure:

1. **Census API key** is in `.env` as `CENSUS_API_KEY` (already done)
2. **Railway DATABASE_URL_SYNC** is in `.env` — this is CRITICAL. The ETL uses `settings.database_url_sync` which defaults to `postgresql://geohealth:geohealth@localhost:5432/geohealth`. To load into Railway production, you must set:
   ```
   DATABASE_URL_SYNC=postgresql://<user>:<password>@<host>:<port>/railway
   ```
   Get this from Railway dashboard: project `elegant-success` → service `postgis` → Variables → `DATABASE_URL` (convert the `+asyncpg` variant to plain `postgresql://`)
3. **Python environment** has ETL deps installed: `pip install -e ".[dev,etl]"`
4. **Local PostGIS is NOT required** — ETL connects directly to Railway via the connection string
5. **Network**: Stable internet for ~12-14 hours of API calls (Census, CDC, EPA)

---

## Phase 1: Core ETL (TIGER + ACS + SVI + PLACES + SDOH Index)

This is the main pipeline. Run from the repo root:

```bash
python -m geohealth.etl.load_all --state all --resume
```

### What `--resume` does

- Queries `tract_profiles` for states that already have geometry (`geom IS NOT NULL`)
- Skips the TIGER shapefile download for those states (GA, KS, MN, MO)
- Still re-runs ACS, SVI, PLACES, and SDOH index for all states (upsert pattern)

### Pipeline per state (5 steps)

| Step | Module | Data Source | API Calls | Est. Time |
|------|--------|-------------|-----------|-----------|
| 1 | `load_tiger` | Census TIGER/Line shapefiles | 1 HTTP download (~1-10 MB ZIP) | 30-60s |
| 2 | `load_acs` | Census ACS 5-Year API | 2 calls (detail + subject tables) | 5-10s |
| 3 | `load_svi` | CDC SVI national CSV | 0 (downloaded once, filtered per state) | 2-5s |
| 4 | `load_places` | CDC PLACES Socrata API | 1-5 calls (paginated, 50K rows/page) | 10-30s |
| 5 | `compute_sdoh_index` | In-database calculation | 0 (reads from DB, writes back) | 2-5s |

### Key details

- **SVI national CSV** (~55 MB) downloads once at pipeline start, then filters per state — no repeated downloads
- **Census API rate limit**: 50 req/sec with API key. Pipeline makes ~2 calls/state = ~102 total. Well within limits.
- **PLACES (Socrata)** has no strict rate limit but paginates at 50K rows. Large states (CA, TX, FL) may need 3-5 pages.
- **Error isolation**: If one state fails, the pipeline logs the error and continues to the next state. Failed states reported at the end.
- **Idempotent**: TIGER deletes existing rows for a state before re-inserting. ACS/SVI/PLACES use upsert. Safe to re-run.
- **Alembic migrations**: Run automatically at start (`ensure_table` calls `alembic upgrade head`)

### Expected runtime

- Per state: ~1-2 minutes (TIGER download + API calls + DB writes)
- 47 new states + 4 resumed: ~60-90 minutes total
- If TIGER downloads are slow: could stretch to 2-3 hours

### Expected output

- ~74,000 rows in `tract_profiles` with columns: `geoid`, `state_fips`, `county_fips`, `tract_code`, `name`, `geom`, `total_population`, `median_household_income`, `poverty_rate`, `uninsured_rate`, `unemployment_rate`, `median_age`, `svi_themes` (JSONB), `places_measures` (JSONB), `sdoh_index`
- Database size: ~800 MB to 1.2 GB (geometry + JSONB + indexes)

### Verification after Phase 1

```bash
# Connect to Railway DB and check counts
python -c "
from sqlalchemy import create_engine, text
from geohealth.config import settings
engine = create_engine(settings.database_url_sync)
with engine.connect() as conn:
    total = conn.execute(text('SELECT COUNT(*) FROM tract_profiles')).scalar()
    states = conn.execute(text('SELECT COUNT(DISTINCT state_fips) FROM tract_profiles')).scalar()
    with_geom = conn.execute(text('SELECT COUNT(*) FROM tract_profiles WHERE geom IS NOT NULL')).scalar()
    with_places = conn.execute(text('SELECT COUNT(*) FROM tract_profiles WHERE places_measures IS NOT NULL')).scalar()
    with_svi = conn.execute(text('SELECT COUNT(*) FROM tract_profiles WHERE svi_themes IS NOT NULL')).scalar()
    print(f'Total tracts: {total}')
    print(f'States loaded: {states}')
    print(f'With geometry: {with_geom}')
    print(f'With PLACES: {with_places}')
    print(f'With SVI: {with_svi}')
"
```

**Expected**: ~74,000 tracts, 51 states, all with geometry, most with PLACES and SVI.

---

## Phase 2: Historical Trends (Multi-Year ACS)

Loads ACS snapshots for 2018-2022 into the `trends` JSONB column. Enables the frontend's trend charts.

```bash
python -m geohealth.etl.load_trends --state all --start-year 2018 --end-year 2022
```

### Details

- **API calls**: 2 calls/year x 5 years x 51 states = 510 Census API calls
- **Rate limit**: With API key, 50 req/sec — no issue
- **Runtime**: ~30-45 minutes (mostly waiting on Census API)
- **Storage**: Adds ~2-3 KB per tract in `trends` JSONB column
- **Safe to skip initially** — the app works without trend data, it just won't show historical charts

### Verification

```bash
python -c "
from sqlalchemy import create_engine, text
from geohealth.config import settings
engine = create_engine(settings.database_url_sync)
with engine.connect() as conn:
    with_trends = conn.execute(text('SELECT COUNT(*) FROM tract_profiles WHERE trends IS NOT NULL')).scalar()
    print(f'Tracts with trend data: {with_trends}')
"
```

---

## Phase 3: EPA Environmental Data

Loads EPA EJScreen environmental indicators into the `epa_data` JSONB column.

```bash
python -m geohealth.etl.load_epa --state all
```

### Details

- **Primary source**: CDC-hosted Socrata API (`data.cdc.gov`)
- **Fallback**: If API is unavailable for a state, generates estimated values from poverty/SVI data (marked `_source: "estimated"`)
- **API calls**: 1-5 per state (paginated at 50K)
- **Runtime**: ~15-30 minutes
- **Storage**: Adds ~1 KB per tract in `epa_data` JSONB column

### Verification

```bash
python -c "
from sqlalchemy import create_engine, text
from geohealth.config import settings
engine = create_engine(settings.database_url_sync)
with engine.connect() as conn:
    with_epa = conn.execute(text('SELECT COUNT(*) FROM tract_profiles WHERE epa_data IS NOT NULL')).scalar()
    estimated = conn.execute(text(\"SELECT COUNT(*) FROM tract_profiles WHERE epa_data->>'_source' = 'estimated'\")).scalar()
    api = conn.execute(text(\"SELECT COUNT(*) FROM tract_profiles WHERE epa_data->>'_source' = 'ejscreen_api'\")).scalar()
    print(f'Tracts with EPA data: {with_epa}')
    print(f'  From API: {api}')
    print(f'  Estimated: {estimated}')
"
```

---

## Execution Order

Run phases sequentially. Each phase depends on the previous:

```
Phase 1 (required)  →  Phase 2 (optional)  →  Phase 3 (optional)
  load_all               load_trends             load_epa
  ~60-90 min             ~30-45 min              ~15-30 min
```

Phase 2 and Phase 3 are independent of each other but both require Phase 1 to complete first (they update existing rows created by Phase 1).

---

## Error Handling

- **Single state failure**: Pipeline continues. Re-run with `--state <fips>` for failed states.
- **Census API 429**: Built-in retry with exponential backoff (3 retries, 2^attempt seconds)
- **SVI download failure**: SVI step skipped for all states (other steps still run). Re-run `load_svi` standalone later.
- **PLACES API timeout**: 120s timeout per request. If Socrata is slow, individual states may fail. Re-run them.
- **Network interruption**: Use `--resume` to restart. TIGER won't re-download for completed states. ACS/SVI/PLACES upsert safely.

### Re-running failed states

```bash
# Example: re-run just California (06) and Texas (48)
python -m geohealth.etl.load_all --state 06,48
python -m geohealth.etl.load_trends --state 06,48
python -m geohealth.etl.load_epa --state 06,48
```

---

## States to Load (47 new + 4 existing)

Already loaded (will upsert ACS/SVI/PLACES, skip TIGER with --resume):
- 13 (GA), 20 (KS), 27 (MN), 29 (MO)

New states (full TIGER + ACS + SVI + PLACES + SDOH):
- 01 (AL), 02 (AK), 04 (AZ), 05 (AR), 06 (CA), 08 (CO), 09 (CT), 10 (DE), 11 (DC)
- 12 (FL), 15 (HI), 16 (ID), 17 (IL), 18 (IN), 19 (IA), 21 (KY), 22 (LA), 23 (ME)
- 24 (MD), 25 (MA), 26 (MI), 28 (MS), 30 (MT), 31 (NE), 32 (NV), 33 (NH)
- 34 (NJ), 35 (NM), 36 (NY), 37 (NC), 38 (ND), 39 (OH), 40 (OK), 41 (OR), 42 (PA)
- 44 (RI), 45 (SC), 46 (SD), 47 (TN), 48 (TX), 49 (UT), 50 (VT), 51 (VA)
- 53 (WA), 54 (WV), 55 (WI), 56 (WY)

**Excluded** (territories — no `--state all` filtering needed, just skip FIPS 60/66/69/72/78):
The `ALL_STATE_FIPS` list in `utils.py` includes territories. To load only 50 states + DC, pass explicit FIPS codes instead of `all`.

### Command to load exactly 50 states + DC (excluding territories)

```bash
python -m geohealth.etl.load_all --resume --state 01,02,04,05,06,08,09,10,11,12,13,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,44,45,46,47,48,49,50,51,53,54,55,56
```

Same for Phase 2 and 3 — replace `--state all` with the explicit list above.

---

## Post-ETL Checklist

After all phases complete:

1. **Verify tract counts** using the verification scripts above
2. **Spot-check the API** — hit a few endpoints for newly loaded states:
   ```
   curl "https://geohealth-api-production.up.railway.app/v1/context?address=123+Main+St,+Denver,+CO"
   curl "https://geohealth-api-production.up.railway.app/v1/context?address=456+Oak+Ave,+Seattle,+WA"
   ```
3. **Check Railway DB storage** — dashboard → postgis service → Metrics. Should be ~1-1.5 GB.
4. **Run existing tests** — `pytest` (tests use mocks, should still pass regardless of DB state)
5. **Verify frontend** — search an address in a newly loaded state on https://geohealth-api.vercel.app
6. **No deployment needed** — the API is already live and reads from the same DB. New states are immediately queryable.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Census API rate limiting | Low (with API key) | Delays | Built-in retry + backoff |
| TIGER download server slow | Medium | Adds 1-2 hrs | `--resume` to restart |
| PLACES API pagination timeout | Low | Single state skipped | Re-run failed state |
| SVI national download fails | Low | SVI skipped for all | Re-run `load_svi` standalone |
| Railway DB storage limit | Low | ETL fails | Check plan; upgrade if needed |
| Network interruption | Medium | Partial load | `--resume` flag handles this |
| Census API returns no data for a state | Very Low | Empty metrics | Check ACS year availability |

---

## Estimated Total Runtime

| Phase | Duration | API Calls |
|-------|----------|-----------|
| Phase 1: Core ETL | 60-90 min | ~150 (TIGER) + ~102 (ACS) + 1 (SVI) + ~200 (PLACES) |
| Phase 2: Trends | 30-45 min | ~510 (ACS historical) |
| Phase 3: EPA | 15-30 min | ~100 (EJScreen) |
| **Total** | **~2-3 hours** | **~1,063 API calls** |

---

## What Changes After This

- **Frontend**: Immediately works for all 50 states. No code changes needed. Users can search any US address.
- **DPC Market Fit API**: Still only has 4 states of provider data. Separate effort to expand (not part of this plan).
- **Database**: Grows from ~100 MB to ~1-1.5 GB. Well within Railway limits.
- **API performance**: Spatial queries remain fast — PostGIS GIST index scales to 74K tracts without issue.
- **Cache**: LRU cache (4,096 entries) will still be effective for repeated lookups.
