"""Tests for the DPC Market Fit scoring engine."""

from __future__ import annotations

from app.models.enums import ScoreCategory
from app.services.census_acs import ACSData
from app.services.census_cbp import CBPData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.services.hrsa_hpsa import HPSAData
from app.services.npi_registry import NPIData
from app.services.scoring import (
    compute_composite,
    score_affordability,
    score_competition,
    score_demand,
    score_employer,
    score_supply_gap,
)
from app.utils.normalization import (
    clamp_score,
    min_max_score,
    percentile_score,
    weighted_average,
)


# ---------------------------------------------------------------------------
# Normalization utilities
# ---------------------------------------------------------------------------


class TestPercentileScore:
    def test_middle_value(self):
        dist = [10, 20, 30, 40, 50]
        score = percentile_score(30, dist)
        assert 30 < score < 70

    def test_minimum_value(self):
        dist = [10, 20, 30, 40, 50]
        score = percentile_score(10, dist)
        assert score < 20

    def test_maximum_value(self):
        dist = [10, 20, 30, 40, 50]
        score = percentile_score(50, dist)
        assert score > 80

    def test_empty_distribution(self):
        assert percentile_score(50, []) == 50.0


class TestMinMaxScore:
    def test_midpoint(self):
        assert min_max_score(50, 0, 100) == 50.0

    def test_minimum(self):
        assert min_max_score(0, 0, 100) == 0.0

    def test_maximum(self):
        assert min_max_score(100, 0, 100) == 100.0

    def test_clamping_above(self):
        assert min_max_score(150, 0, 100) == 100.0

    def test_clamping_below(self):
        assert min_max_score(-10, 0, 100) == 0.0

    def test_inverted(self):
        score = min_max_score(75, 0, 100, invert=True)
        assert score == 25.0

    def test_equal_min_max(self):
        assert min_max_score(50, 50, 50) == 50.0


class TestWeightedAverage:
    def test_basic(self):
        result = weighted_average([(80, 0.5), (60, 0.5)])
        assert result == 70.0

    def test_unequal_weights(self):
        result = weighted_average([(100, 0.75), (0, 0.25)])
        assert result == 75.0

    def test_empty(self):
        assert weighted_average([]) == 0.0


class TestClampScore:
    def test_within_range(self):
        assert clamp_score(55.5) == 55.5

    def test_above_100(self):
        assert clamp_score(110.0) == 100.0

    def test_below_0(self):
        assert clamp_score(-5.0) == 0.0


# ---------------------------------------------------------------------------
# Score categories
# ---------------------------------------------------------------------------


class TestScoreCategory:
    def test_excellent(self):
        assert ScoreCategory.from_score(85) == ScoreCategory.EXCELLENT

    def test_strong(self):
        assert ScoreCategory.from_score(72) == ScoreCategory.STRONG

    def test_moderate(self):
        assert ScoreCategory.from_score(45) == ScoreCategory.MODERATE

    def test_weak(self):
        assert ScoreCategory.from_score(20) == ScoreCategory.WEAK

    def test_boundary_80(self):
        assert ScoreCategory.from_score(80) == ScoreCategory.EXCELLENT

    def test_boundary_60(self):
        assert ScoreCategory.from_score(60) == ScoreCategory.STRONG

    def test_boundary_40(self):
        assert ScoreCategory.from_score(40) == ScoreCategory.MODERATE

    def test_zero(self):
        assert ScoreCategory.from_score(0) == ScoreCategory.WEAK


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_acs(**overrides):
    defaults = {
        "total_population": 5000,
        "insurance_universe": 4500,
        "uninsured": 500,
        "employer_insurance": 2500,
        "medicaid": 400,
        "medicare": 300,
        "civilian_labor_force": 3000,
        "unemployed": 200,
        "median_household_income": 65000,
        "renters_total": 1500,
        "renters_30_34pct": 100,
        "renters_35_39pct": 80,
        "renters_40_49pct": 60,
        "renters_50pct_plus": 40,
        "employment_universe": 3500,
        "in_labor_force": 3200,
    }
    for key in [
        "male_18_19", "male_20", "male_21", "male_22_24",
        "male_25_29", "male_30_34", "male_35_39", "male_40_44",
        "male_45_49", "male_50_54", "male_55_59", "male_60_61", "male_62_64",
        "female_18_19", "female_20", "female_21", "female_22_24",
        "female_25_29", "female_30_34", "female_35_39", "female_40_44",
        "female_45_49", "female_50_54", "female_55_59", "female_60_61", "female_62_64",
    ]:
        defaults[key] = 120
    defaults.update(overrides)
    return ACSData(defaults)


