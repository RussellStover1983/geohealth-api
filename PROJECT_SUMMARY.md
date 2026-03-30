# GeoHealth API — Project Summary

## What This Project Is

A **census-tract-level geographic health intelligence platform**. Given a street address or lat/lng coordinates, it returns a rich profile of the surrounding census tract: demographics, social vulnerability, health outcomes, environmental data, historical trends, and optionally an AI-generated narrative summary.

**Target users**: Healthcare organizations, public health researchers, community health workers, and developers building health equity tools.

---

## Live Deployments

| What | URL |
|------|-----|
| **Frontend (Vercel)** | `https://geohealth-api.vercel.app` |
| **API (Railway)** | `https://geohealth-api-production.up.railway.app` |
| **Swagger UI** | `https://geohealth-api-production.up.railway.app/docs` |
| **Documentation site** | `https://russellstover1983.github.io/geohealth-api/` |
| **PyPI package** | `pip install geohealth-api` (v0.1.1) |
| **GitHub repo** | `https://github.com/RussellStover1983/geohealth-api` |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI / PostgreSQL 16 + PostGIS 3.4 / SQLAlchemy 2.0 async |
| **Frontend** | Next.js 14 (App Router) / TypeScript / Tailwind CSS 3.4 / shadcn/ui / MapLibre GL / Recharts / Zustand |
| **AI narratives** | Anthropic Claude API |
| **Backend deployment** | Railway (Docker, Gunicorn + Uvicorn workers) |
| **Frontend deployment** | Vercel (auto-deploys from `master`) |
| **Docs** | MkDocs + Material theme → GitHub Pages |
| **CI/CD** | GitHub Actions (lint, test, Docker build, docs deploy) |

---

## Data Coverage

**All 50 US states + DC loaded** (~84,000 census tracts). Each tract has **50+ individual metrics** from 7 data sources.

---

## Data Sources — Complete Inventory

### 1. TIGER/Line Shapefiles (Census Bureau)

**What it is**: Census tract boundary geometries — the polygons that define each tract on the map.

| | |
|---|---|
| **Provider** | US Census Bureau |
| **ETL file** | `geohealth/etl/load_tiger.py` |
| **Data year** | 2022 |
| **Storage** | Fixed columns in `tract_profiles` |

**Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `geom` | PostGIS MultiPolygon | Census tract boundary geometry (SRID 4326) |
| `geoid` | String(11) | Full FIPS code (state 2 + county 3 + tract 6) |
| `state_fips` | String(2) | 2-digit state FIPS code |
| `county_fips` | String(3) | 3-digit county FIPS code |
| `tract_code` | String(6) | 6-digit tract code |
| `name` | Text | Human-readable tract name |

---

### 2. American Community Survey (ACS) 5-Year Estimates

**What it is**: Core demographic and socioeconomic indicators for every tract. The foundation layer — population, income, poverty, insurance, employment, age.

| | |
|---|---|
| **Provider** | US Census Bureau (Census API) |
| **ETL file** | `geohealth/etl/load_acs.py` |
| **Data year** | 2022 |
| **Storage** | Fixed columns in `tract_profiles` |
| **API source** | `https://api.census.gov/data/2022/acs/acs5` |

**Fields**:
| Field | Census Variable | Description |
|-------|----------------|-------------|
| `total_population` | B01003_001E | Total population estimate |
| `median_household_income` | B19013_001E | Median household income ($) |
| `median_age` | B01002_001E | Median age (years) |
| `poverty_rate` | S1701_C03_001E | % below federal poverty level |
| `uninsured_rate` | S2701_C05_001E | % without health insurance |
| `unemployment_rate` | S2301_C04_001E | % of civilian labor force unemployed |

---

### 3. CDC/ATSDR Social Vulnerability Index (SVI)

**What it is**: Percentile rankings (0–1 scale) measuring community vulnerability across four themes. Used by emergency managers and public health officials to identify communities most at risk during disasters and health crises.

