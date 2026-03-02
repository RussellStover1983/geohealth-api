from __future__ import annotations

from enum import Enum


class ScoreCategory(str, Enum):
    """Market fit score category thresholds."""
    WEAK = "WEAK"           # 0-39
    MODERATE = "MODERATE"   # 40-59
    STRONG = "STRONG"       # 60-79
    EXCELLENT = "EXCELLENT"  # 80-100

    @classmethod
    def from_score(cls, score: float) -> ScoreCategory:
        if score >= 80:
            return cls.EXCELLENT
        if score >= 60:
            return cls.STRONG
        if score >= 40:
            return cls.MODERATE
        return cls.WEAK


class ProviderTier(str, Enum):
    """NPI taxonomy tier for supply calculations."""
    TIER1 = "tier1"
    TIER1_TIER2 = "tier1_tier2"
    ALL = "all"


class Dimension(str, Enum):
    """Scoring dimensions."""
    DEMAND = "demand"
    SUPPLY_GAP = "supply_gap"
    AFFORDABILITY = "affordability"
    EMPLOYER = "employer"
    COMPETITION = "competition"
