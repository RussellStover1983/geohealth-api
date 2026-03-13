# Data Sources & Methodology

GeoHealth SDOH Explorer aggregates federal public health, demographic, and environmental datasets to provide census-tract-level intelligence. This page documents every data source, how scores are computed, and the limitations of the analysis.

All data is sourced from U.S. government agencies and is publicly available.

---

## Data Sources

### American Community Survey (ACS) 5-Year Estimates

| Field | Value |
|-------|-------|
| **Provider** | U.S. Census Bureau |
| **Vintage** | 2018–2022 |
| **Update frequency** | Annual (5-year rolling) |
| **Geography** | Census tract |
| **URL** | [census.gov/programs-surveys/acs](https://www.census.gov/programs-surveys/acs) |

Demographic, economic, and housing data at the census tract level including income, poverty, insurance coverage, employment, and age distribution.

**Used in:** Demographics card, Affordability scoring, Demand scoring, Trends, Comparison

---

### CDC PLACES

| Field | Value |
|-------|-------|
| **Provider** | Centers for Disease Control and Prevention |
| **Full name** | Population Level Analysis and Community Estimates |
| **Vintage** | 2023 Release |
| **Update frequency** | Annual |
| **Geography** | Census tract |
| **URL** | [cdc.gov/places](https://www.cdc.gov/places/) |

Model-based estimates for 36 chronic disease measures at the census tract level, derived from the Behavioral Risk Factor Surveillance System (BRFSS). Measures include diabetes, obesity, mental health, physical health, blood pressure, asthma, heart disease, smoking, insurance, preventive care, and behavioral indicators.

**Used in:** Health Outcomes card, DPC Demand scoring

---

### CDC/ATSDR Social Vulnerability Index (SVI)

| Field | Value |
|-------|-------|
| **Provider** | CDC/Agency for Toxic Substances and Disease Registry |
| **Vintage** | 2022 |
| **Update frequency** | Biennial |
| **Geography** | Census tract |
| **URL** | [atsdr.cdc.gov/placeandhealth/svi](https://www.atsdr.cdc.gov/placeandhealth/svi/) |

Percentile-ranked index across four themes:

1. **Socioeconomic Status** — poverty, unemployment, housing cost burden, no health insurance, no high school diploma
2. **Household Characteristics** — aged 65+, aged 17 and under, disability, single-parent households, limited English
3. **Racial/Ethnic Minority Status** — minority percentage, limited English speakers
4. **Housing Type/Transportation** — multi-unit structures, mobile homes, crowding, no vehicle, group quarters

**Used in:** SVI Radar card, DPC Demand scoring

---

### EPA EJScreen

| Field | Value |
|-------|-------|
| **Provider** | U.S. Environmental Protection Agency |
| **Full name** | Environmental Justice Screening and Mapping Tool |
| **Vintage** | 2024 |
| **Update frequency** | Annual |
| **Geography** | Census tract / block group |
| **URL** | [epa.gov/ejscreen](https://www.epa.gov/ejscreen) |

Environmental and demographic indicators including PM2.5, ozone, lead paint, air toxics cancer risk, traffic proximity, and Superfund site proximity.

**Used in:** Environmental card

---

### NPPES NPI Registry

| Field | Value |
|-------|-------|
| **Provider** | Centers for Medicare & Medicaid Services (CMS) |
| **Full name** | National Plan and Provider Enumeration System |
| **Vintage** | Monthly updates |
| **Update frequency** | Monthly |
| **Geography** | Provider address (geocoded to census tract) |
| **URL** | [nppes.cms.hhs.gov](https://nppes.cms.hhs.gov/) |

Registry of all healthcare providers in the U.S. Used to identify primary care physicians (PCPs), FQHCs, urgent care centers, and rural health clinics by taxonomy code and practice location.

**Used in:** Provider overlay, DPC Supply Gap scoring, DPC Competition scoring

---

### HRSA HPSA Designations

| Field | Value |
|-------|-------|
| **Provider** | Health Resources and Services Administration |
| **Full name** | Health Professional Shortage Area Designations |
| **Vintage** | 2024 |
| **Update frequency** | Quarterly |
| **Geography** | County / service area |
| **URL** | [data.hrsa.gov/topics/health-workforce/shortage-areas](https://data.hrsa.gov/topics/health-workforce/shortage-areas) |

Federal designation identifying geographic areas, populations, or facilities with shortages of primary care, dental, or mental health providers. HPSA scores range 0–25, with higher scores indicating greater shortage.

**Used in:** DPC Supply Gap scoring

---

### Census County Business Patterns (CBP)

| Field | Value |
|-------|-------|
| **Provider** | U.S. Census Bureau |
| **Vintage** | 2022 |
| **Update frequency** | Annual |
| **Geography** | County |
| **URL** | [census.gov/programs-surveys/cbp](https://www.census.gov/programs-surveys/cbp.html) |

Annual data on business establishments, employment, and payroll by county and industry (NAICS). Used to assess employer landscape for DPC partnership potential—specifically mid-size employers (10–249 employees) and average wages.

**Used in:** DPC Employer scoring

---

### Census TIGER/Line Shapefiles

| Field | Value |
|-------|-------|
| **Provider** | U.S. Census Bureau |
| **Vintage** | 2022 |
| **Update frequency** | Annual |
| **Geography** | Census tract |
| **URL** | [census.gov/geographies/mapping-files](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) |

Geographic boundary shapefiles for census tracts, counties, and states. Used for map rendering and spatial operations.

**Used in:** Map boundaries

---

## SDOH Index

The SDOH Index (0–1) is a composite vulnerability score combining poverty rate, uninsured rate, unemployment rate, and CDC SVI percentile rankings. Higher values indicate greater social determinant burden. The index uses min-max normalization across loaded tracts with equal weighting of components.

- **Range:** 0 (least vulnerable) – 1 (most vulnerable)
- **Sources:** Census ACS, CDC/ATSDR SVI

---

## DPC Market Fit Scoring Methodology

The DPC (Direct Primary Care) Market Fit score estimates the geographic viability for Direct Primary Care practices. DPC is a membership-based primary care model where patients pay a monthly fee (typically $75–$150) for comprehensive primary care without insurance billing.

The composite score (0–100) is a weighted average of five dimensions, each scored independently using min-max normalization against national reference ranges.

### Score Categories

| Category | Score Range |
|----------|------------|
| WEAK | 0–39 |
| MODERATE | 40–59 |
| STRONG | 60–79 |
| EXCELLENT | 80–100 |

### Dimension: Demand (Weight: 25%)

Measures the need for primary care services in the area.

| Indicator | Weight | Source | Direction |
|-----------|--------|--------|-----------|
| Uninsured Rate | 25% | Census ACS | Higher = more demand |
| Chronic Disease Burden | 25% | CDC PLACES | Higher = more demand |
| Working-Age Population | 15% | Census ACS | Larger = bigger market |
| SVI Socioeconomic Theme | 15% | CDC/ATSDR SVI | Higher = more need |

!!! note
    Extremely high uninsured rates (>35%) receive a 0.8x penalty because the population may not be able to afford DPC membership.

### Dimension: Affordability (Weight: 20%)

Evaluates the population's ability to pay for DPC membership.

| Indicator | Weight | Source | Direction |
|-----------|--------|--------|-----------|
| Median Household Income | 35% | Census ACS | Higher = more ability to pay |
| DPC as % of Income | 30% | Census ACS (derived) | Lower = more affordable |
| Employment Rate | 20% | Census ACS | Higher = more stable income |
| Housing Cost Burden | 15% | Census ACS | Lower = more disposable income |

### Dimension: Supply Gap (Weight: 25%)

Identifies areas with insufficient primary care infrastructure.

| Indicator | Weight | Source | Direction |
|-----------|--------|--------|-----------|
| PCP per 100k Population | 40% | NPPES NPI | Lower = more opportunity |
| HPSA Score | 35% | HRSA HPSA | Higher = greater shortage |
| FQHC Presence | 25% | NPPES NPI | Fewer = less safety-net coverage |

### Dimension: Employer (Weight: 20%)

Assesses the local business landscape for employer-sponsored DPC partnerships.

| Indicator | Weight | Source | Direction |
|-----------|--------|--------|-----------|
| Target Establishment % | 40% | Census CBP | More mid-size = better |
| Average Annual Wage | 35% | Census CBP | Higher = can afford DPC benefit |
| Total Establishments | 25% | Census CBP | More = more prospects |

### Dimension: Competition (Weight: 10%)

Evaluates the competitive landscape.

| Indicator | Weight | Source | Direction |
|-----------|--------|--------|-----------|
| Competing Facility Count | 50% | NPPES NPI | Fewer = less competition |
| PCP Density | 50% | NPPES NPI | Lower = less saturation |

!!! note
    When data completeness is below 100%, competition scores are capped at 70 to prevent inflated "EXCELLENT" ratings from incomplete data.

---

## Health Outcomes Benchmarking

Health outcome measures from CDC PLACES are benchmarked against national averages:

- **Green (favorable):** Tract value ≤ 85% of national benchmark
- **Amber (moderate):** Tract value within 85–115% of national benchmark
- **Red (elevated):** Tract value > 115% of national benchmark

For preventive measures (routine checkups, dental visits), the comparison is inverted—higher values are better.

!!! warning
    CDC PLACES estimates are model-based using BRFSS data and should be interpreted as estimates, not direct measurements. Small-area estimates may have wider confidence intervals in low-population tracts.

---

## Limitations

- **Geographic coverage:** Currently limited to 4 states (GA, KS, MN, MO) covering 6,784 census tracts. National coverage is planned.
- **Temporal lag:** ACS 5-year estimates represent 2018–2022 averages. Rapid demographic shifts may not yet be reflected.
- **Model-based estimates:** CDC PLACES health measures are modeled from BRFSS survey data, not direct measurements.
- **DPC scoring is exploratory:** The market fit model uses heuristic weights and national reference ranges. It is intended for screening, not as a definitive business assessment.
- **Provider data currency:** NPPES data is refreshed monthly, but provider practice locations may lag behind actual moves or closures.
- **County-level employer data:** Census CBP employer data is at the county level and may not reflect within-county variation for large counties.
- **HPSA boundaries:** HRSA HPSA designations are at the county or service area level, not tract level. A tract within a non-HPSA county may still experience provider shortages.

---

## Suggested Citation

> GeoHealth SDOH Explorer. Data from U.S. Census Bureau American Community Survey, CDC PLACES, CDC/ATSDR Social Vulnerability Index, HRSA HPSA, CMS NPPES, Census County Business Patterns, and EPA EJScreen. Available at https://geohealth-api.vercel.app. Accessed [date].

When citing specific data, please also cite the original source agency (e.g., "CDC PLACES 2023 Release, based on BRFSS 2022 data. Greenlund KJ et al., Prev Chronic Dis 2022;19:210459").

---

## Source Code

- **Main API + ETL:** [github.com/RussellStover1983/geohealth-api](https://github.com/RussellStover1983/geohealth-api)
- **Scoring engine:** [`dpc-market-fit/app/services/scoring.py`](https://github.com/RussellStover1983/geohealth-api/blob/master/dpc-market-fit/app/services/scoring.py)
- **Frontend:** [`geohealth-ui/`](https://github.com/RussellStover1983/geohealth-api/tree/master/geohealth-ui)