def _make_places(**overrides):
    defaults = {
        "diabetes_pct": 12.0,
        "hypertension_pct": 30.0,
        "obesity_pct": 32.0,
        "copd_pct": 7.0,
        "depression_pct": 20.0,
        "asthma_pct": 10.0,
    }
    defaults.update(overrides)
    return PLACESData(defaults)


def _make_svi(**overrides):
    defaults = {
        "rpl_theme1": 0.6,
        "rpl_theme2": 0.5,
        "rpl_theme3": 0.4,
        "rpl_theme4": 0.3,
        "rpl_themes": 0.5,
    }
    defaults.update(overrides)
    return SVIData(defaults)


def _make_npi(**overrides):
    defaults = {
        "pcp_count": 25,
        "pcp_details": [],
        "facility_counts": {
            "261QF0400X": 2,
            "261QU0200X": 3,
            "261QR1300X": 0,
        },
        "total_population": 5000,
    }
    defaults.update(overrides)
    return NPIData(**defaults)


def _make_hpsa(**overrides):
    defaults = {
        "is_hpsa": True,
        "hpsa_score": 15.0,
        "hpsa_type": "Geographic HPSA",
        "designation_type": "Designated",
        "discipline": "Primary Care",
    }
    defaults.update(overrides)
    return HPSAData(**defaults)


def _make_cbp(**overrides):
    defaults = {
        "total_establishments": 500,
        "target_establishments": 120,
        "total_employees": 8000,
        "annual_payroll": 400_000_000,  # $400M total payroll (already converted from $1000s)
        "industry_breakdown": {
            "Professional, Scientific & Technical Services": 80,
        },
    }
    defaults.update(overrides)
    return CBPData(**defaults)


# ---------------------------------------------------------------------------
# Demand scoring
# ---------------------------------------------------------------------------


class TestDemandScoring:
    def test_full_data_produces_valid_score(self):
        result = score_demand(_make_acs(), _make_places(), _make_svi())
        assert 0 <= result.score <= 100
        assert result.data_completeness > 0
        assert result.category in ScoreCategory

    def test_no_data_returns_weak(self):
        result = score_demand(None, None, None)
        assert result.score == 0.0
        assert result.category == ScoreCategory.WEAK
        assert result.data_completeness == 0.0

    def test_high_uninsured_area(self):
        acs = _make_acs(uninsured=1800, insurance_universe=4500)
        places = _make_places()
        svi = _make_svi(rpl_theme1=0.9)
        result = score_demand(acs, places, svi)
        assert result.score > 40

    def test_low_need_area(self):
        acs = _make_acs(uninsured=50, insurance_universe=4500)
        places = _make_places(
            diabetes_pct=5, hypertension_pct=15, obesity_pct=18,
            copd_pct=3, depression_pct=8, asthma_pct=5,
        )
        svi = _make_svi(rpl_theme1=0.1)
        result = score_demand(acs, places, svi)
        assert result.score < 50


# ---------------------------------------------------------------------------
# Affordability scoring
# ---------------------------------------------------------------------------