| | |
|---|---|
| **Provider** | CDC/ATSDR (https://svi.cdc.gov/) |
| **ETL file** | `geohealth/etl/load_svi.py` |
| **Data year** | 2022 |
| **Storage** | JSONB column `svi_themes` |

**Fields**:
| Field | Description |
|-------|-------------|
| `rpl_theme1` | Socioeconomic status percentile (income, poverty, employment, education) |
| `rpl_theme2` | Household composition & disability percentile (age, disability, single-parent) |
| `rpl_theme3` | Minority status & language percentile (race/ethnicity, English proficiency) |
| `rpl_theme4` | Housing type & transportation percentile (multi-unit, mobile homes, crowding, no vehicle) |
| `rpl_themes` | Overall composite vulnerability percentile |

---

### 4. CDC PLACES Health Outcome Measures

**What it is**: Model-based crude prevalence estimates for chronic diseases, health behaviors, and preventive care utilization at the census tract level. The most granular health data available for US communities.

| | |
|---|---|
| **Provider** | CDC PLACES (Socrata API) |
| **ETL file** | `geohealth/etl/load_places.py` |
| **Data year** | 2023 |
| **Storage** | JSONB column `places_measures` |
| **API source** | `https://data.cdc.gov/resource/cwsq-ngmh.json` |

**Fields** (all values are % of adults 18+):
| Field | Description |
|-------|-------------|
| `diabetes` | Diagnosed diabetes prevalence |
| `obesity` | Obesity (BMI ≥ 30) prevalence |
| `mhlth` | Frequent mental health distress (14+ days/month) |
| `phlth` | Frequent physical health distress (14+ days/month) |
| `bphigh` | High blood pressure prevalence |
| `casthma` | Current asthma prevalence |
| `chd` | Coronary heart disease prevalence |
| `csmoking` | Current smoking prevalence |
| `access2` | No health insurance (ages 18–64) |
| `checkup` | Routine checkup within past year |
| `dental` | Dental visit within past year |
| `sleep` | Short sleep duration (< 7 hours) |
| `lpa` | No leisure-time physical activity |
| `binge` | Binge drinking prevalence |

---

### 5. EPA EJScreen Environmental Data

**What it is**: Environmental justice screening indicators measuring pollution exposure, proximity to hazardous facilities, and environmental health risks.

| | |
|---|---|
| **Provider** | EPA EJScreen |
| **ETL file** | `geohealth/etl/load_epa.py` |
| **Data year** | 2023 (EJScreen v2.22) |
| **Storage** | JSONB column `epa_data` |
| **Fallback** | If EPA API unavailable, generates estimated values correlated with SVI/poverty data |

**Fields**:
| Field | Unit | Description |
|-------|------|-------------|
| `pm25` | μg/m³ | Fine particulate matter (PM2.5) |
| `ozone` | ppb | Ground-level ozone |
| `diesel_pm` | μg/m³ | Diesel particulate matter |
| `air_toxics_cancer_risk` | per million | Cancer risk from air toxics |
| `respiratory_hazard_index` | ratio | Respiratory hazard index |
| `traffic_proximity` | vehicles/day/distance | Traffic proximity and volume |
| `lead_paint_pct` | % | Pre-1960 housing (lead paint indicator) |
| `superfund_proximity` | count/distance | Proximity to Superfund sites |
| `rmp_proximity` | count/distance | Proximity to Risk Management Plan facilities |
| `hazardous_waste_proximity` | count/distance | Proximity to hazardous waste facilities |
| `wastewater_discharge` | toxicity-weighted | Wastewater discharge indicator |
| `_source` | string | `"ejscreen_api"` or `"estimated"` |

---

### 6. Multi-Year ACS Trend Data

**What it is**: Historical snapshots of the same ACS metrics across 5 years, enabling trend analysis and change detection.

| | |
|---|---|
| **Provider** | US Census Bureau (Census API) — same source as primary ACS |
| **ETL file** | `geohealth/etl/load_trends.py` |
| **Data years** | 2018–2022 |
| **Storage** | JSONB column `trends` |

**Structure**: Year-keyed nested dict:
```json
{
  "2018": {"poverty_rate": 20.1, "median_household_income": 45000, ...},
  "2019": {"poverty_rate": 18.5, ...},
  ...
  "2022": {"poverty_rate": 15.2, ...}
}
```

**Metrics per year**: `total_population`, `median_household_income`, `median_age`, `poverty_rate`, `uninsured_rate`, `unemployment_rate`

The `/v1/trends` endpoint also computes absolute change and percent change between earliest and latest data points.

---

### 7. Composite SDOH Index (Computed)

**What it is**: A derived 0–1 composite vulnerability score combining ACS and SVI data. Higher values indicate greater social determinant burden. Useful for clinical triage and quick-glance vulnerability assessment.

| | |
|---|---|
| **Provider** | Computed internally (no external data source) |
| **ETL file** | `geohealth/etl/compute_sdoh_index.py` |
| **Storage** | Fixed column `sdoh_index` |
| **Dependencies** | Requires ACS + SVI to be loaded first |

**Formula**:
1. Min-max normalize: `poverty_rate`, `uninsured_rate`, `unemployment_rate`
2. Extract SVI overall percentile: `rpl_themes` (already 0–1)
3. Average the four normalized components (handles missing values)

---

## Data Source Summary

| Source | Provider | ETL File | Storage | Metrics | Year |
|--------|----------|----------|---------|---------|------|
| TIGER Shapefiles | Census Bureau | load_tiger.py | Fixed cols | 6 (geometry + identifiers) | 2022 |
| ACS Demographics | Census Bureau | load_acs.py | Fixed cols | 6 | 2022 |
| SVI Vulnerability | CDC/ATSDR | load_svi.py | JSONB `svi_themes` | 5 | 2022 |
| PLACES Health | CDC | load_places.py | JSONB `places_measures` | 14 | 2023 |
| EPA EJScreen | EPA | load_epa.py | JSONB `epa_data` | 11 (+source flag) | 2023 |
| ACS Trends | Census Bureau | load_trends.py | JSONB `trends` | 6 × 5 years | 2018–2022 |
| SDOH Index | Computed | compute_sdoh_index.py | Fixed col | 1 | Derived |

**Total**: 7 data sources, 50+ unique metrics per tract

---

## Frontend (`geohealth-ui/`)

Interactive SDOH explorer deployed on Vercel. Key features:

- **Choropleth map** — 35+ metric layers, auto-loads tract polygons by visible state
- **Address autocomplete** — Nominatim-backed with 300ms debounce, keyboard navigation
- **Tract detail panel** — click any tract to see demographics, SVI radar, health outcomes, EPA data
- **Layer switcher** — toggle between any available metric for choropleth coloring
- **Trend sparklines** — inline 2018–2022 trend visualization
- **AI narrative** — Claude-generated plain-English summary per tract

---

## API Endpoints

### Public (no auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DB connectivity + uptime stats |
| GET | `/metrics` | Request counters, latency percentiles, cache stats |
| GET | `/llms.txt` | Agent-readable API overview |
| GET | `/llms-full.txt` | Full agent reference with clinical context |

### Authenticated (`X-API-Key` header)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/context` | Primary lookup — address or lat/lng → full tract profile + optional narrative |
| POST | `/v1/batch` | Multi-address lookup (up to 50) |
| GET | `/v1/nearby` | Spatial radius search — tracts within N miles |
| GET | `/v1/compare` | Compare two tracts or tract vs county/state/national |
| GET | `/v1/trends` | Historical trend data with change metrics |
| GET | `/v1/demographics/compare` | Tract vs county/state/national with percentile rankings |
| GET | `/v1/stats` | Per-state tract counts |
| GET | `/v1/dictionary` | Field definitions with clinical context |
| POST | `/v1/webhooks` | Create webhook subscription |
| GET | `/v1/webhooks` | List webhook subscriptions |
| GET | `/v1/webhooks/{id}` | Get webhook details |
| DELETE | `/v1/webhooks/{id}` | Delete webhook |

---

## Adding New Data Sources

The JSONB column pattern makes it straightforward:

1. **New data source** (e.g., HRSA HPSA data) → add a JSONB column via `alembic revision --autogenerate`, write an ETL loader
2. **New metric within existing source** (e.g., adding `stroke` to `places_measures`) → update the ETL loader only, no migration needed
3. **New computed index** (e.g., environmental vulnerability score) → one migration for the fixed column + a compute script

The `TractDataModel` has `extra = "allow"` so new JSONB fields flow through the API automatically without schema changes.
