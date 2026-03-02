"""DPC Market Fit scoring engine.

Phase 1: Demand + Affordability dimensions from Census ACS, CDC PLACES, CDC SVI.
Supply Gap, Employer, and Competition dimensions return placeholder scores
until Phase 2-3 data sources are integrated.
"""

from __future__ import annotations

import logging

from app.models.enums import Dimension, ScoreCategory
from app.models.response import CompositeScore, DimensionScore
from app.services.census_acs import ACSData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.utils.normalization import clamp_score, min_max_score, weighted_average

logger = logging.getLogger(__name__)

# --- Default dimension weights (Phase 1: only demand + affordability active) ---
DEFAULT_WEIGHTS = {
    Dimension.DEMAND: 0.25,
    Dimension.SUPPLY_GAP: 0.25,
    Dimension.AFFORDABILITY: 0.20,
    Dimension.EMPLOYER: 0.20,
    Dimension.COMPETITION: 0.10,
}

# --- National reference ranges for min-max normalization ---
# These approximate the range across US census tracts.
# In production, these would be computed from actual distributions.
_NATIONAL_REFS = {
    "uninsured_rate": (2.0, 40.0),           # % uninsured
    "chronic_disease_burden": (5.0, 35.0),    # avg prevalence %
    "working_age_pop": (500, 10000),          # count
    "svi_socioeconomic": (0.0, 1.0),         # percentile 0-1
    "median_income": (15000, 150000),         # dollars
    "dpc_pct_income": (0.5, 10.0),           # %
    "employment_rate": (60.0, 99.0),         # %
    "housing_burden": (10.0, 70.0),          # %
}


def score_demand(
    acs: ACSData | None,
    places: PLACESData | None,
    svi: SVIData | None,
) -> DimensionScore:
    """Score the Demand dimension (0-100).

    Higher uninsured rates, chronic disease burden, and SVI = higher demand.
    """
    indicators: list[tuple[float, float]] = []
    completeness_parts = 0
    completeness_total = 4  # uninsured, chronic, working_age, svi

    # Uninsured rate (weight: 0.25) — higher = more demand
    if acs and acs.uninsured_rate is not None:
        score = min_max_score(
            acs.uninsured_rate, *_NATIONAL_REFS["uninsured_rate"]
        )
        # Cap extremely high uninsured (>40%) — population can't afford DPC
        if acs.uninsured_rate > 35:
            score = score * 0.8  # penalty
        indicators.append((score, 0.25))
        completeness_parts += 1

    # Chronic disease burden (weight: 0.25) — higher = more utilization need
    if places and places.chronic_disease_burden is not None:
        score = min_max_score(
            places.chronic_disease_burden, *_NATIONAL_REFS["chronic_disease_burden"]
        )
        indicators.append((score, 0.25))
        completeness_parts += 1

    # Working-age population (weight: 0.15) — larger = bigger market
    if acs and acs.working_age_population is not None:
        score = min_max_score(
            acs.working_age_population, *_NATIONAL_REFS["working_age_pop"]
        )
        indicators.append((score, 0.15))
        completeness_parts += 1

    # SVI socioeconomic theme (weight: 0.15) — higher = more need
    if svi and svi.socioeconomic is not None:
        score = min_max_score(
            svi.socioeconomic, *_NATIONAL_REFS["svi_socioeconomic"]
        )
        indicators.append((score, 0.15))
        completeness_parts += 1

    # ED ACSC rate (weight: 0.20) — Phase 2, placeholder
    # Not available until CMS data integration

    if not indicators:
        return DimensionScore(
            score=0.0,
            category=ScoreCategory.WEAK,
            summary="Insufficient data for demand scoring.",
            data_completeness=0.0,
        )

    final = clamp_score(weighted_average(indicators))
    completeness = completeness_parts / completeness_total

    summary = _demand_summary(acs, places, final)

    return DimensionScore(
        score=final,
        category=ScoreCategory.from_score(final),
        summary=summary,
        data_completeness=round(completeness, 2),
    )


