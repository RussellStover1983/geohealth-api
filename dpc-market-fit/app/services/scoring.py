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
from app.services.census_cbp import CBPData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.services.hrsa_hpsa import HPSAData
from app.services.npi_registry import NPIData
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
    # Demand dimension
    "uninsured_rate": (4.0, 25.0),           # % uninsured — 95th %ile ~25%
    "chronic_disease_burden": (8.0, 25.0),    # avg prevalence % — most tracts 10-22%
    "working_age_pop": (800, 5000),          # count — typical tract range
    "svi_socioeconomic": (0.0, 1.0),         # percentile 0-1 (unchanged)
    # Affordability dimension
    "median_income": (25000, 120000),         # dollars — tighter range
    "dpc_pct_income": (1.0, 6.0),            # % — typical DPC range
    "employment_rate": (85.0, 98.0),         # % — most tracts 88-97%
    "housing_burden": (15.0, 55.0),          # % — tighter range
    # Supply gap dimension
    "pcp_per_100k": (30.0, 120.0),           # PCPs per 100k — realistic density
    "hpsa_score": (0.0, 25.0),              # HPSA score 0-25 (unchanged)
    "fqhc_presence": (0, 3),                 # FQHC count — most areas 0-2
    # Employer dimension
    "target_estab_pct": (8.0, 35.0),         # % establishments 10-249 employees
    "avg_annual_wage": (30000, 80000),        # average annual wage — middle 90%
    "total_establishments": (200, 5000),      # total establishments — typical counties
    # Competition dimension
    "competing_facilities": (0, 10),          # total competing facility count
    "pcp_density": (30.0, 120.0),            # PCP density per 100k — matches supply gap
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


def score_supply_gap(
    npi: NPIData | None = None,
    hpsa: HPSAData | None = None,
    population: int | None = None,
) -> DimensionScore:
    """Score the Supply Gap dimension (0-100).

    Higher score = larger supply gap = MORE opportunity for DPC.
    Low PCP density and HPSA designation indicate unmet demand.
    """
    indicators: list[tuple[float, float]] = []
    completeness_parts = 0
    completeness_total = 3  # pcp_density, hpsa_score, fqhc_presence

    # PCP per 100k (weight: 0.40) — INVERTED: fewer PCPs = higher opportunity
    if npi and population and population > 0:
        pcp_per_100k = npi.pcp_count / population * 100_000
        score = min_max_score(
            pcp_per_100k, *_NATIONAL_REFS["pcp_per_100k"], invert=True
        )
        indicators.append((score, 0.40))
        completeness_parts += 1
    elif npi and npi.pcp_per_100k is not None:
        score = min_max_score(
            npi.pcp_per_100k, *_NATIONAL_REFS["pcp_per_100k"], invert=True
        )
        indicators.append((score, 0.40))
        completeness_parts += 1

    # HPSA score (weight: 0.35) — higher HPSA score = greater shortage = opportunity
    if hpsa and hpsa.is_hpsa and hpsa.hpsa_score is not None:
        score = min_max_score(hpsa.hpsa_score, *_NATIONAL_REFS["hpsa_score"])
        indicators.append((score, 0.35))
        completeness_parts += 1
    elif hpsa and not hpsa.is_hpsa:
        # Not a shortage area — moderate-low supply gap score
        indicators.append((30.0, 0.35))
        completeness_parts += 1

    # FQHC presence (weight: 0.25) — INVERTED: more FQHCs = less gap
    if npi:
        fqhc_count = npi.fqhc_count
        score = min_max_score(fqhc_count, *_NATIONAL_REFS["fqhc_presence"], invert=True)
        indicators.append((score, 0.25))
        completeness_parts += 1

    if not indicators:
        return DimensionScore(
            score=50.0,
            category=ScoreCategory.MODERATE,
            summary="Insufficient data for supply gap scoring.",
            data_completeness=0.0,
        )

    final = clamp_score(weighted_average(indicators))
    completeness = completeness_parts / completeness_total

    summary = _supply_gap_summary(npi, hpsa, final)

    return DimensionScore(
        score=final,
        category=ScoreCategory.from_score(final),
        summary=summary,
        data_completeness=round(completeness, 2),
    )


