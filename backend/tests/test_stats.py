"""
Tests for 1RM / PR calculations.
No database or network calls needed — pure unit tests.
"""
import pytest
from app.routers.stats import epley_1rm


class TestEpley1RM:
    def test_single_rep_returns_weight(self):
        """1RM for a single-rep set is just the weight itself."""
        assert epley_1rm(100.0, 1) == 100.0

    def test_zero_reps_returns_weight(self):
        """Edge case: 0 reps — return weight unchanged."""
        assert epley_1rm(100.0, 0) == 100.0

    def test_five_rep_max(self):
        """100 kg × 5 reps → 100 × (1 + 5/30) ≈ 116.7 kg"""
        result = epley_1rm(100.0, 5)
        assert abs(result - 116.67) < 0.1

    def test_reps_capped_at_12(self):
        """15-rep set should give same 1RM estimate as 12-rep set (cap applied)."""
        assert epley_1rm(60.0, 15) == epley_1rm(60.0, 12)
        assert epley_1rm(60.0, 20) == epley_1rm(60.0, 12)

    def test_cap_at_12_value(self):
        """100 kg × 12 reps (capped) → 100 × (1 + 12/30) = 140 kg"""
        result = epley_1rm(100.0, 12)
        assert abs(result - 140.0) < 0.01

    def test_bodyweight_exercise(self):
        """Works with low weights like bodyweight movements."""
        result = epley_1rm(0.0, 10)
        assert result == 0.0
