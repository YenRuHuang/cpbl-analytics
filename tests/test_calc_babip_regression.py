"""Tests for scripts/calc_babip_regression.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def babip_db(tmp_path: Path) -> Path:
    """Create temp DB with PA data for BABIP regression tests."""
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

    # 2 first-half games + 2 second-half games
    conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("g1", "2025-04-01", 2025, "T1", "T2", 5, 3, "V1", "A", "rebas"),
        ("g2", "2025-06-01", 2025, "T1", "T2", 4, 2, "V1", "A", "rebas"),
        ("g3", "2025-08-01", 2025, "T1", "T2", 3, 4, "V1", "A", "rebas"),
        ("g4", "2025-09-01", 2025, "T1", "T2", 6, 1, "V1", "A", "rebas"),
    ])

    # 3 batters with different profiles
    conn.executemany("INSERT INTO players VALUES (?,?,?,?)", [
        ("b1", "高BABIP", "High BABIP", "T1"),
        ("b2", "低BABIP", "Low BABIP", "T1"),
        ("b3", "不合格", "Unqualified", "T2"),
    ])

    conn.executemany("INSERT INTO batter_box VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("g1", "b1", "T1", 4, 2, 1, 1, 1, 1, 0, 0, 0, 0, "rebas"),
        ("g1", "b2", "T1", 4, 1, 0, 2, 0, 0, 0, 0, 0, 0, "rebas"),
    ])

    pa_seq = 0

    # b1: High BABIP first half (lots of singles), avg drops second half
    for game_id, results in [
        ("g1", ["single"] * 12 + ["double"] * 2 + ["strikeout"] * 5 + ["out"] * 11),
        ("g2", ["single"] * 10 + ["homer"] * 1 + ["walk"] * 3 + ["strikeout"] * 6 + ["out"] * 10),
        ("g3", ["single"] * 5 + ["double"] * 1 + ["walk"] * 3 + ["strikeout"] * 8 + ["out"] * 13),
        ("g4", ["single"] * 6 + ["homer"] * 1 + ["walk"] * 2 + ["strikeout"] * 7 + ["out"] * 14),
    ]:
        for r in results:
            pa_seq += 1
            conn.execute(
                "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (game_id, 1, "top", pa_seq, "b1", "p1", "000", 0, r, "000", 1, 0, 0, "rebas"),
            )

    # b2: Low BABIP first half, improves second half
    for game_id, results in [
        ("g1", ["single"] * 4 + ["strikeout"] * 10 + ["out"] * 16),
        ("g2", ["single"] * 5 + ["walk"] * 2 + ["strikeout"] * 8 + ["out"] * 15),
        ("g3", ["single"] * 10 + ["double"] * 3 + ["walk"] * 2 + ["strikeout"] * 5 + ["out"] * 10),
        ("g4", ["single"] * 8 + ["double"] * 2 + ["homer"] * 1 + ["walk"] * 3 + ["strikeout"] * 6 + ["out"] * 10),
    ]:
        for r in results:
            pa_seq += 1
            conn.execute(
                "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (game_id, 1, "top", pa_seq, "b2", "p1", "000", 0, r, "000", 1, 0, 0, "rebas"),
            )

    # b3: Only 10 PA total → should not qualify
    for r in ["single"] * 3 + ["out"] * 7:
        pa_seq += 1
        conn.execute(
            "INSERT INTO plate_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("g1", 1, "top", pa_seq, "b3", "p1", "000", 0, r, "000", 1, 0, 0, "rebas"),
        )

    conn.commit()
    conn.close()
    return db_path


class TestCalcBabipRegression:
    def test_produces_output(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "babip.json"))

        result = mod.calc_babip_regression()
        assert "meta" in result
        assert "batters" in result

    def test_unqualified_batters_excluded(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "babip.json"))

        result = mod.calc_babip_regression()
        pids = [b["player_id"] for b in result["batters"]]
        assert "b3" not in pids

    def test_regression_computed(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "babip.json"))

        result = mod.calc_babip_regression()
        reg = result["meta"]["regression"]
        if reg is not None:
            assert "slope" in reg
            assert "intercept" in reg
            assert "r_squared" in reg
            assert 0 <= reg["r_squared"] <= 1

    def test_avg_change_is_second_minus_first(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "babip.json"))

        result = mod.calc_babip_regression()
        for b in result["batters"]:
            expected = round(b["second_half"]["avg"] - b["first_half"]["avg"], 3)
            assert b["avg_change"] == expected

    def test_output_file_written(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        out = tmp_path / "out" / "babip.json"
        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(out))

        mod.calc_babip_regression()
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["meta"]["year"] == 2025

    def test_sorted_by_first_half_babip_desc(self, babip_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_babip_regression as mod

        monkeypatch.setattr(mod, "DB_PATH", str(babip_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "babip.json"))

        result = mod.calc_babip_regression()
        babips = [b["first_half"]["babip"] for b in result["batters"]]
        assert babips == sorted(babips, reverse=True)
