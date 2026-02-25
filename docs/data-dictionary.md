# Data Dictionary

Every census tract profile includes **26 fields** across four categories. This page provides clinical thresholds and interpretation guidance for each field.

!!! tip "Quick triage"
    If you only have time to check one number, look at **`sdoh_index`**. Values above **0.6** indicate high social vulnerability — patients from these tracts are likely to face multiple compounding barriers to health.

---

## Demographics (American Community Survey)

Source: **US Census Bureau, American Community Survey (ACS)**. Updated annually.

| Field | Type | Unit | Typical Range | Clinical Threshold | Interpretation |
|-------|------|------|---------------|-------------------|----------------|
| `total_population` | int | persons | 500–15,000 | <1,000 = unreliable rates | Denominator for all rate metrics. Small populations produce less reliable estimates. |
| `median_household_income` | float | dollars | $15,000–$150,000 | <$30,000 = high risk | Predicts healthcare access and outcomes. Low incomes correlate with chronic disease, delayed care-seeking, and medication non-adherence. |
| `poverty_rate` | float | % | 0–60% | **>20% = high-poverty** | Strongest single predictor of poor health outcomes. Associated with increased chronic disease, limited healthcare access, and reduced life expectancy. Screen for food insecurity, medication affordability, and transportation barriers. |
| `uninsured_rate` | float | % | 0–35% | >15% = access barriers | Directly impacts healthcare utilization and preventive care. Uninsured individuals are more likely to delay care, skip medications, and present with advanced disease. |
| `unemployment_rate` | float | % | 0–25% | >10% = economic distress | Associated with depression, anxiety, substance use, and loss of employer-sponsored insurance. Consider behavioral health screening. |
| `median_age` | float | years | 18–65 | >45 = chronic disease risk | Tracts above 45 may have higher chronic disease prevalence. Tracts below 25 may indicate student populations or young families with pediatric needs. |

---

## Vulnerability (CDC/ATSDR Social Vulnerability Index)

Source: **CDC/ATSDR Social Vulnerability Index (SVI)**. All values are **national percentiles (0–1)**. Higher = more vulnerable.

!!! warning "Clinical rule of thumb"
    SVI percentile above **0.75** = top 25% most vulnerable nationally. These communities need intensive social needs screening and care coordination.

| Field | What It Measures | Interpretation |
|-------|-----------------|----------------|
| `svi_themes.rpl_theme1` | **Socioeconomic status**: poverty, unemployment, no insurance, no high school diploma, housing cost burden | Percentiles above 0.75 indicate compounding barriers — poverty, low education, and lack of insurance — that drive worse outcomes across virtually all conditions. |
| `svi_themes.rpl_theme2` | **Household composition & disability**: aged 65+, under 17, civilian with disability, single-parent households | High percentiles indicate populations with greater care dependency. May need home health services, accessible facilities, and caregiver support. |
| `svi_themes.rpl_theme3` | **Minority status & language**: racial/ethnic minorities, limited English proficiency | Consider culturally competent care, interpreter services, and awareness of health disparities affecting specific racial/ethnic groups. |
| `svi_themes.rpl_theme4` | **Housing type & transportation**: multi-unit/mobile homes, crowding, no vehicle, group quarters | Patients may miss appointments due to lack of transportation, live in crowded conditions promoting infectious disease, or face housing-related health hazards. |
| `svi_themes.rpl_themes` | **Overall composite** across all 4 themes | The single best summary of community vulnerability. Above 0.75 = most vulnerable 25% nationally. Use as a quick triage metric. |

---

## Health Outcomes (CDC PLACES)

Source: **CDC PLACES**. All values are **crude prevalence percentages** among adults 18+, derived from Behavioral Risk Factor Surveillance System (BRFSS) model-based estimates.

