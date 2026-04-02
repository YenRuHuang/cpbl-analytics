"""Shared pytest fixtures for CPBL Analytics tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

_MIGRATION_SQL = Path(__file__).parent.parent / "src" / "db" / "migrations" / "001_initial.sql"


@pytest.fixture()
def db_session() -> Session:
    """In-memory SQLite with all tables created; rolls back after each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # SQLite in-memory doesn't support WAL or scripts via executescript in the same way,
    # so we execute each statement individually, skipping PRAGMA journal_mode=WAL.
    sql = _MIGRATION_SQL.read_text()
    with engine.connect() as conn:
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.upper().startswith("PRAGMA JOURNAL_MODE"):
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
        conn.commit()

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def seed_data(db_session: Session) -> Session:
    """Insert sample games, batter_box, pitcher_box, plate_appearances, pitch_events."""

    # ── Games ────────────────────────────────────────────────────
    db_session.execute(text("""
        INSERT INTO games (game_id, game_date, year, home_team, away_team,
                           home_score, away_score, venue, kind_code, source)
        VALUES
            ('test_g1', '2026-04-01', 2026, 'AAA', 'AJL', 5, 3, '洲際', 'A', 'rebas'),
            ('test_g2', '2026-04-02', 2026, 'ACN', 'ADD', 2, 7, '台南', 'A', 'rebas')
    """))

    # ── Batter box ───────────────────────────────────────────────
    db_session.execute(text("""
        INSERT INTO batter_box (game_id, player_id, team, ab, h, bb, so, rbi, r, hr, sb, lob, left_behind_lob, source)
        VALUES
            ('test_g1', 'cpbl_batter_1', 'AAA', 4, 2, 1, 1, 2, 1, 1, 0, 2, 1, 'rebas'),
            ('test_g1', 'cpbl_batter_2', 'AJL', 4, 1, 0, 2, 0, 1, 0, 1, 3, 2, 'rebas'),
            ('test_g2', 'cpbl_batter_1', 'AAA', 3, 0, 2, 1, 0, 0, 0, 0, 1, 1, 'rebas')
    """))

    # ── Pitcher box ──────────────────────────────────────────────
    db_session.execute(text("""
        INSERT INTO pitcher_box (game_id, player_id, team, ip, pitch_count, h, r, er, bb, so, hr, source)
        VALUES
            ('test_g1', 'cpbl_pitcher_1', 'AAA', 6.0, 90, 5, 3, 3, 2, 6, 1, 'rebas'),
            ('test_g2', 'cpbl_pitcher_1', 'AAA', 7.0, 105, 4, 2, 2, 1, 7, 0, 'rebas')
    """))

    # ── Plate appearances ────────────────────────────────────────
    # game_id, inning, top_bottom, pa_seq, batter_id, pitcher_id,
    # runners_before, outs_before, result, runners_after, outs_after, runs_scored, rbi
    db_session.execute(text("""
        INSERT INTO plate_appearances
            (game_id, inning, top_bottom, pa_seq, batter_id, pitcher_id,
             runners_before, outs_before, result, runners_after, outs_after, runs_scored, rbi, source)
        VALUES
            ('test_g1', 1, 'top', 1, 'cpbl_batter_2', 'cpbl_pitcher_1', '000', 0, '1B',  '100', 0, 0, 0, 'rebas'),
            ('test_g1', 1, 'top', 2, 'cpbl_batter_2', 'cpbl_pitcher_1', '100', 0, 'out', '100', 1, 0, 0, 'rebas'),
            ('test_g1', 1, 'top', 3, 'cpbl_batter_2', 'cpbl_pitcher_1', '100', 1, 'BB',  '110', 1, 0, 0, 'rebas'),
            ('test_g1', 2, 'top', 4, 'cpbl_batter_2', 'cpbl_pitcher_1', '000', 0, 'HR',  '000', 0, 1, 1, 'rebas'),
            ('test_g1', 2, 'top', 5, 'cpbl_batter_2', 'cpbl_pitcher_1', '000', 0, 'out', '000', 1, 0, 0, 'rebas'),
            ('test_g1', 7, 'top', 6, 'cpbl_batter_2', 'cpbl_pitcher_1', '111', 1, '2B',  '011', 1, 2, 2, 'rebas'),
            ('test_g1', 9, 'top', 7, 'cpbl_batter_2', 'cpbl_pitcher_1', '000', 0, 'out', '000', 1, 0, 0, 'rebas'),
            ('test_g2', 1, 'top', 1, 'cpbl_batter_1', 'cpbl_pitcher_1', '000', 0, '2B',  '010', 0, 0, 0, 'rebas'),
            ('test_g2', 3, 'top', 2, 'cpbl_batter_1', 'cpbl_pitcher_1', '100', 0, 'out', '100', 1, 0, 0, 'rebas'),
            ('test_g2', 8, 'top', 3, 'cpbl_batter_1', 'cpbl_pitcher_1', '111', 1, '1B',  '111', 1, 1, 1, 'rebas')
    """))

    # ── Pitch events ──────────────────────────────────────────────
    # 30 pitches spread across the two games
    pitches = [
        # game_id, inning, top_bottom, pa_seq, pitch_seq, pitcher_id, batter_id,
        # pitch_result, balls_before, strikes_before, pitch_number_game
        ("test_g1", 1, "top", 1, 1, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      0, 0,  1),
        ("test_g1", 1, "top", 1, 2, "cpbl_pitcher_1", "cpbl_batter_2", "in_play",   1, 0,  2),
        ("test_g1", 1, "top", 2, 1, "cpbl_pitcher_1", "cpbl_batter_2", "strike",    0, 0,  3),
        ("test_g1", 1, "top", 2, 2, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      0, 1,  4),
        ("test_g1", 1, "top", 2, 3, "cpbl_pitcher_1", "cpbl_batter_2", "in_play_out",1,1,  5),
        ("test_g1", 1, "top", 3, 1, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      0, 0,  6),
        ("test_g1", 1, "top", 3, 2, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      1, 0,  7),
        ("test_g1", 1, "top", 3, 3, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      2, 0,  8),
        ("test_g1", 1, "top", 3, 4, "cpbl_pitcher_1", "cpbl_batter_2", "walk",      3, 0,  9),
        ("test_g1", 2, "top", 4, 1, "cpbl_pitcher_1", "cpbl_batter_2", "homer",     0, 0, 10),
        ("test_g1", 2, "top", 5, 1, "cpbl_pitcher_1", "cpbl_batter_2", "strike",    0, 0, 11),
        ("test_g1", 2, "top", 5, 2, "cpbl_pitcher_1", "cpbl_batter_2", "strikeout", 0, 1, 12),
        ("test_g1", 7, "top", 6, 1, "cpbl_pitcher_1", "cpbl_batter_2", "ball",      0, 0, 13),
        ("test_g1", 7, "top", 6, 2, "cpbl_pitcher_1", "cpbl_batter_2", "in_play",   1, 0, 14),
        ("test_g1", 9, "top", 7, 1, "cpbl_pitcher_1", "cpbl_batter_2", "in_play_out",0,0, 15),
        # game 2 — higher pitch numbers to test fatigue buckets
        ("test_g2", 1, "top", 1, 1, "cpbl_pitcher_1", "cpbl_batter_1", "ball",      0, 0, 16),
        ("test_g2", 1, "top", 1, 2, "cpbl_pitcher_1", "cpbl_batter_1", "in_play",   1, 0, 17),
        ("test_g2", 3, "top", 2, 1, "cpbl_pitcher_1", "cpbl_batter_1", "strike",    0, 0, 18),
        ("test_g2", 3, "top", 2, 2, "cpbl_pitcher_1", "cpbl_batter_1", "in_play_out",0,1, 19),
        ("test_g2", 8, "top", 3, 1, "cpbl_pitcher_1", "cpbl_batter_1", "hit",       0, 0, 20),
        # Extra pitches to push into second bucket (pitch_number_game 16+)
        ("test_g2", 8, "top", 3, 2, "cpbl_pitcher_1", "cpbl_batter_1", "single",    0, 0, 21),
        ("test_g2", 8, "top", 3, 3, "cpbl_pitcher_1", "cpbl_batter_1", "in_play_out",1,0, 22),
        ("test_g2", 8, "top", 3, 4, "cpbl_pitcher_1", "cpbl_batter_1", "strikeout", 2, 0, 23),
        ("test_g2", 8, "top", 3, 5, "cpbl_pitcher_1", "cpbl_batter_1", "walk",      3, 0, 24),
        ("test_g2", 8, "top", 3, 6, "cpbl_pitcher_1", "cpbl_batter_1", "hit",       0, 0, 25),
        ("test_g2", 8, "top", 3, 7, "cpbl_pitcher_1", "cpbl_batter_1", "single",    0, 0, 26),
        ("test_g2", 8, "top", 3, 8, "cpbl_pitcher_1", "cpbl_batter_1", "hit",       1, 0, 27),
        ("test_g2", 8, "top", 3, 9, "cpbl_pitcher_1", "cpbl_batter_1", "strikeout", 2, 0, 28),
        ("test_g2", 8, "top", 3,10, "cpbl_pitcher_1", "cpbl_batter_1", "in_play_out",3,0, 29),
        ("test_g2", 8, "top", 3,11, "cpbl_pitcher_1", "cpbl_batter_1", "walk",      0, 0, 30),
    ]
    for p in pitches:
        db_session.execute(text("""
            INSERT INTO pitch_events
                (game_id, inning, top_bottom, pa_seq, pitch_seq, pitcher_id, batter_id,
                 pitch_result, balls_before, strikes_before, pitch_number_game, source)
            VALUES
                (:game_id, :inning, :top_bottom, :pa_seq, :pitch_seq, :pitcher_id,
                 :batter_id, :pitch_result, :balls_before, :strikes_before,
                 :pitch_number_game, 'rebas')
        """), {
            "game_id": p[0], "inning": p[1], "top_bottom": p[2],
            "pa_seq": p[3], "pitch_seq": p[4], "pitcher_id": p[5],
            "batter_id": p[6], "pitch_result": p[7], "balls_before": p[8],
            "strikes_before": p[9], "pitch_number_game": p[10],
        })

    db_session.commit()
    return db_session
