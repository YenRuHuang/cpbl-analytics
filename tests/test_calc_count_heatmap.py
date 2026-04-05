"""Tests for scripts/calc_count_heatmap.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.calc_count_heatmap import aggregate_counts


@pytest.fixture()
def counts_dir(tmp_path: Path) -> Path:
    """Create fake player count JSON files for aggregation."""
    year_dir = tmp_path / "dashboard" / "static" / "api" / "analysis" / "counts" / "2025"
    year_dir.mkdir(parents=True)

    # Player 1
    p1 = {
        "by_count": [
            {"count": "0-0", "pa": 50, "result_hit": 15, "result_k": 5, "result_bb": 0},
            {"count": "0-1", "pa": 30, "result_hit": 6, "result_k": 8, "result_bb": 0},
            {"count": "3-2", "pa": 20, "result_hit": 4, "result_k": 6, "result_bb": 5},
        ]
    }
    (year_dir / "player1.json").write_text(json.dumps(p1))

    # Player 2
    p2 = {
        "by_count": [
            {"count": "0-0", "pa": 40, "result_hit": 10, "result_k": 4, "result_bb": 0},
            {"count": "0-1", "pa": 25, "result_hit": 5, "result_k": 7, "result_bb": 0},
            {"count": "1-0", "pa": 15, "result_hit": 5, "result_k": 1, "result_bb": 0},
        ]
    }
    (year_dir / "player2.json").write_text(json.dumps(p2))

    return tmp_path


class TestAggregateCounts:
    def test_aggregates_pa(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)

        counts_map = {c["count"]: c for c in result["counts"]}
        # 0-0: 50 + 40 = 90
        assert counts_map["0-0"]["pa"] == 90
        # 0-1: 30 + 25 = 55
        assert counts_map["0-1"]["pa"] == 55

    def test_ba_calculation(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)

        counts_map = {c["count"]: c for c in result["counts"]}
        # 0-0: hits = 15+10=25, pa=90 → BA=25/90=0.278
        assert counts_map["0-0"]["ba"] == round(25 / 90, 3)

    def test_k_pct_and_bb_pct(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)

        counts_map = {c["count"]: c for c in result["counts"]}
        # 3-2: only p1 → pa=20, k=6, bb=5
        assert counts_map["3-2"]["k_pct"] == round(6 / 20, 3)
        assert counts_map["3-2"]["bb_pct"] == round(5 / 20, 3)

    def test_total_players_count(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)
        assert result["total_players"] == 2

    def test_follows_counts_order(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)

        output_counts = [c["count"] for c in result["counts"]]
        expected_order = [c for c in mod.COUNTS_ORDER if c in output_counts]
        assert output_counts == expected_order

    def test_balls_and_strikes_parsed(self, counts_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(counts_dir))
        result = aggregate_counts(2025)

        for c in result["counts"]:
            assert c["balls"] == int(c["count"][0])
            assert c["strikes"] == int(c["count"][2])

    def test_no_files_raises_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_count_heatmap as mod

        monkeypatch.setattr(mod, "BASE_DIR", str(tmp_path))
        # Create directory but no files
        (tmp_path / "dashboard" / "static" / "api" / "analysis" / "counts" / "2025").mkdir(parents=True)

        with pytest.raises(FileNotFoundError):
            aggregate_counts(2025)