def score_employer(
    cbp: CBPData | None = None,
    acs: ACSData | None = None,
) -> DimensionScore:
    """Score the Employer Opportunity dimension (0-100).

    Higher score = better employer landscape for DPC partnerships.
    More mid-size employers, higher wages, robust business base.
    """
    indicators: list[tuple[float, float]] = []
    completeness_parts = 0
    completeness_total = 3  # target_estab_pct, avg_wage, total_estab

    # DPC-target establishment % (weight: 0.40) — more mid-size = better
    if cbp and cbp.target_establishment_pct is not None:
        score = min_max_score(
            cbp.target_establishment_pct, *_NATIONAL_REFS["target_estab_pct"]
        )
        indicators.append((score, 0.40))
        completeness_parts += 1

    # Average annual wage (weight: 0.35) — higher wages = can afford DPC benefit
    if cbp and cbp.avg_annual_wage is not None:
        score = min_max_score(
            cbp.avg_annual_wage, *_NATIONAL_REFS["avg_annual_wage"]
        )
        indicators.append((score, 0.35))
        completeness_parts += 1

    # Total establishments (weight: 0.25) — larger business base = more prospects
    if cbp and cbp.total_establishments > 0:
        score = min_max_score(
            cbp.total_establishments, *_NATIONAL_REFS["total_establishments"]
        )
        indicators.append((score, 0.25))
        completeness_parts += 1

    if not indicators:
        return DimensionScore(
            score=50.0,
            category=ScoreCategory.MODERATE,
            summary="Insufficient data for employer scoring.",
            data_completeness=0.0,
        )

    final = clamp_score(weighted_average(indicators))
    completeness = completeness_parts / completeness_total

    summary = _employer_summary(cbp, final)

    return DimensionScore(
        score=final,
        category=ScoreCategory.from_score(final),
        summary=summary,
        data_completeness=round(completeness, 2),
    )


def score_competition(
    npi: NPIData | None = None,
    population: int | None = None,
) -> DimensionScore:
    """Score the Competition dimension (0-100).

    Higher score = LESS competition = MORE opportunity.
    Fewer competing facilities and lower PCP density = less saturation.
    """
    indicators: list[tuple[float, float]] = []
    completeness_parts = 0
    completeness_total = 2  # competing_facilities, pcp_density

    # Competing facility count (weight: 0.50) — INVERTED: fewer = better
    if npi:
        total_competing = (
            npi.fqhc_count + npi.urgent_care_count + npi.rural_health_clinic_count
        )
        score = min_max_score(
            total_competing, *_NATIONAL_REFS["competing_facilities"], invert=True
        )
        indicators.append((score, 0.50))
        completeness_parts += 1

    # PCP density (weight: 0.50) — INVERTED: lower density = less competition
    if npi and population and population > 0:
        pcp_density = npi.pcp_count / population * 100_000
        score = min_max_score(
            pcp_density, *_NATIONAL_REFS["pcp_density"], invert=True
        )
        indicators.append((score, 0.50))
        completeness_parts += 1

    if not indicators:
        return DimensionScore(
            score=50.0,
            category=ScoreCategory.MODERATE,
            summary="Insufficient data for competition scoring.",
            data_completeness=0.0,
        )

    final = clamp_score(weighted_average(indicators))
    completeness = completeness_parts / completeness_total

    # Cap at 70 when data is incomplete to prevent false "EXCELLENT" ratings
    if completeness < 1.0 and final > 70.0:
        final = 70.0

    summary = _competition_summary(npi, final)

    return DimensionScore(
        score=final,
        category=ScoreCategory.from_score(final),
        summary=summary,
        data_completeness=round(completeness, 2),
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


def _supply_gap_summary(
    npi: NPIData | None, hpsa: HPSAData | None, score: float
) -> str:
    parts: list[str] = []
    if npi and npi.pcp_per_100k is not None:
        parts.append(f"{npi.pcp_per_100k} PCPs per 100k (benchmark: 75)")
    elif npi:
        parts.append(f"{npi.pcp_count} PCPs found in area")
    if hpsa and hpsa.is_hpsa:
        hpsa_str = f"HPSA designated (score {hpsa.hpsa_score})" if hpsa.hpsa_score else "HPSA designated"
        parts.append(hpsa_str)
    elif hpsa:
        parts.append("not a designated HPSA")
    if npi and npi.fqhc_count > 0:
        parts.append(f"{npi.fqhc_count} FQHC(s) in area")

    category = ScoreCategory.from_score(score).value.lower()
    indicators = "; ".join(parts) if parts else "limited data available"
    return f"{category.capitalize()} supply gap: {indicators}."


def _employer_summary(cbp: CBPData | None, score: float) -> str:
    parts: list[str] = []
    if cbp and cbp.target_establishments > 0:
        parts.append(f"{cbp.target_establishments:,} mid-size employers (10-249 employees)")
    if cbp and cbp.avg_annual_wage is not None:
        parts.append(f"avg wage ${cbp.avg_annual_wage:,.0f}")
    if cbp and cbp.total_establishments > 0:
        parts.append(f"{cbp.total_establishments:,} total establishments")

    category = ScoreCategory.from_score(score).value.lower()
    indicators = "; ".join(parts) if parts else "limited data available"
    return f"{category.capitalize()} employer opportunity: {indicators}."


def _competition_summary(npi: NPIData | None, score: float) -> str:
    parts: list[str] = []
    if npi:
        total = npi.fqhc_count + npi.urgent_care_count + npi.rural_health_clinic_count
        if total > 0:
            parts.append(f"{total} competing facilities")
        else:
            parts.append("no competing facilities found")
        if npi.pcp_per_100k is not None:
            parts.append(f"PCP density {npi.pcp_per_100k}/100k")

    category = ScoreCategory.from_score(score).value.lower()
    indicators = "; ".join(parts) if parts else "limited data available"
    return f"{category.capitalize()} competition: {indicators}."
