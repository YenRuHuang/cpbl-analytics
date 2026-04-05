"""Tests for scripts/calc_half_splits.py — calc_half_stats (unit) + calc_half_splits (integration)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.calc_half_splits import calc_half_stats

# ─────────────────────────────────────────────────────────────────
# calc_half_stats — unit tests (pure function, no DB needed)
# ─────────────────────────────────────────────────────────────────


class TestCalcHalfStats:
    def test_basic_stats(self) -> None:
        raw = {"pa": 100, "bb": 10, "hbp": 2, "sac": 3, "s1b": 20, "s2b": 5, "s3b": 1, "hr": 3, "so": 15}
        result = calc_half_stats(raw)

        ab = 100 - 10 - 2 - 3  # 85
        h = 20 + 5 + 1 + 3  # 29
        assert result["pa"] == 100
        assert result["ab"] == ab
        assert result["h"] == h
        assert result["avg"] == round(h / ab, 3)

    def test_obp_calculation(self) -> None:
        raw = {"pa": 50, "bb": 5, "hbp": 1, "sac": 0, "s1b": 10, "s2b": 2, "s3b": 0, "hr": 1, "so": 8}
        result = calc_half_stats(raw)

        ab = 50 - 5 - 1 - 0  # 44
        h = 10 + 2 + 0 + 1  # 13
        obp_denom = ab + 5 + 1  # 50
        expected_obp = (h + 5 + 1) / obp_denom
        assert result["obp"] == round(expected_obp, 3)

    def test_slg_calculation(self) -> None:
        raw = {"pa": 80, "bb": 0, "hbp": 0, "sac": 0, "s1b": 10, "s2b": 5, "s3b": 2, "hr": 3, "so": 10}
        result = calc_half_stats(raw)

        ab = 80
        total_bases = 10 + 2 * 5 + 3 * 2 + 4 * 3  # 10+10+6+12 = 38
        assert result["slg"] == round(total_bases / ab, 3)

    def test_woba_calculation(self) -> None:
        raw = {"pa": 60, "bb": 5, "hbp": 1, "sac": 0, "s1b": 10, "s2b": 3, "s3b": 1, "hr": 2, "so": 8}
        result = calc_half_stats(raw)

        woba_num = 0.69 * 5 + 0.72 * 1 + 0.87 * 10 + 1.22 * 3 + 1.56 * 1 + 1.95 * 2
        denom = (60 - 5 - 1 - 0) + 5 + 1  # ab + bb + hbp = 60
        assert result["woba"] == round(woba_num / denom, 4)

    def test_babip_excludes_hr_and_k(self) -> None:
        raw = {"pa": 50, "bb": 0, "hbp": 0, "sac": 0, "s1b": 10, "s2b": 3, "s3b": 0, "hr": 2, "so": 10}
        result = calc_half_stats(raw)

        h = 10 + 3 + 0 + 2  # 15
        babip_denom = 50 - 10 - 2  # ab - K - HR = 38
        expected = (h - 2) / babip_denom
        assert result["babip"] == round(expected, 3)

    def test_zero_ab_returns_zero(self) -> None:
        """All PA are walks — AB=0."""
        raw = {"pa": 10, "bb": 10, "hbp": 0, "sac": 0, "s1b": 0, "s2b": 0, "s3b": 0, "hr": 0, "so": 0}
        result = calc_half_stats(raw)
        assert result["avg"] == 0
        assert result["slg"] == 0

    def test_babip_none_when_denom_zero(self) -> None:
        """All AB are HR or K — BABIP denominator = 0."""
        raw = {"pa": 10, "bb": 0, "hbp": 0, "sac": 0, "s1b": 0, "s2b": 0, "s3b": 0, "hr": 5, "so": 5}
        result = calc_half_stats(raw)
        assert result["babip"] is None

    def test_ops_is_obp_plus_slg(self) -> None:
        raw = {"pa": 100, "bb": 10, "hbp": 2, "sac": 0, "s1b": 20, "s2b": 5, "s3b": 1, "hr": 3, "so": 15}
        result = calc_half_stats(raw)
        assert result["ops"] == round(result["obp"] + result["slg"], 3)


# ─────────────────────────────────────────────────────────────────
# calc_half_splits — integration tests
# ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def splits_db(tmp_path: Path) -> Path:
    """Create temp DB with PA data spanning both halves of 2025."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    conn.execute("""CREATE TABLE games (
        game_id TEXT PRIMARY KEY, game_date TEXT, year INTEGER,
        home_team TEXT, away_team TEXT, home_score INTEGER, away_score INTEGER,
        venue TEXT, kind_code TEXT, source TEXT
    )""")
    conn.execute("""CREATE TABLE plate_appearances (
        game_id TEXT, inning INTEGER, top_bottom TEXT, pa_seq INTEGER,
        batter_id TEXT, pitcher_id TEXT, runners_before TEXT, outs_before INTEGER,
        result TEXT, runners_after TEXT, outs_after INTEGER, runs_scored INTEGER,
        rbi INTEGER, source TEXT
    )""")
    conn.execute("""CREATE TABLE players (
        player_id TEXT PRIMARY KEY, name_zh TEXT, name_en TEXT, team TEXT
    )""")
    conn.execute("""CREATE TABLE batter_box (
        game_id TEXT, player_id TEXT, team TEXT, ab INTEGER, h INTEGER,
        bb INTEGER, so INTEGER, rbi INTEGER, r INTEGER, hr INTEGER,
        sb INTEGER, lob INTEGER, left_behind_lob INTEGER, source TEXT
    )""")

    # Games: 2 first-half, 2 second-half
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("g1", "2025-04-01", 2025, "T1", "T2", 5, 3, "V1", "A", "rebas"),
        ("g2", "2025-06-01", 2025, "T1", "T2", 4, 2, "V1", "A", "rebas"),
        ("g3", "2025-08-01", 2025, "T1", "T2", 3, 4, "V1", "A", "rebas"),
        ("g4", "2025-09-01", 2025, "T1", "T2", 6, 1, "V1", "A", "rebas"),
    ])

    conn.execute("INSERT INTO players VALUES (?, ?, ?, ?)", ("b1", "測試打者", "Test Batter", "T1"))

    # 60 PA in first half (g1+g2), 60 PA in second half (g3+g4)
    pa_seq = 0
    results_first = ["single"] * 15 + ["double"] * 3 + ["homer"] * 2 + ["walk"] * 5 + ["strikeout"] * 10 + ["out"] * 25
    results_second = ["single"] * 20 + ["double"] * 5 + ["homer"] * 3 + ["walk"] * 3 + ["strikeout"] * 8 + ["out"] * 21

    for game_id, results in [("g1", results_first[:30]), ("g2", results_first[30:]),
                              ("g3", results_second[:30]), ("g4", results_second[30:])]:
        for r in results:
            pa_seq += 1
            conn.execute(
                "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (game_id, 1, "top", pa_seq, "b1", "p1", "000", 0, r, "000", 1, 0, 0, "rebas"),
            )

    # batter_box for team lookup
    conn.executemany("INSERT INTO batter_box VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("g1", "b1", "T1", 4, 2, 1, 1, 1, 1, 0, 0, 0, 0, "rebas"),
        ("g2", "b1", "T1", 4, 2, 1, 1, 1, 1, 0, 0, 0, 0, "rebas"),
    ])

    conn.commit()
    conn.close()
    return db_path


class TestCalcHalfSplits:
    def test_produces_output(self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_half_splits as mod

        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "splits.json"))

        result = mod.calc_half_splits()
        assert "meta" in result
        assert "batters" in result
        assert result["meta"]["qualified_batters"] >= 1

    def test_delta_woba_computed(self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_half_splits as mod

        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "splits.json"))

        result = mod.calc_half_splits()
        batter = result["batters"][0]
        assert "delta" in batter
        assert "woba" in batter["delta"]
        assert "ops" in batter["delta"]
        assert "avg" in batter["delta"]

    def test_delta_is_second_minus_first(
        self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import scripts.calc_half_splits as mod

        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "splits.json"))

        result = mod.calc_half_splits()
        b = result["batters"][0]
        expected_delta = round(b["second_half"]["woba"] - b["first_half"]["woba"], 4)
        assert b["delta"]["woba"] == expected_delta

    def test_team_from_batter_box(self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_half_splits as mod

        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "splits.json"))

        result = mod.calc_half_splits()
        assert result["batters"][0]["team"] == "T1"

    def test_output_file_written(self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_half_splits as mod

        out = tmp_path / "out" / "splits.json"
        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(out))

        mod.calc_half_splits()
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["meta"]["year"] == 2025

    def test_min_pa_filter(self, splits_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_half_splits as mod

        monkeypatch.setattr(mod, "DB_PATH", str(splits_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "splits.json"))
        monkeypatch.setattr(mod, "MIN_PA_HALF", 999)

        result = mod.calc_half_splits()
        assert result["meta"]["qualified_batters"] == 0
