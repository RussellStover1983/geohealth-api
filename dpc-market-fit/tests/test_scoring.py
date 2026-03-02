"""Tests for the DPC Market Fit scoring engine."""

from __future__ import annotations

from app.models.enums import ScoreCategory
from app.services.census_acs import ACSData
from app.services.cdc_places import PLACESData
from app.services.cdc_svi import SVIData
from app.services.scoring import (
    compute_composite,
    score_affordability,
    score_demand,
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
# Demand scoring
# ---------------------------------------------------------------------------


class TestDemandScoring:
    def _make_acs(self, **overrides):
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
        # Add working-age keys
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

    def _make_places(self, **overrides):
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

    def _make_svi(self, **overrides):
        defaults = {
            "rpl_theme1": 0.6,
            "rpl_theme2": 0.5,
            "rpl_theme3": 0.4,
            "rpl_theme4": 0.3,
            "rpl_themes": 0.5,
        }
        defaults.update(overrides)
        return SVIData(defaults)

    def test_full_data_produces_valid_score(self):
        acs = self._make_acs()
        places = self._make_places()
        svi = self._make_svi()
        result = score_demand(acs, places, svi)
        assert 0 <= result.score <= 100
        assert result.data_completeness > 0
        assert result.category in ScoreCategory

    def test_no_data_returns_weak(self):
        result = score_demand(None, None, None)
        assert result.score == 0.0
        assert result.category == ScoreCategory.WEAK
        assert result.data_completeness == 0.0

    def test_high_uninsured_area(self):
        acs = self._make_acs(uninsured=1800, insurance_universe=4500)
        places = self._make_places()
        svi = self._make_svi(rpl_theme1=0.9)
        result = score_demand(acs, places, svi)
        # High uninsured (40%) should still give >50% demand due to chronic disease
        assert result.score > 40

    def test_low_need_area(self):
        acs = self._make_acs(uninsured=50, insurance_universe=4500)
        places = self._make_places(
            diabetes_pct=5, hypertension_pct=15, obesity_pct=18,
            copd_pct=3, depression_pct=8, asthma_pct=5,
        )
        svi = self._make_svi(rpl_theme1=0.1)
        result = score_demand(acs, places, svi)
        assert result.score < 50


# ---------------------------------------------------------------------------
# Affordability scoring
# ---------------------------------------------------------------------------


class TestAffordabilityScoring:
    def _make_acs(self, **overrides):
        defaults = {
            "total_population": 5000,
            "insurance_universe": 4500,
            "uninsured": 200,
            "employer_insurance": 3000,
            "medicaid": 200,
            "medicare": 300,
            "civilian_labor_force": 3000,
            "unemployed": 150,
            "median_household_income": 75000,
            "renters_total": 1500,
            "renters_30_34pct": 100,
            "renters_35_39pct": 50,
            "renters_40_49pct": 30,
            "renters_50pct_plus": 20,
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

    def test_affluent_area(self):
        acs = self._make_acs(median_household_income=120000, unemployed=50)
        result = score_affordability(acs)
        assert result.score > 60
        assert result.category in (ScoreCategory.STRONG, ScoreCategory.EXCELLENT)

    def test_low_income_area(self):
        acs = self._make_acs(
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

    def test_supply_gap_placeholder(self):
        result = score_supply_gap()
        assert result.score == 50.0
        assert result.data_completeness == 0.0
