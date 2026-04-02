"""Tests for src/analysis/leverage.py and compute_leverage_index."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.analysis.leverage import (
    LeverageStats,
    _calc_ba,
    _is_at_bat,
    _is_hit,
    compute_batter_clutch,
)
from src.utils.run_expectancy import compute_leverage_index

# ─────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────

class TestIsHit:
    def test_single(self) -> None:
        assert _is_hit("1B") is True

    def test_double(self) -> None:
        assert _is_hit("2B") is True

    def test_triple(self) -> None:
        assert _is_hit("3B") is True

    def test_home_run(self) -> None:
        assert _is_hit("HR") is True

    def test_out(self) -> None:
        assert _is_hit("out") is False

    def test_walk(self) -> None:
        assert _is_hit("BB") is False

    def test_none(self) -> None:
        assert _is_hit(None) is False


class TestIsAtBat:
    def test_hit_counts_as_ab(self) -> None:
        assert _is_at_bat("1B") is True

    def test_strikeout_counts_as_ab(self) -> None:
        assert _is_at_bat("K") is True

    def test_walk_not_ab(self) -> None:
        assert _is_at_bat("BB") is False

    def test_hbp_not_ab(self) -> None:
        assert _is_at_bat("HBP") is False

    def test_sac_not_ab(self) -> None:
        assert _is_at_bat("SAC") is False

    def test_none_returns_false(self) -> None:
        assert _is_at_bat(None) is False


class TestCalcBa:
    def test_normal(self) -> None:
        assert _calc_ba(3, 10) == pytest.approx(0.3)

    def test_zero_ab_returns_none(self) -> None:
        assert _calc_ba(0, 0) is None

    def test_perfect_average(self) -> None:
        assert _calc_ba(5, 5) == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────
# compute_leverage_index from run_expectancy
# ─────────────────────────────────────────────────────────────────

class TestComputeLeverageIndex:
    def test_bases_empty_early_inning_low_li(self) -> None:
        """Empty bases, 0 outs, inning 1, close game → moderate LI (not very high)."""
        li = compute_leverage_index("000", 0, inning=1, score_diff=0)
        # RE24("000",0)=0.481, avg≈0.95, base_li<1, close_game=1.3 → should be < 1.5
        assert li < 1.5

    def test_bases_loaded_late_inning_close_game_high_li(self) -> None:
        """Bases loaded, 0 outs, inning 9, 1-run game → very high LI."""
        li = compute_leverage_index("111", 0, inning=9, score_diff=1)
        assert li > 2.0

    def test_blowout_reduces_li(self) -> None:
        """Large score diff should reduce LI via close_game_factor."""
        li_close = compute_leverage_index("000", 0, inning=7, score_diff=1)
        li_blowout = compute_leverage_index("000", 0, inning=7, score_diff=10)
        assert li_blowout < li_close

    def test_extra_innings_factor(self) -> None:
        """Extra innings should have higher LI multiplier than early innings."""
        li_early = compute_leverage_index("000", 0, inning=2, score_diff=0)
        li_extra = compute_leverage_index("000", 0, inning=11, score_diff=0)
        assert li_extra > li_early

    def test_invalid_base_state_raises(self) -> None:
        with pytest.raises(KeyError):
            compute_leverage_index("999", 0, inning=1, score_diff=0)

    def test_returns_float(self) -> None:
        result = compute_leverage_index("100", 1, inning=5, score_diff=2)
        assert isinstance(result, float)


# ─────────────────────────────────────────────────────────────────
# compute_batter_clutch — integration tests
# ─────────────────────────────────────────────────────────────────

class TestComputeBatterClutch:
    def test_returns_result_for_seeded_batter(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=2026)
        assert result is not None

    def test_returns_none_for_unknown_batter(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "nobody_here", year=2026)
        assert result is None

    def test_result_is_leverage_stats(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=2026)
        assert isinstance(result, LeverageStats)

    def test_total_pa_matches_seeded_data(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        # We seeded 7 PAs for cpbl_batter_2 in test_g1
        assert result.total_pa == 7

    def test_sample_note_is_string(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        assert isinstance(result.sample_note, str)

    def test_wrong_year_returns_none(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=1990)
        assert result is None

    def test_overall_ba_in_valid_range(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_clutch(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        if result.overall_ba is not None:
            assert 0.0 <= result.overall_ba <= 1.0