| Field | What It Measures | Unit | Typical Range | High-Burden Threshold |
|-------|-----------------|------|---------------|----------------------|
| `places_measures.diabetes` | Diagnosed diabetes | % | 5–25% | **>12%** |
| `places_measures.obesity` | BMI >= 30 | % | 15–50% | **>35%** |
| `places_measures.mhlth` | 14+ days mental distress/month | % | 8–25% | **>16%** |
| `places_measures.phlth` | 14+ days physical distress/month | % | 5–20% | **>15%** |
| `places_measures.bphigh` | Hypertension (high blood pressure) | % | 20–50% | **>35%** |
| `places_measures.casthma` | Current asthma | % | 5–15% | **>10%** |
| `places_measures.chd` | Coronary heart disease | % | 2–12% | **>7%** |
| `places_measures.csmoking` | Current smoking | % | 8–30% | **>20%** |
| `places_measures.access2` | No health insurance (18–64) | % | 3–30% | **>15%** |
| `places_measures.checkup` | Annual checkup | % | 55–85% | **<65%** (low = concern) |
| `places_measures.dental` | Annual dental visit | % | 35–80% | **<55%** (low = concern) |
| `places_measures.sleep` | Short sleep (<7 hours) | % | 25–50% | **>38%** |
| `places_measures.lpa` | No leisure-time physical activity | % | 15–45% | **>30%** |
| `places_measures.binge` | Binge drinking | % | 10–30% | **>20%** |

### Clinical context for key measures

!!! info "Diabetes (`places_measures.diabetes`)"
    Prevalence above 12% indicates a high-burden area. Diabetes drives cardiovascular disease, kidney disease, and amputations. High-prevalence tracts may benefit from community-based diabetes prevention programs, A1c screening, and nutrition counseling.

!!! info "Mental health distress (`places_measures.mhlth`)"
    Prevalence above 16% signals significant community mental health burden. Correlates with substance use, suicide risk, and reduced workforce participation. Screen for depression and anxiety; assess behavioral health service availability.

!!! info "Hypertension (`places_measures.bphigh`)"
    Hypertension is the leading modifiable risk factor for cardiovascular disease and stroke. Prevalence above 35% warrants community-level blood pressure screening programs and medication adherence support.

!!! info "Smoking (`places_measures.csmoking`)"
    Smoking above 20% indicates a high-burden area. Leading preventable cause of death — drives lung cancer, COPD, and cardiovascular disease. Prioritize tobacco cessation programs.

!!! info "Checkup and dental rates"
    These are **inverted** — low values are concerning. Checkup rates below 65% and dental rates below 55% suggest underutilization of preventive care, often indicating access barriers, distrust of healthcare, or competing priorities.

---

## Composite Index

| Field | Type | Scale | Interpretation |
|-------|------|-------|----------------|
| `sdoh_index` | float | 0–1 | Computed from normalized poverty rate, uninsured rate, unemployment rate, and SVI overall percentile. **Above 0.6 = high vulnerability.** The single most useful triage metric for clinical risk assessment. Use to prioritize social needs screening, care management enrollment, and community health worker referrals. |

---

## Data Sources & Methodology

| Source | Coverage | Update Frequency | Geographic Level |
|--------|----------|-----------------|-----------------|
| **American Community Survey (ACS)** | All US census tracts | Annual (5-year estimates) | Census tract |
| **CDC/ATSDR SVI** | All US census tracts | Biennial | Census tract |
| **CDC PLACES** | All US census tracts | Annual | Census tract |

**Census tract** = a statistical subdivision averaging ~4,000 people, designed to be relatively homogeneous in population characteristics, economic status, and living conditions. This is the standard geographic unit for neighborhood-level health analysis.

**SDOH index computation**: The composite `sdoh_index` normalizes poverty rate, uninsured rate, and unemployment rate to 0–1 scales, then averages them with the SVI overall percentile (`rpl_themes`). The result is a single 0–1 score where higher values indicate greater social vulnerability.

---

## Programmatic Access

All field definitions are available programmatically via the [/v1/dictionary](api-reference.md#get-v1dictionary-data-dictionary) endpoint, which returns structured JSON with type, source, clinical relevance, and example values for every field.
