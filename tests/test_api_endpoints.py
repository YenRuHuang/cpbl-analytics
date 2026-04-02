"""Tests for FastAPI endpoints using TestClient.

The routes use get_db() which points to the real SQLite file.
We monkey-patch src.db.engine.get_db at the module level so the
injection works even when routes import it inside function bodies
(which run in a threadpool where patch() context vars may not propagate).
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import src.api.routes.analysis as _analysis_routes
import src.api.routes.games as _games_routes
import src.api.routes.players as _players_routes
import src.db.engine as _engine_module
from src.api.app import create_app

_MIGRATION_SQL = Path(__file__).parent.parent / "src" / "db" / "migrations" / "001_initial.sql"


# ─────────────────────────────────────────────────────────────────
# Test DB factory — use a named temp file so all connections share it
# ─────────────────────────────────────────────────────────────────

def _make_test_engine(db_path: str):
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    sql = _MIGRATION_SQL.read_text()
    with engine.connect() as conn:
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s and not s.upper().startswith("PRAGMA JOURNAL_MODE"):
                try:
                    conn.execute(text(s))
                except Exception:
                    pass
        conn.commit()
    return engine


def _seed(session: Session) -> None:
    session.execute(text("""
        INSERT INTO games (game_id, game_date, year, home_team, away_team,
                           home_score, away_score, venue, kind_code, source)
        VALUES
            ('api_g1', '2026-04-01', 2026, 'AAA', 'AJL', 5, 3, '洲際', 'A', 'rebas'),
            ('api_g2', '2026-04-02', 2026, 'ACN', 'ADD', 2, 7, '台南', 'A', 'rebas')
    """))
    session.execute(text("""
        INSERT INTO players (player_id, name_zh, name_en, team, position, bats, throws)
        VALUES
            ('cpbl_p1', '王建民', 'Wang Chien-Ming', 'AAA', 'SP', 'R', 'R'),
            ('cpbl_p2', '陳金鋒', 'Chen Chin-Feng',  'AJL', 'RF', 'R', 'R')
    """))
    session.execute(text("""
        INSERT INTO pitcher_box (game_id, player_id, team, ip, pitch_count, h, r, er, bb, so, hr, source)
        VALUES
            ('api_g1', 'cpbl_p1', 'AAA', 6.0, 90, 5, 3, 3, 2, 6, 1, 'rebas'),
            ('api_g2', 'cpbl_p1', 'AAA', 7.0, 95, 4, 2, 2, 1, 7, 0, 'rebas')
    """))
    session.commit()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """TestClient with a temp-file SQLite DB injected by replacing get_db on the module."""
    # Create the temp file path without auto-deleting yet
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    engine = _make_test_engine(db_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    original_get_db = _engine_module.get_db

    @contextmanager
    def _fake_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Seed via a dedicated session
    seed_session = factory()
    _seed(seed_session)
    seed_session.close()

    # Replace get_db at module level for all route modules — visible to all threads.
    # Routes import get_db at module level, so we patch each route module directly.
    _engine_module.get_db = _fake_get_db  # type: ignore[assignment]
    original_players = _players_routes.get_db
    original_games = _games_routes.get_db
    original_analysis = _analysis_routes.get_db
    _players_routes.get_db = _fake_get_db  # type: ignore[assignment]
    _games_routes.get_db = _fake_get_db  # type: ignore[assignment]
    _analysis_routes.get_db = _fake_get_db  # type: ignore[assignment]

    try:
        app = create_app()
        yield TestClient(app)
    finally:
        _engine_module.get_db = original_get_db  # type: ignore[assignment]
        _players_routes.get_db = original_players  # type: ignore[assignment]
        _games_routes.get_db = original_games  # type: ignore[assignment]
        _analysis_routes.get_db = original_analysis  # type: ignore[assignment]
        engine.dispose()
        Path(db_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_json_status_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_service_name(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "cpbl" in data["service"].lower()


# ─────────────────────────────────────────────────────────────────
# /api/players
# ─────────────────────────────────────────────────────────────────

class TestPlayersEndpoint:
    def test_list_players_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/players")
        assert resp.status_code == 200

    def test_list_players_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/players")
        data = resp.json()
        assert isinstance(data, list)

    def test_list_players_has_seeded_data(self, client: TestClient) -> None:
        resp = client.get("/api/players")
        data = resp.json()
        assert len(data) == 2

    def test_player_fields_present(self, client: TestClient) -> None:
        resp = client.get("/api/players")
        player = resp.json()[0]
        assert "player_id" in player
        assert "name_zh" in player

    def test_get_player_by_id_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/players/cpbl_p1")
        assert resp.status_code == 200

    def test_get_player_by_id_correct_data(self, client: TestClient) -> None:
        resp = client.get("/api/players/cpbl_p1")
        data = resp.json()
        assert data["player_id"] == "cpbl_p1"
        assert data["name_zh"] == "王建民"

    def test_get_unknown_player_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/players/nobody_here")
        assert resp.status_code == 404

    def test_filter_by_team(self, client: TestClient) -> None:
        resp = client.get("/api/players?team=AAA")
        data = resp.json()
        assert isinstance(data, list)
        for p in data:
            assert p["team"] == "AAA"


# ─────────────────────────────────────────────────────────────────
# /api/games
# ─────────────────────────────────────────────────────────────────

class TestGamesEndpoint:
    def test_list_games_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/games")
        assert resp.status_code == 200

    def test_list_games_is_paginated(self, client: TestClient) -> None:
        resp = client.get("/api/games")
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data

    def test_list_games_has_seeded_games(self, client: TestClient) -> None:
        resp = client.get("/api/games")
        data = resp.json()
        assert data["total"] == 2

    def test_filter_by_year(self, client: TestClient) -> None:
        resp = client.get("/api/games?year=2026")
        data = resp.json()
        assert data["total"] == 2

    def test_filter_wrong_year_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/games?year=2000")
        data = resp.json()
        assert data["total"] == 0

    def test_get_game_by_id_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/games/api_g1")
        assert resp.status_code == 200

    def test_get_game_by_id_correct_data(self, client: TestClient) -> None:
        resp = client.get("/api/games/api_g1")
        data = resp.json()
        assert data["game_id"] == "api_g1"
        assert data["year"] == 2026

    def test_get_unknown_game_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/games/nonexistent_game")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────
# /api/analysis/lob
# ─────────────────────────────────────────────────────────────────

class TestLobEndpoint:
    def test_lob_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/lob")
        assert resp.status_code == 200

    def test_lob_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/lob")
        data = resp.json()
        assert isinstance(data, list)

    def test_lob_entry_fields(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/lob?min_ip=0")
        data = resp.json()
        if data:
            entry = data[0]
            assert "player_id" in entry
            assert "lob_pct" in entry
            assert "is_lucky" in entry
            assert "is_unlucky" in entry

    def test_lob_with_high_min_ip_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/lob?min_ip=9999")
        data = resp.json()
        assert data == []

    def test_lob_pitcher_in_leaderboard(self, client: TestClient) -> None:
        resp = client.get("/api/analysis/lob?min_ip=0&year=2026")
        data = resp.json()
        player_ids = [e["player_id"] for e in data]
        assert "cpbl_p1" in player_ids
