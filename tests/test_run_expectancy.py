"""Tests for src/utils/run_expectancy.py."""

from __future__ import annotations

import pytest

from src.utils.run_expectancy import (
    MLB_RE24_2023,
    compute_leverage_index,
    get_re24,
    get_run_expectancy,
)

# ─────────────────────────────────────────────────────────────────
# get_re24
# ─────────────────────────────────────────────────────────────────

class TestGetRe24:
    def test_returns_24_entries(self) -> None:
        matrix = get_re24()
        assert len(matrix) == 24

    def test_returns_dict(self) -> None:
        matrix = get_re24()
        assert isinstance(matrix, dict)

    def test_all_keys_are_tuples(self) -> None:
        matrix = get_re24()
        for key in matrix.keys():
            assert isinstance(key, tuple)
            assert len(key) == 2

    def test_all_values_are_floats(self) -> None:
        matrix = get_re24()
        for val in matrix.values():
            assert isinstance(val, float)

    def test_year_arg_returns_same_matrix(self) -> None:
        """Currently always returns MLB proxy regardless of year."""
        assert get_re24(2026) == get_re24(None)

    def test_same_as_mlb_constant(self) -> None:
        assert get_re24() is MLB_RE24_2023


# ─────────────────────────────────────────────────────────────────
# get_run_expectancy
# ─────────────────────────────────────────────────────────────────

class TestGetRunExpectancy:
    def test_empty_bases_zero_outs(self) -> None:
        """('000', 0) should be ≈ 0.481 per MLB 2023 data."""
        re = get_run_expectancy("000", 0)
        assert re == pytest.approx(0.481, abs=1e-6)

    def test_bases_loaded_zero_outs(self) -> None:
        re = get_run_expectancy("111", 0)
        assert re == pytest.approx(2.282, abs=1e-6)

    def test_runner_on_second_two_outs(self) -> None:
        re = get_run_expectancy("010", 2)
        assert re == pytest.approx(0.319, abs=1e-6)

    def test_two_outs_empty_bases(self) -> None:
        re = get_run_expectancy("000", 2)
        assert re == pytest.approx(0.098, abs=1e-6)

    def test_invalid_base_state_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_run_expectancy("999", 0)

    def test_invalid_outs_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_run_expectancy("000", 3)

    def test_all_24_states_accessible(self) -> None:
        base_states = ["000", "100", "010", "001", "110", "101", "011", "111"]
        for bs in base_states:
            for outs in range(3):
                val = get_run_expectancy(bs, outs)
                assert val >= 0.0


# ─────────────────────────────────────────────────────────────────
# compute_leverage_index — edge cases
# ─────────────────────────────────────────────────────────────────

class TestComputeLeverageIndexEdgeCases:
    def test_all_base_states_outs_compute(self) -> None:
        """All 24 base-out states should compute without error."""
        base_states = ["000", "100", "010", "001", "110", "101", "011", "111"]
        for bs in base_states:
            for outs in range(3):
                li = compute_leverage_index(bs, outs, inning=5, score_diff=0)
                assert li > 0

    def test_li_positive(self) -> None:
        li = compute_leverage_index("000", 0, inning=1, score_diff=0)
        assert li > 0

    def test_late_inning_higher_than_early(self) -> None:
        li_early = compute_leverage_index("100", 1, inning=1, score_diff=1)
        li_late = compute_leverage_index("100", 1, inning=8, score_diff=1)
        assert li_late > li_early

    def test_close_game_higher_than_blowout(self) -> None:
        li_close = compute_leverage_index("000", 0, inning=9, score_diff=1)
        li_blowout = compute_leverage_index("000", 0, inning=9, score_diff=8)
        assert li_close > li_blowout

    def test_extra_innings_factor_1_5(self) -> None:
        """inning > 9 should use factor 1.5; inning 1 uses 1.0."""
        li_inning1 = compute_leverage_index("000", 0, inning=1, score_diff=5)
        li_extra = compute_leverage_index("000", 0, inning=10, score_diff=5)
        # extra_innings / inning_1 ≈ 1.5
        assert li_extra / li_inning1 == pytest.approx(1.5, abs=0.01)

    def test_score_diff_exactly_2_uses_130_factor(self) -> None:
        li_2 = compute_leverage_index("000", 0, inning=5, score_diff=2)
        li_3 = compute_leverage_index("000", 0, inning=5, score_diff=3)
        # score_diff=2 → factor 1.3, score_diff=3 → factor 1.0
        assert li_2 / li_3 == pytest.approx(1.3, abs=0.01)