class TestAffordabilityScoring:
    def test_affluent_area(self):
        acs = _make_acs(median_household_income=120000, unemployed=50)
        result = score_affordability(acs)
        assert result.score > 60
        assert result.category in (ScoreCategory.STRONG, ScoreCategory.EXCELLENT)

    def test_low_income_area(self):
        acs = _make_acs(
            median_household_income=25000, unemployed=600,
            renters_30_34pct=200, renters_35_39pct=200,
            renters_40_49pct=200, renters_50pct_plus=200,
        )
        result = score_affordability(acs)
        assert result.score < 40

    def test_no_data(self):
        result = score_affordability(None)
        assert result.score == 0.0
        assert result.data_completeness == 0.0


# ---------------------------------------------------------------------------
# Supply gap scoring
# ---------------------------------------------------------------------------


class TestSupplyGapScoring:
    def test_no_data_returns_placeholder(self):
        result = score_supply_gap()
        assert result.score == 50.0
        assert result.data_completeness == 0.0

    def test_shortage_area_high_score(self):
        """HPSA with few PCPs = high supply gap = high opportunity."""
        npi = _make_npi(pcp_count=5, total_population=10000)
        hpsa = _make_hpsa(is_hpsa=True, hpsa_score=20.0)
        result = score_supply_gap(npi, hpsa, 10000)
        assert result.score > 60
        assert result.data_completeness > 0

    def test_well_served_area_low_score(self):
        """Non-HPSA with many PCPs = low supply gap = low opportunity."""
        npi = _make_npi(pcp_count=100, total_population=5000)
        hpsa = HPSAData(is_hpsa=False)
        result = score_supply_gap(npi, hpsa, 5000)
        assert result.score < 40

    def test_hpsa_only(self):
        """HPSA data only, no NPI — partial scoring."""
        hpsa = _make_hpsa(is_hpsa=True, hpsa_score=18.0)
        result = score_supply_gap(None, hpsa, None)
        assert result.score > 50
        assert 0 < result.data_completeness < 1.0

    def test_npi_only_no_hpsa(self):
        """NPI data only, no HPSA — partial scoring."""
        npi = _make_npi(pcp_count=10, total_population=5000)
        result = score_supply_gap(npi, None, 5000)
        assert result.data_completeness > 0
        assert 0 < result.score <= 100

    def test_many_fqhcs_lower_gap(self):
        """FQHCs present = lower supply gap (they fill some need)."""
        npi_with_fqhc = _make_npi(
            pcp_count=10,
            total_population=5000,
            facility_counts={
                "261QF0400X": 5,
                "261QU0200X": 0,
                "261QR1300X": 0,
            },
        )
        npi_no_fqhc = _make_npi(
            pcp_count=10,
            total_population=5000,
            facility_counts={
                "261QF0400X": 0,
                "261QU0200X": 0,
                "261QR1300X": 0,
            },
        )
        result_fqhc = score_supply_gap(npi_with_fqhc, None, 5000)
        result_none = score_supply_gap(npi_no_fqhc, None, 5000)
        # More FQHCs should lower the supply gap score
        assert result_fqhc.score < result_none.score


# ---------------------------------------------------------------------------
# Employer scoring
# ---------------------------------------------------------------------------


class TestEmployerScoring:
    def test_no_data_returns_placeholder(self):
        result = score_employer()
        assert result.score == 50.0
        assert result.data_completeness == 0.0

    def test_strong_employer_market(self):
        cbp = _make_cbp(
            total_establishments=5000,
            target_establishments=2000,
            total_employees=50000,
            annual_payroll=4_000_000_000,  # $4B total → $80k avg
        )
        result = score_employer(cbp)
        assert result.score > 60
        assert result.data_completeness > 0

    def test_weak_employer_market(self):
        cbp = CBPData(
            total_establishments=50,
            target_establishments=5,
            total_employees=200,
            annual_payroll=5_000_000,  # $5M → $25k avg
        )
        result = score_employer(cbp)
        assert result.score < 40

    def test_high_wages_boost_score(self):
        cbp_high_wage = _make_cbp(
            total_employees=1000,
            annual_payroll=80_000_000,  # $80M → $80k avg
        )
        cbp_low_wage = _make_cbp(
            total_employees=1000,
            annual_payroll=30_000_000,  # $30M → $30k avg
        )
        result_high = score_employer(cbp_high_wage)
        result_low = score_employer(cbp_low_wage)
        assert result_high.score > result_low.score

    def test_summary_includes_data(self):
        cbp = _make_cbp()
        result = score_employer(cbp)
        assert "mid-size employers" in result.summary.lower() or "establishments" in result.summary.lower()


