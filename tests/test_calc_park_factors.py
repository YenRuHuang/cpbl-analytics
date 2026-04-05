"""Tests for scripts/calc_park_factors.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture()
def pf_db(tmp_path: Path) -> Path:
    """Create a temp SQLite DB with game data for park factor tests."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            game_date TEXT, year INTEGER,
            home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            venue TEXT, kind_code TEXT, source TEXT
        )
    """)
    # Team A: high-scoring at home, low-scoring on road → PF > 1
    # Team B: low-scoring at home, high-scoring on road → PF < 1
    games = [
        # Team A home (venue=Stadium_A): 8 runs/game total
        ("g1", "2025-04-01", 2025, "TeamA", "TeamB", 5, 3, "Stadium_A", "A", "rebas"),
        ("g2", "2025-04-02", 2025, "TeamA", "TeamB", 4, 4, "Stadium_A", "A", "rebas"),
        # Team A road: 4 runs/game total
        ("g3", "2025-04-03", 2025, "TeamB", "TeamA", 1, 3, "Stadium_B", "A", "rebas"),
        ("g4", "2025-04-04", 2025, "TeamB", "TeamA", 2, 2, "Stadium_B", "A", "rebas"),
        # Team B home (venue=Stadium_B): 4 runs/game total (from g3, g4)
        # Team B road: 8 runs/game total (from g1, g2)
    ]
    conn.executemany(
        "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)", games
    )
    conn.commit()
    conn.close()
    return db_path


class TestCalcParkFactors:
    def test_team_based_pf(self, pf_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_park_factors as mod

        monkeypatch.setattr(mod, "DB_PATH", str(pf_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "pf.json"))

        result = mod.calc_park_factors()

        assert "team_park_factors" in result
        teams = {r["team"]: r for r in result["team_park_factors"]}

        # TeamA: home RPG = (5+3+4+4)/2=8, road RPG = (1+3+2+2)/2=4 → PF = 8/4 = 2.0
        assert teams["TeamA"]["park_factor"] == 2.0
        assert teams["TeamA"]["home_games"] == 2
        assert teams["TeamA"]["road_games"] == 2

        # TeamB: home RPG = (1+3+2+2)/2=4, road RPG = (5+3+4+4)/2=8 → PF = 4/8 = 0.5
        assert teams["TeamB"]["park_factor"] == 0.5

    def test_venue_based_pf(self, pf_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_park_factors as mod

        monkeypatch.setattr(mod, "DB_PATH", str(pf_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "pf.json"))

        result = mod.calc_park_factors()

        # Only 2 games per venue, threshold is 10, so venue results should be empty
        assert result["venue_park_factors"] == []

    def test_output_file_written(self, pf_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_park_factors as mod

        out_path = tmp_path / "output" / "pf.json"
        monkeypatch.setattr(mod, "DB_PATH", str(pf_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(out_path))

        mod.calc_park_factors()

        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "meta" in data
        assert data["meta"]["year"] == 2025

    def test_sorted_by_pf_descending(self, pf_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_park_factors as mod

        monkeypatch.setattr(mod, "DB_PATH", str(pf_db))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "pf.json"))

        result = mod.calc_park_factors()
        pfs = [r["park_factor"] for r in result["team_park_factors"]]
        assert pfs == sorted(pfs, reverse=True)

    def test_no_games_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.calc_park_factors as mod

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE games (
                game_id TEXT, game_date TEXT, year INTEGER,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                venue TEXT, kind_code TEXT, source TEXT
            )
        """)
        conn.commit()
        conn.close()

        monkeypatch.setattr(mod, "DB_PATH", str(db_path))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "pf.json"))

        result = mod.calc_park_factors()
        assert result["team_park_factors"] == []

    def test_zero_road_rpg_defaults_to_one(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Edge case: if road RPG is 0 (denominator), PF should default to 1.0."""
        import scripts.calc_park_factors as mod

        db_path = tmp_path / "edge.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE games (
                game_id TEXT, game_date TEXT, year INTEGER,
                home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER,
                venue TEXT, kind_code TEXT, source TEXT
            )
        """)
        # TeamA has 0 road RPG (both scores 0 when TeamA is away)
        conn.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("g1", "2025-04-01", 2025, "TeamA", "TeamB", 3, 2, "S_A", "A", "rebas"),
            ("g2", "2025-04-02", 2025, "TeamB", "TeamA", 0, 0, "S_B", "A", "rebas"),
        ])
        conn.commit()
        conn.close()

        monkeypatch.setattr(mod, "DB_PATH", str(db_path))
        monkeypatch.setattr(mod, "OUT_PATH", str(tmp_path / "pf.json"))

        result = mod.calc_park_factors()
        teams = {r["team"]: r for r in result["team_park_factors"]}
        # TeamA: road RPG = (0+0)/1 = 0 → PF defaults to 1.0
        assert teams["TeamA"]["park_factor"] == 1.0