def score_affordability(acs: ACSData | None) -> DimensionScore:
    """Score the Affordability dimension (0-100).

    Higher income, lower housing burden, higher employment = higher score.
    """
    indicators: list[tuple[float, float]] = []
    completeness_parts = 0
    completeness_total = 4

    # Median household income (weight: 0.35) — higher = more ability to pay
    if acs and acs.median_household_income is not None:
        score = min_max_score(
            acs.median_household_income, *_NATIONAL_REFS["median_income"]
        )
        indicators.append((score, 0.35))
        completeness_parts += 1

    # DPC as % of income (weight: 0.30) — lower % = higher score (inverted)
    if acs and acs.dpc_as_pct_of_income is not None:
        score = min_max_score(
            acs.dpc_as_pct_of_income, *_NATIONAL_REFS["dpc_pct_income"],
            invert=True,
        )
        indicators.append((score, 0.30))
        completeness_parts += 1

    # Employment rate (weight: 0.20) — higher = more stable income
    if acs and acs.employment_rate is not None:
        score = min_max_score(
            acs.employment_rate, *_NATIONAL_REFS["employment_rate"]
        )
        indicators.append((score, 0.20))
        completeness_parts += 1

    # Housing cost burden (weight: 0.15) — lower burden = higher score (inverted)
    if acs and acs.housing_cost_burden_rate is not None:
        score = min_max_score(
            acs.housing_cost_burden_rate, *_NATIONAL_REFS["housing_burden"],
            invert=True,
        )
        indicators.append((score, 0.15))
        completeness_parts += 1

    if not indicators:
        return DimensionScore(
            score=0.0,
            category=ScoreCategory.WEAK,
            summary="Insufficient data for affordability scoring.",
            data_completeness=0.0,
        )

    final = clamp_score(weighted_average(indicators))
    completeness = completeness_parts / completeness_total

    summary = _affordability_summary(acs, final)

    return DimensionScore(
        score=final,
        category=ScoreCategory.from_score(final),
        summary=summary,
        data_completeness=round(completeness, 2),
    )


def score_supply_gap() -> DimensionScore:
    """Placeholder for Supply Gap dimension (Phase 2)."""
    return DimensionScore(
        score=50.0,
        category=ScoreCategory.MODERATE,
        summary="Supply gap analysis requires NPI and HRSA data (Phase 2).",
        data_completeness=0.0,
    )


def score_employer() -> DimensionScore:
    """Placeholder for Employer Opportunity dimension (Phase 3)."""
    return DimensionScore(
        score=50.0,
        category=ScoreCategory.MODERATE,
        summary="Employer analysis requires County Business Patterns data (Phase 3).",
        data_completeness=0.0,
    )


def score_competition() -> DimensionScore:
    """Placeholder for Competition dimension (Phase 3)."""
    return DimensionScore(
        score=50.0,
        category=ScoreCategory.MODERATE,
        summary="Competition analysis requires DPC registry data (Phase 3).",
        data_completeness=0.0,
    )


def compute_composite(
    dimension_scores: dict[str, DimensionScore],
    weights: dict[str, float] | None = None,
) -> CompositeScore:
    """Compute weighted composite score from dimension scores."""
    w = weights or {d.value: DEFAULT_WEIGHTS[d] for d in Dimension}

    pairs: list[tuple[float, float]] = []
    for dim_name, dim_score in dimension_scores.items():
        weight = w.get(dim_name, 0.0)
        if weight > 0:
            pairs.append((dim_score.score, weight))

    composite_val = clamp_score(weighted_average(pairs))

    return CompositeScore(
        value=composite_val,
        percentile=None,  # Requires national distribution (future)
        category=ScoreCategory.from_score(composite_val),
        weights_used=w,
    )


# ---------------------------------------------------------------------------
# Summary generators
# ---------------------------------------------------------------------------


def _demand_summary(
    acs: ACSData | None, places: PLACESData | None, score: float
) -> str:
    parts: list[str] = []
    if acs and acs.uninsured_rate is not None:
        parts.append(f"uninsured rate {acs.uninsured_rate}%")
    if places and places.chronic_disease_burden is not None:
        parts.append(f"avg chronic disease prevalence {places.chronic_disease_burden}%")
    if acs and acs.working_age_population is not None:
        parts.append(f"{acs.working_age_population:,} working-age residents")

    category = ScoreCategory.from_score(score).value.lower()
    indicators = "; ".join(parts) if parts else "limited data available"
    return f"{category.capitalize()} demand signal: {indicators}."


def _affordability_summary(acs: ACSData | None, score: float) -> str:
    parts: list[str] = []
    if acs and acs.median_household_income is not None:
        parts.append(f"median income ${acs.median_household_income:,.0f}")
    if acs and acs.dpc_as_pct_of_income is not None:
        parts.append(f"DPC at {acs.dpc_as_pct_of_income}% of income")
    if acs and acs.employment_rate is not None:
        parts.append(f"employment rate {acs.employment_rate}%")

    category = ScoreCategory.from_score(score).value.lower()
    indicators = "; ".join(parts) if parts else "limited data available"
    return f"{category.capitalize()} affordability: {indicators}."
