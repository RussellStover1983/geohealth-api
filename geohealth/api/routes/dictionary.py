"""Data dictionary endpoint — field definitions with clinical context."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from geohealth.api.auth import require_api_key
from geohealth.api.schemas import (
    DictionaryCategory,
    DictionaryResponse,
    ErrorResponse,
    FieldDefinition,
)
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["dictionary"])

# ---------------------------------------------------------------------------
# Static field definitions — the canonical data dictionary
# ---------------------------------------------------------------------------

_DEMOGRAPHICS_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="total_population",
        type="int",
        source="ACS",
        category="demographics",
        description="American Community Survey total population estimate for the census tract.",
        clinical_relevance=(
            "Establishes the denominator for all rate-based metrics. Small populations "
            "(under 1,000) produce less reliable rate estimates. Large populations may "
            "mask within-tract disparities."
        ),
        unit="persons",
        typical_range="500-15000",
        example_value=4521,
    ),
    FieldDefinition(
        name="median_household_income",
        type="float",
        source="ACS",
        category="demographics",
        description="ACS median household income in dollars for the census tract.",
        clinical_relevance=(
            "Strong predictor of healthcare access and health outcomes. Incomes below "
            "$30,000 correlate with higher rates of chronic disease, delayed care-seeking, "
            "and medication non-adherence. Consider screening for financial barriers to "
            "treatment and medication affordability."
        ),
        unit="dollars",
        typical_range="15000-150000",
        example_value=72500.0,
    ),
    FieldDefinition(
        name="poverty_rate",
        type="float",
        source="ACS",
        category="demographics",
        description=(
            "Percentage of population below the federal poverty level (ACS estimate)."
        ),
        clinical_relevance=(
            "Rates above 20% indicate a high-poverty area and are the strongest single "
            "predictor of poor health outcomes. Associated with increased chronic disease "
            "burden, limited healthcare access, and reduced life expectancy. Screen for "
            "food insecurity, medication affordability, and transportation barriers."
        ),
        unit="%",
        typical_range="0-60",
        example_value=11.3,
    ),
    FieldDefinition(
        name="uninsured_rate",
        type="float",
        source="ACS",
        category="demographics",
        description="Percentage of population without health insurance (ACS estimate).",
        clinical_relevance=(
            "Directly impacts healthcare utilization and preventive care. Rates above "
            "15% suggest significant access barriers. Uninsured individuals are more "
            "likely to delay care, skip medications, and present with advanced disease. "
            "Consider connecting patients to coverage programs and community health centers."
        ),
        unit="%",
        typical_range="0-35",
        example_value=5.8,
    ),
    FieldDefinition(
        name="unemployment_rate",
        type="float",
        source="ACS",
        category="demographics",
        description="Percentage of civilian labor force that is unemployed (ACS estimate).",
        clinical_relevance=(
            "Unemployment is associated with depression, anxiety, substance use, and "
            "loss of employer-sponsored insurance. Rates above 10% indicate economic "
            "distress. Consider behavioral health screening and referrals to workforce "
            "development programs."
        ),
        unit="%",
        typical_range="0-25",
        example_value=4.2,
    ),
    FieldDefinition(
        name="median_age",
        type="float",
        source="ACS",
        category="demographics",
        description="Median age of the population in the census tract (ACS estimate).",
        clinical_relevance=(
            "Indicates the age distribution of the community. Tracts with median age "
            "above 45 may have higher chronic disease prevalence and greater need for "
            "geriatric services. Tracts below 25 may indicate student populations or "
            "young families with pediatric care needs."
        ),
        unit="years",
        typical_range="18-65",
        example_value=34.7,
    ),
]

_VULNERABILITY_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="svi_themes.socioeconomic_status",
        type="float",
        source="SVI",
        category="vulnerability",
        description=(
            "CDC/ATSDR SVI Theme 1 percentile: socioeconomic status. Combines "
            "below-poverty, unemployed, housing cost burden, no high school diploma, "
            "and no health insurance."
        ),
        clinical_relevance=(
            "Percentiles above 0.75 indicate high socioeconomic vulnerability. These "
            "communities face compounding barriers — poverty, low education, and lack of "
            "insurance — that drive worse health outcomes across virtually all conditions. "
            "Prioritize social needs screening and care navigation."
        ),
        unit="percentile (0-1)",
        typical_range="0.0-1.0",
        example_value=0.35,
    ),
    FieldDefinition(
        name="svi_themes.household_disability",
        type="float",
        source="SVI",
        category="vulnerability",
        description=(
            "CDC/ATSDR SVI Theme 2 percentile: household composition and disability. "
            "Combines aged 65+, aged 17 and younger, civilian with a disability, and "
            "single-parent households."
        ),
        clinical_relevance=(
            "High percentiles indicate populations with greater care dependency — "
            "elderly residents, children, disabled individuals, and single-parent "
            "households. These groups may need home health services, accessible "
            "facilities, and caregiver support programs."
        ),
        unit="percentile (0-1)",
        typical_range="0.0-1.0",
        example_value=0.42,
    ),
    FieldDefinition(
        name="svi_themes.minority_status",
        type="float",
        source="SVI",
        category="vulnerability",
        description=(
            "CDC/ATSDR SVI Theme 3 percentile: minority status and language. "
            "Combines minority race/ethnicity and speaks English 'less than well'."
        ),
        clinical_relevance=(
            "High percentiles indicate racial/ethnic diversity and potential language "
            "barriers. Consider culturally competent care, interpreter services, and "
            "awareness of health disparities affecting specific racial/ethnic groups "
            "(e.g., higher diabetes prevalence in Black and Hispanic populations)."
        ),
        unit="percentile (0-1)",
        typical_range="0.0-1.0",
        example_value=0.61,
    ),
    FieldDefinition(
        name="svi_themes.housing_transportation",
        type="float",
        source="SVI",
        category="vulnerability",
        description=(
            "CDC/ATSDR SVI Theme 4 percentile: housing type and transportation. "
            "Combines multi-unit structures, mobile homes, crowding, no vehicle, "
            "and group quarters."
        ),
        clinical_relevance=(
            "High percentiles indicate housing instability and transportation barriers. "
            "Patients may miss appointments due to lack of transportation, live in "
            "crowded conditions promoting infectious disease, or face housing-related "
            "health hazards. Screen for transportation needs and housing stability."
        ),
        unit="percentile (0-1)",
        typical_range="0.0-1.0",
        example_value=0.28,
    ),
    FieldDefinition(
        name="svi_themes.overall",
        type="float",
        source="SVI",
        category="vulnerability",
        description=(
            "CDC/ATSDR SVI overall composite percentile ranking across all four "
            "themes."
        ),
        clinical_relevance=(
            "The single best summary of community vulnerability. Percentiles above "
            "0.75 represent the most vulnerable 25% of census tracts nationally. "
            "Use as a quick triage metric — high-SVI tracts warrant more intensive "
            "social needs assessment and care coordination."
        ),
        unit="percentile (0-1)",
        typical_range="0.0-1.0",
        example_value=0.44,
    ),
]

_HEALTH_OUTCOME_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="places_measures.diabetes",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of diagnosed diabetes among adults aged 18+.",
        clinical_relevance=(
            "Prevalence above 12% indicates a high-burden area. Diabetes drives "
            "cardiovascular disease, kidney disease, and amputations. High-prevalence "
            "tracts may benefit from community-based diabetes prevention and management "
            "programs, A1c screening, and nutrition counseling."
        ),
        unit="%",
        typical_range="5-25",
        example_value=9.1,
    ),
    FieldDefinition(
        name="places_measures.obesity",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of obesity (BMI >= 30) among adults aged 18+.",
        clinical_relevance=(
            "Prevalence above 35% indicates a high-obesity area. Obesity is a risk "
            "factor for diabetes, cardiovascular disease, certain cancers, and "
            "musculoskeletal disorders. Consider food environment assessment and "
            "referrals to weight management programs."
        ),
        unit="%",
        typical_range="15-50",
        example_value=28.4,
    ),
    FieldDefinition(
        name="places_measures.mental_health",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of frequent mental health distress (14+ days in "
            "past 30) among adults aged 18+."
        ),
        clinical_relevance=(
            "Prevalence above 16% signals significant community mental health burden. "
            "Correlates with substance use, suicide risk, and reduced workforce "
            "participation. Screen for depression and anxiety; assess behavioral "
            "health service availability in the area."
        ),
        unit="%",
        typical_range="8-25",
        example_value=14.7,
    ),
    FieldDefinition(
        name="places_measures.physical_health",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of frequent physical health distress (14+ days in "
            "past 30) among adults aged 18+."
        ),
        clinical_relevance=(
            "High rates indicate significant chronic pain and disability burden. "
            "Often co-occurs with mental health distress and substance use. "
            "Consider integrated pain management and physical therapy referrals."
        ),
        unit="%",
        typical_range="5-20",
        example_value=11.2,
    ),
    FieldDefinition(
        name="places_measures.high_blood_pressure",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of high blood pressure among adults aged 18+."
        ),
        clinical_relevance=(
            "Hypertension is the leading modifiable risk factor for cardiovascular "
            "disease and stroke. Prevalence above 35% warrants community-level "
            "blood pressure screening programs and medication adherence support."
        ),
        unit="%",
        typical_range="20-50",
        example_value=29.8,
    ),
    FieldDefinition(
        name="places_measures.asthma",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of current asthma among adults aged 18+.",
        clinical_relevance=(
            "Rates above 10% may indicate environmental triggers (air quality, "
            "housing conditions). Assess environmental exposures, access to inhalers, "
            "and asthma action plan adherence."
        ),
        unit="%",
        typical_range="5-15",
        example_value=9.4,
    ),
    FieldDefinition(
        name="places_measures.coronary_heart_disease",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of coronary heart disease among adults aged 18+.",
        clinical_relevance=(
            "CHD prevalence above 7% indicates elevated cardiovascular risk. "
            "Correlates with poverty, smoking, diabetes, and hypertension. "
            "Prioritize cardiac risk factor management and emergency response access."
        ),
        unit="%",
        typical_range="2-12",
        example_value=5.7,
    ),
    FieldDefinition(
        name="places_measures.smoking",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of current smoking among adults aged 18+.",
        clinical_relevance=(
            "Smoking above 20% indicates a high-burden area. Smoking is the leading "
            "preventable cause of death — drives lung cancer, COPD, and cardiovascular "
            "disease. Prioritize tobacco cessation programs and screening for "
            "smoking-related conditions."
        ),
        unit="%",
        typical_range="8-30",
        example_value=15.1,
    ),
    FieldDefinition(
        name="places_measures.lack_of_insurance",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of no health insurance among adults aged 18-64."
        ),
        clinical_relevance=(
            "Complements the ACS uninsured_rate with a PLACES behavioral estimate. "
            "High values confirm access barriers. Connect patients to marketplace "
            "enrollment, Medicaid, and safety-net providers."
        ),
        unit="%",
        typical_range="3-30",
        example_value=8.5,
    ),
    FieldDefinition(
        name="places_measures.checkup",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of routine checkup within the past year among "
            "adults aged 18+."
        ),
        clinical_relevance=(
            "Low checkup rates (below 65%) suggest underutilization of preventive "
            "care. May indicate access barriers, distrust of healthcare, or competing "
            "priorities. Promote preventive care and wellness visits."
        ),
        unit="%",
        typical_range="55-85",
        example_value=72.1,
    ),
    FieldDefinition(
        name="places_measures.dental",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of dental visit within the past year among "
            "adults aged 18+."
        ),
        clinical_relevance=(
            "Dental care access is a strong marker of overall healthcare access. "
            "Low rates (below 55%) correlate with poverty and lack of dental "
            "insurance. Oral health impacts systemic conditions including "
            "cardiovascular disease and diabetes management."
        ),
        unit="%",
        typical_range="35-80",
        example_value=61.3,
    ),
    FieldDefinition(
        name="places_measures.sleep_lt7",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of short sleep duration (less than 7 hours) among "
            "adults aged 18+."
        ),
        clinical_relevance=(
            "Short sleep above 38% indicates community-level sleep deficiency. "
            "Associated with obesity, diabetes, cardiovascular disease, depression, "
            "and impaired immune function. Screen for sleep disorders and assess "
            "shift-work prevalence in the area."
        ),
        unit="%",
        typical_range="25-50",
        example_value=35.2,
    ),
    FieldDefinition(
        name="places_measures.physical_inactivity",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description=(
            "Crude prevalence of no leisure-time physical activity among "
            "adults aged 18+."
        ),
        clinical_relevance=(
            "Inactivity above 30% is a major modifiable risk factor for chronic "
            "disease. Correlates with obesity, diabetes, and cardiovascular disease. "
            "Assess walkability, park access, and availability of community "
            "exercise programs."
        ),
        unit="%",
        typical_range="15-45",
        example_value=22.3,
    ),
    FieldDefinition(
        name="places_measures.binge_drinking",
        type="float",
        source="PLACES",
        category="health_outcomes",
        description="Crude prevalence of binge drinking among adults aged 18+.",
        clinical_relevance=(
            "Binge drinking above 20% signals elevated substance use risk. "
            "Associated with liver disease, injuries, violence, and fetal alcohol "
            "spectrum disorders. Screen with AUDIT-C and assess availability of "
            "substance use treatment services."
        ),
        unit="%",
        typical_range="10-30",
        example_value=18.6,
    ),
]

_COMPOSITE_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="sdoh_index",
        type="float",
        source="computed",
        category="composite",
        description=(
            "Composite social determinants of health index (0-1 scale). Computed "
            "from normalized poverty rate, uninsured rate, unemployment rate, and "
            "SVI overall percentile. Higher values indicate greater vulnerability."
        ),
        clinical_relevance=(
            "The single most useful triage metric for clinical risk assessment. "
            "Values above 0.6 indicate high social vulnerability — patients from "
            "these tracts are likely to face multiple compounding barriers to health. "
            "Use to prioritize social needs screening, care management enrollment, "
            "and community health worker referrals."
        ),
        unit="0-1 scale",
        typical_range="0.0-1.0",
        example_value=0.41,
    ),
]

_CATEGORIES: list[DictionaryCategory] = [
    DictionaryCategory(
        category="demographics",
        description=(
            "American Community Survey (ACS) demographic and socioeconomic "
            "indicators. Updated annually by the US Census Bureau."
        ),
        source="ACS (US Census Bureau)",
        fields=_DEMOGRAPHICS_FIELDS,
    ),
    DictionaryCategory(
        category="vulnerability",
        description=(
            "CDC/ATSDR Social Vulnerability Index (SVI) theme percentile "
            "rankings. Percentiles range from 0 (least vulnerable) to 1 (most "
            "vulnerable) relative to all US census tracts."
        ),
        source="CDC/ATSDR SVI",
        fields=_VULNERABILITY_FIELDS,
    ),
    DictionaryCategory(
        category="health_outcomes",
        description=(
            "CDC PLACES health outcome measures — model-based crude prevalence "
            "estimates at the census tract level. Derived from the Behavioral "
            "Risk Factor Surveillance System (BRFSS)."
        ),
        source="CDC PLACES",
        fields=_HEALTH_OUTCOME_FIELDS,
    ),
    DictionaryCategory(
        category="composite",
        description=(
            "Computed composite indices derived from multiple data sources to "
            "provide single-number summary metrics for clinical triage."
        ),
        source="Computed",
        fields=_COMPOSITE_FIELDS,
    ),
]

_TOTAL_FIELDS = sum(len(c.fields) for c in _CATEGORIES)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get(
    "/dictionary",
    summary="Data dictionary — field definitions with clinical context",
    description=(
        "Returns structured metadata about every data field the API provides, "
        "including data type, source, clinical relevance, and interpretation "
        "guidance. Use this to understand what the data means before querying."
    ),
    response_model=DictionaryResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_dictionary(
    response: Response,
    category: str | None = Query(
        None,
        description=(
            "Filter by category: demographics, vulnerability, "
            "health_outcomes, or composite"
        ),
    ),
    api_key: str = Depends(require_api_key),
):
    """Return field definitions grouped by category."""
    # --- rate limit ------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded", headers=rl_headers,
        )

    if category:
        filtered = [c for c in _CATEGORIES if c.category == category]
        total = sum(len(c.fields) for c in filtered)
        return DictionaryResponse(total_fields=total, categories=filtered)

    return DictionaryResponse(total_fields=_TOTAL_FIELDS, categories=_CATEGORIES)