# ---------------------------------------------------------------------------
# Competition scoring
# ---------------------------------------------------------------------------


class TestCompetitionScoring:
    def test_no_data_returns_placeholder(self):
        result = score_competition()
        assert result.score == 50.0
        assert result.data_completeness == 0.0

    def test_low_competition_high_score(self):
        """Few facilities + low PCP density = less competition = high score."""
        npi = _make_npi(
            pcp_count=5,
            total_population=10000,
            facility_counts={
                "261QF0400X": 0,
                "261QU0200X": 0,
                "261QR1300X": 0,
            },
        )
        result = score_competition(npi, 10000)
        assert result.score > 60

    def test_high_competition_low_score(self):
        """Many facilities + high PCP density = more competition = low score."""
        npi = _make_npi(
            pcp_count=150,
            total_population=5000,
            facility_counts={
                "261QF0400X": 5,
                "261QU0200X": 8,
                "261QR1300X": 3,
            },
        )
        result = score_competition(npi, 5000)
        assert result.score < 30

    def test_npi_only_partial_completeness(self):
        npi = _make_npi(pcp_count=20, total_population=None)
        result = score_competition(npi, None)
        # Without population we can only score facility counts
        assert result.data_completeness > 0
        assert result.data_completeness < 1.0


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------


class TestCompositeScoring:
    def test_equal_scores(self):
        from app.models.response import DimensionScore

        dims = {
            "demand": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
            "supply_gap": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
            "affordability": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
            "employer": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
            "competition": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
        }
        composite = compute_composite(dims)
        assert composite.value == 70.0
        assert composite.category == ScoreCategory.STRONG

    def test_custom_weights(self):
        from app.models.response import DimensionScore

        dims = {
            "demand": DimensionScore(score=100, category=ScoreCategory.EXCELLENT, summary=""),
            "supply_gap": DimensionScore(score=0, category=ScoreCategory.WEAK, summary=""),
            "affordability": DimensionScore(score=0, category=ScoreCategory.WEAK, summary=""),
            "employer": DimensionScore(score=0, category=ScoreCategory.WEAK, summary=""),
            "competition": DimensionScore(score=0, category=ScoreCategory.WEAK, summary=""),
        }
        weights = {
            "demand": 1.0,
            "supply_gap": 0.0,
            "affordability": 0.0,
            "employer": 0.0,
            "competition": 0.0,
        }
        composite = compute_composite(dims, weights)
        assert composite.value == 100.0

    def test_all_dimensions_contribute(self):
        """With real data all five dimensions should contribute to composite."""
        from app.models.response import DimensionScore

        dims = {
            "demand": DimensionScore(score=80, category=ScoreCategory.EXCELLENT, summary=""),
            "supply_gap": DimensionScore(score=60, category=ScoreCategory.STRONG, summary=""),
            "affordability": DimensionScore(score=70, category=ScoreCategory.STRONG, summary=""),
            "employer": DimensionScore(score=50, category=ScoreCategory.MODERATE, summary=""),
            "competition": DimensionScore(score=90, category=ScoreCategory.EXCELLENT, summary=""),
        }
        composite = compute_composite(dims)
        # 80*0.25 + 60*0.25 + 70*0.20 + 50*0.20 + 90*0.10 = 20+15+14+10+9 = 68
        assert 67 <= composite.value <= 69
        assert composite.category == ScoreCategory.STRONG
