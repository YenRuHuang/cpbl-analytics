"""Tests for scripts/calc_rolling_woba.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def rolling_db(tmp_path: Path) -> Path:
    """Create temp DB with enough PA for rolling wOBA calculation."""
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

    # 10 games spread across the season
    for i in range(10):
        conn.execute(
            "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"g{i}", f"2025-{4 + i // 3:02d}-{1 + i % 28:02d}", 2025,
             "T1", "T2", 5, 3, "V1", "A", "rebas"),
        )

    conn.execute("INSERT INTO players VALUES (?,?,?,?)", ("b1", "測試打者", "Test", "T1"))
    conn.execute("INSERT INTO batter_box VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("g0", "b1", "T1", 4, 2, 1, 1, 1, 1, 0, 0, 0, 0, "rebas"))

    # 120 PA for b1: mix of results
    pa_seq = 0
    results = (["single"] * 30 + ["double"] * 8 + ["homer"] * 5 +
               ["walk"] * 12 + ["strikeout"] * 25 + ["out"] * 40)
    for i, r in enumerate(results):
        game_idx = i // 12  # ~12 PA per game
        pa_seq += 1
        conn.execute(
            "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"g{game_idx}", 1, "top", pa_seq, "b1", "p1",
             "000", 0, r, "000", 1, 0, 0, "rebas"),
        )

    # b2: only 30 PA → below MIN_PA (100)
    conn.execute("INSERT INTO players VALUES (?,?,?,?)", ("b2", "不合格", "Unq", "T2"))
    for i in range(30):
        pa_seq += 1
        conn.execute(
            "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("g0", 1, "top", pa_seq, "b2", "p1",
             "000", 0, "out", "000", 1, 0, 0, "rebas"),
        )

    conn.commit()
    conn.close()
    return db_path


class TestCalcRollingWoba:
    def test_produces_output(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "rolling.json"))

        result = mod.calc_rolling_woba()
        assert "meta" in result
        assert "players" in result

    def test_unqualified_excluded(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "rolling.json"))

        result = mod.calc_rolling_woba()
        pids = [p["player_id"] for p in result["players"]]
        assert "b2" not in pids

    def test_rolling_series_length(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "rolling.json"))

        result = mod.calc_rolling_woba()
        player = result["players"][0]
        # 120 PA, window=50 → 120-50+1 = 71 data points
        assert len(player["series"]) == player["total_pa"] - mod.WINDOW + 1

    def test_woba_in_valid_range(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "rolling.json"))

        result = mod.calc_rolling_woba()
        for player in result["players"]:
            for pt in player["series"]:
                assert 0 <= pt["woba"] <= 2.0  # wOBA theoretically maxes around 2.0
                assert 0 <= pt["avg"] <= 1.0

    def test_output_file_written(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        out = tmp_path / "out" / "rolling.json"
        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(out))

        mod.calc_rolling_woba()
        assert out.exists()

    def test_sorted_by_pa_descending(self, rolling_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_rolling_woba as mod

        monkeypatch.setattr(mod, "DB_PATH", str(rolling_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "rolling.json"))

        result = mod.calc_rolling_woba()
        pas = [p["total_pa"] for p in result["players"]]
        assert pas == sorted(pas, reverse=True)
