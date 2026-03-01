# ETL Runbook — Loading New States

## Prerequisites

- Python environment with ETL deps: `pip install -e ".[dev,etl]"`
- TCP proxy enabled on Railway PostGIS service
- Production `DATABASE_URL_SYNC` connection string

## State FIPS Codes

Find your state's FIPS code: [Census Bureau FIPS list](https://www.census.gov/library/reference/code-lists/ansi/ansi-codes-for-states.html)

Common codes: AL=01, AK=02, AZ=04, CA=06, CO=08, FL=12, GA=13, IL=17, NY=36, TX=48

## Step-by-Step Process

### 1. Load core data (TIGER + ACS + SVI + PLACES + SDOH)

```bash
DATABASE_URL_SYNC="postgresql://geohealth:<password>@<host>:<port>/geohealth" \
  python -m geohealth.etl.load_all --state <FIPS>
```

This runs 5 steps in order:
1. **TIGER** — Downloads tract boundary shapefiles from Census Bureau (~30s)
2. **ACS** — Fetches demographics from Census API (~10s)
3. **SVI** — Downloads national SVI CSV, filters to state (~20s first time, cached after)
4. **PLACES** — Fetches CDC PLACES health outcomes (~10s)
5. **SDOH** — Computes composite vulnerability index from loaded data (~5s)

**Expected output**: Alembic migration check, then silence (known logging issue). Check results via the stats endpoint.

**Typical time**: 1-3 minutes per state.

### 2. Load historical trends (2018-2022)

```bash
DATABASE_URL_SYNC="postgresql://geohealth:<password>@<host>:<port>/geohealth" \
  python -m geohealth.etl.load_trends --state <FIPS> --start-year 2018 --end-year 2022
```

Fetches 5 years of ACS data from Census Bureau API. Expect ~10 API calls (2 per year).

### 3. Load EPA environmental data

```bash
DATABASE_URL_SYNC="postgresql://geohealth:<password>@<host>:<port>/geohealth" \
  python -m geohealth.etl.load_epa --state <FIPS>
```

Tries EPA EJScreen API first. If unavailable (currently returning 404), generates estimated values from demographic correlations. Estimated data is flagged with `_source: "estimated"`.

### 4. Verify the load

Run these checks against the production API:

```bash
API_KEY="your-key"
BASE="https://geohealth-api-production.up.railway.app"
FIPS="13"  # Georgia

# 1. Check tract count
curl -s -H "X-API-Key: $API_KEY" "$BASE/v1/stats" | python -m json.tool

# 2. Context lookup with a known address in the state
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE/v1/context?address=100+Peachtree+St+NW,+Atlanta,+GA+30303"

# 3. Pick a GEOID from the context response and test trends
curl -s -H "X-API-Key: $API_KEY" "$BASE/v1/trends?geoid=<GEOID>"

# 4. Test demographics comparison
curl -s -H "X-API-Key: $API_KEY" "$BASE/v1/demographics/compare?geoid=<GEOID>"

# 5. Test nearby search with coordinates from the state
curl -s -H "X-API-Key: $API_KEY" "$BASE/v1/nearby?lat=<LAT>&lng=<LNG>&radius=3&limit=5"

# 6. Test EPA data is present in context response
curl -s -H "X-API-Key: $API_KEY" "$BASE/v1/context?lat=<LAT>&lng=<LNG>" \
  | python -c "import sys,json; print(json.load(sys.stdin)['tract'].get('epa_data',{}).get('_source','MISSING'))"
```

### Verification checklist

- [ ] Stats endpoint shows new state with expected tract count
- [ ] Context lookup resolves an address in the state to a tract
- [ ] Tract has all data layers: demographics, SVI, PLACES, SDOH, EPA
- [ ] Trends endpoint returns multi-year data (typically 3-5 years)
- [ ] Demographics compare returns percentile rankings
- [ ] Nearby search finds tracts around coordinates in the state

## Loading Multiple States

```bash
# Comma-separated FIPS codes
python -m geohealth.etl.load_all --state 06,12,36,48

# All 50 states + DC + territories (takes hours)
python -m geohealth.etl.load_all --state all --resume
```

The `--resume` flag skips TIGER for states already loaded (ACS/SVI/PLACES use upserts so they're safe to re-run).

After `load_all`, run trends and EPA for each state:
```bash
for FIPS in 06 12 36 48; do
  python -m geohealth.etl.load_trends --state $FIPS --start-year 2018 --end-year 2022
  python -m geohealth.etl.load_epa --state $FIPS
done
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| No output after Alembic lines | `ensure_table()` resets root logger | Expected — check stats endpoint to verify |
| `TypeError: unsupported operand` in EPA | Null `rpl_themes` in SVI data | Fixed in `730ce7d` — update code |
| Census API 204/500 | Rate limiting or maintenance | Wait and retry |
| `Connection refused` | TCP proxy not enabled | Enable in Railway dashboard |
| Trends show fewer years | Tract didn't exist in older Census vintages | Normal — tract boundaries change every 10 years |

## Post-Load Cleanup

- **Disable TCP proxy** on the PostGIS service when done (saves resources, reduces attack surface)
- **Update CLAUDE.md** `Data loaded` line with new state
- **Update memory** if significant
