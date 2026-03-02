"""Score normalization utilities — percentile-based and min-max."""

from __future__ import annotations


def percentile_score(value: float, distribution: list[float]) -> float:
    """Compute percentile rank of value within a distribution.

    Returns a score from 0 to 100.
    """
    if not distribution:
        return 50.0
    count_below = sum(1 for v in distribution if v < value)
    count_equal = sum(1 for v in distribution if v == value)
    percentile = (count_below + 0.5 * count_equal) / len(distribution) * 100
    return round(max(0, min(100, percentile)), 1)


def min_max_score(
    value: float, min_val: float, max_val: float, invert: bool = False
) -> float:
    """Normalize value to 0-100 using min-max scaling.

    Args:
        value: Raw value to normalize.
        min_val: Minimum of the reference range.
        max_val: Maximum of the reference range.
        invert: If True, higher raw values produce lower scores.
    """
    if max_val == min_val:
        return 50.0
    clamped = max(min_val, min(max_val, value))
    normalized = (clamped - min_val) / (max_val - min_val)
    if invert:
        normalized = 1.0 - normalized
    return round(normalized * 100, 1)


def clamp_score(score: float) -> float:
    """Clamp a score to the 0-100 range."""
    return max(0.0, min(100.0, round(score, 1)))


def weighted_average(scores: list[tuple[float, float]]) -> float:
    """Compute weighted average from list of (score, weight) tuples.

    Skips entries where score is None-like. Renormalizes weights
    to sum to 1.0 across available scores.
    """
    available = [(s, w) for s, w in scores if w > 0]
    if not available:
        return 0.0
    total_weight = sum(w for _, w in available)
    if total_weight == 0:
        return 0.0
    return round(sum(s * w for s, w in available) / total_weight, 1)
