"""Tests for src/analysis/lob_pct.py — _calc_lob_pct & compute_lob_leaderboard."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.analysis.lob_pct import _calc_lob_pct, compute_lob_leaderboard

# ─────────────────────────────────────────────────────────────────
# _calc_lob_pct — unit tests
# ─────────────────────────────────────────────────────────────────

class TestCalcLobPct:
    def test_normal_case(self) -> None:
        """h=10, bb=5, r=8, hr=2 should yield expected LOB%."""
        # numerator = 10 + 5 - 8 = 7
        # denominator = 10 + 5 - 1.4 * 2 = 15 - 2.8 = 12.2
        # raw = 7 / 12.2 ≈ 0.5738
        result = _calc_lob_pct(h=10, bb=5, r=8, hr=2)
        assert result is not None
        assert abs(result - (7 / 12.2)) < 1e-6

    def test_zero_denominator_returns_none(self) -> None:
        """When h + bb + hbp - 1.4 * hr <= 0, return None."""
        # h=0, bb=0, hbp=0, hr=1  → denominator = -1.4
        result = _calc_lob_pct(h=0, bb=0, r=0, hr=1)
        assert result is None

    def test_all_zeros(self) -> None:
        """All zeros: denominator = 0, should return None."""
        result = _calc_lob_pct(h=0, bb=0, r=0, hr=0)
        assert result is None

    def test_lob_pct_clamps_to_zero(self) -> None:
        """Negative numerator should clamp to 0.0."""
        # h=2, bb=0, r=5, hr=0 → numerator = -3, denominator = 2
        result = _calc_lob_pct(h=2, bb=0, r=5, hr=0)
        assert result == 0.0

    def test_lob_pct_clamps_to_one(self) -> None:
        """Value > 1.0 should clamp to 1.0."""
        # h=10, bb=0, r=0, hr=0 → numerator = 10, denominator = 10 → 1.0
        result = _calc_lob_pct(h=10, bb=0, r=0, hr=0)
        assert result == 1.0

    def test_hbp_contributes_to_formula(self) -> None:
        """hbp should be added to both numerator and denominator."""
        # h=5, bb=2, r=3, hr=0, hbp=1 → num=5, den=8
        result = _calc_lob_pct(h=5, bb=2, r=3, hr=0, hbp=1)
        assert result is not None
        assert abs(result - (5 / 8)) < 1e-6

    def test_returns_float(self) -> None:
        result = _calc_lob_pct(h=8, bb=3, r=5, hr=1)
        assert isinstance(result, float)

    def test_exact_denominator_boundary(self) -> None:
        """denominator == 0 exactly should return None."""
        # h=0, bb=0, hbp=0, hr=0 → denom = 0
        result = _calc_lob_pct(h=0, bb=0, r=0, hr=0, hbp=0)
        assert result is None


# ─────────────────────────────────────────────────────────────────
# compute_lob_leaderboard — integration tests
# ─────────────────────────────────────────────────────────────────

class TestComputeLobLeaderboard:
    def test_returns_list(self, db_session: Session, seed_data: Session) -> None:
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        assert isinstance(results, list)

    def test_pitcher_in_results(self, db_session: Session, seed_data: Session) -> None:
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        player_ids = [r.player_id for r in results]
        assert "cpbl_pitcher_1" in player_ids

    def test_min_ip_filter(self, db_session: Session, seed_data: Session) -> None:
        """Pitchers below min_ip threshold should be excluded."""
        results_high = compute_lob_leaderboard(db_session, year=2026, min_ip=100.0)
        assert len(results_high) == 0

    def test_result_fields(self, db_session: Session, seed_data: Session) -> None:
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        r = results[0]
        assert hasattr(r, "player_id")
        assert hasattr(r, "lob_pct")
        assert hasattr(r, "is_lucky")
        assert hasattr(r, "is_unlucky")
        assert hasattr(r, "league_avg")
        assert r.league_avg == pytest.approx(0.70)

    def test_sorted_by_lob_pct_descending(self, db_session: Session, seed_data: Session) -> None:
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        pcts = [r.lob_pct for r in results if r.lob_pct is not None]
        assert pcts == sorted(pcts, reverse=True)

    def test_wrong_year_returns_empty(self, db_session: Session, seed_data: Session) -> None:
        results = compute_lob_leaderboard(db_session, year=2000, min_ip=0.0)
        assert results == []

    def test_sample_note_small_ip(self, db_session: Session, seed_data: Session) -> None:
        """Pitcher with < 10 IP should have a small-sample note."""
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        # Our seeded pitcher has 13 IP total — between 10 and 30
        r = next((x for x in results if x.player_id == "cpbl_pitcher_1"), None)
        assert r is not None
        assert r.sample_note != ""  # some note present for < 30 IP

    def test_is_lucky_flag(self, db_session: Session, seed_data: Session) -> None:
        """is_lucky / is_unlucky are booleans."""
        results = compute_lob_leaderboard(db_session, year=2026, min_ip=0.0)
        for r in results:
            assert isinstance(r.is_lucky, bool)
            assert isinstance(r.is_unlucky, bool)
