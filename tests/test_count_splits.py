"""Tests for src/analysis/count_splits.py."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.analysis.count_splits import (
    _aggregate_counts,
    _classify_count,
    compute_batter_count_splits,
)
from src.utils.constants import COUNT_AHEAD, COUNT_BEHIND, COUNT_EVEN

# ─────────────────────────────────────────────────────────────────
# _classify_count
# ─────────────────────────────────────────────────────────────────

class TestClassifyCount:
    def test_basic(self) -> None:
        assert _classify_count(2, 1) == "2-1"

    def test_zero_zero(self) -> None:
        assert _classify_count(0, 0) == "0-0"

    def test_full_count(self) -> None:
        assert _classify_count(3, 2) == "3-2"

    def test_returns_string(self) -> None:
        result = _classify_count(1, 2)
        assert isinstance(result, str)
        assert result == "1-2"

    def test_format_is_balls_dash_strikes(self) -> None:
        result = _classify_count(3, 0)
        assert result == "3-0"


# ─────────────────────────────────────────────────────────────────
# _aggregate_counts
# ─────────────────────────────────────────────────────────────────

class TestAggregateCounts:
    @pytest.fixture()
    def sample_rows(self) -> list[dict]:
        return [
            {"count": "1-0", "pa": 5, "hits": 2, "outs": 2, "bb": 1, "k": 0},
            {"count": "2-0", "pa": 3, "hits": 1, "outs": 2, "bb": 0, "k": 0},
            {"count": "0-1", "pa": 4, "hits": 1, "outs": 2, "bb": 0, "k": 1},
            {"count": "0-0", "pa": 6, "hits": 2, "outs": 3, "bb": 0, "k": 1},
        ]

    def test_aggregate_ahead_counts(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, COUNT_AHEAD)
        assert result is not None
        # "1-0" and "2-0" match COUNT_AHEAD
        assert result.pa == 8
        assert result.result_hit == 3
        assert result.result_out == 4

    def test_aggregate_behind_counts(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, COUNT_BEHIND)
        assert result is not None
        assert result.pa == 4  # only "0-1"

    def test_returns_none_for_empty_set(self, sample_rows: list[dict]) -> None:
        """Count set with no matching rows should return None."""
        result = _aggregate_counts(sample_rows, {"9-9"})
        assert result is None

    def test_ba_calculation(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, {"0-0"})
        assert result is not None
        # hits=2, outs=3, ab=5 → BA = 0.4
        assert result.ba == pytest.approx(0.4, abs=1e-3)

    def test_k_pct_calculation(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, {"0-1"})
        assert result is not None
        # k=1, pa=4 → K% = 0.25
        assert result.k_pct == pytest.approx(0.25, abs=1e-3)

    def test_bb_pct_calculation(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, COUNT_AHEAD)
        assert result is not None
        # bb=1 / pa=8 = 0.125
        assert result.bb_pct == pytest.approx(0.125, abs=1e-3)

    def test_ba_none_when_no_at_bats(self) -> None:
        """AB = 0 (all BB) should yield ba=None."""
        rows = [{"count": "3-0", "pa": 2, "hits": 0, "outs": 0, "bb": 2, "k": 0}]
        result = _aggregate_counts(rows, {"3-0"})
        assert result is not None
        assert result.ba is None

    def test_count_string_is_sorted_join(self, sample_rows: list[dict]) -> None:
        result = _aggregate_counts(sample_rows, COUNT_EVEN)
        assert result is not None
        # COUNT_EVEN sorted and joined
        assert result.count == ",".join(sorted(COUNT_EVEN))


# ─────────────────────────────────────────────────────────────────
# compute_batter_count_splits — integration tests
# ─────────────────────────────────────────────────────────────────

class TestComputeBatterCountSplits:
    def test_returns_result_for_seeded_batter(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=2026)
        assert result is not None

    def test_returns_none_for_unknown_batter(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_nobody", year=2026)
        assert result is None

    def test_role_is_batter(self, db_session: Session, seed_data: Session) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        assert result.role == "batter"

    def test_player_id_preserved(self, db_session: Session, seed_data: Session) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        assert result.player_id == "cpbl_batter_2"

    def test_by_count_non_empty(self, db_session: Session, seed_data: Session) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        assert len(result.by_count) > 0

    def test_wrong_year_returns_none(self, db_session: Session, seed_data: Session) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=1999)
        assert result is None

    def test_total_pa_non_negative(self, db_session: Session, seed_data: Session) -> None:
        result = compute_batter_count_splits(db_session, "cpbl_batter_2", year=2026)
        assert result is not None
        assert result.total_pa >= 0
