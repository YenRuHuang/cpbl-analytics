-- CPBL Analytics — Initial Schema
-- 雙資料源：Rebas Open Data + CPBL 官網公開資料

PRAGMA journal_mode=WAL;

-- ═══════════════════════════════════════════
-- 核心表
-- ═══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS games (
    game_id       TEXT PRIMARY KEY,
    game_date     DATE NOT NULL,
    year          INTEGER NOT NULL,
    home_team     TEXT NOT NULL,
    away_team     TEXT NOT NULL,
    home_score    INTEGER,
    away_score    INTEGER,
    venue         TEXT,
    kind_code     TEXT DEFAULT 'A',
    cpbl_game_sno INTEGER,
    source        TEXT NOT NULL DEFAULT 'rebas',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_date, home_team, away_team)
);

CREATE TABLE IF NOT EXISTS players (
    player_id     TEXT PRIMARY KEY,
    name_zh       TEXT NOT NULL,
    name_en       TEXT,
    team          TEXT,
    position      TEXT,
    bats          TEXT,
    throws        TEXT,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_mapping (
    cpbl_name       TEXT NOT NULL,
    rebas_player_id TEXT NOT NULL,
    confidence      REAL DEFAULT 1.0,
    PRIMARY KEY (cpbl_name, rebas_player_id)
);

CREATE TABLE IF NOT EXISTS plate_appearances (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES games(game_id),
    inning        INTEGER NOT NULL,
    top_bottom    TEXT NOT NULL,
    pa_seq        INTEGER NOT NULL,
    batter_id     TEXT NOT NULL,
    pitcher_id    TEXT NOT NULL,
    runners_before TEXT,
    outs_before   INTEGER NOT NULL,
    result        TEXT NOT NULL,
    runners_after TEXT,
    outs_after    INTEGER NOT NULL,
    runs_scored   INTEGER DEFAULT 0,
    rbi           INTEGER DEFAULT 0,
    source        TEXT NOT NULL DEFAULT 'rebas',
    UNIQUE(game_id, inning, top_bottom, pa_seq)
);

CREATE TABLE IF NOT EXISTS pitch_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id        TEXT NOT NULL REFERENCES games(game_id),
    inning         INTEGER NOT NULL,
    top_bottom     TEXT NOT NULL,
    pa_seq         INTEGER NOT NULL,
    pitch_seq      INTEGER NOT NULL,
    pitcher_id     TEXT NOT NULL,
    batter_id      TEXT NOT NULL,
    pitch_result   TEXT NOT NULL,
    balls_before   INTEGER NOT NULL,
    strikes_before INTEGER NOT NULL,
    pitch_number_game INTEGER,
    source         TEXT NOT NULL DEFAULT 'rebas',
    UNIQUE(game_id, inning, top_bottom, pa_seq, pitch_seq)
);

CREATE TABLE IF NOT EXISTS batter_box (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    player_id       TEXT NOT NULL,
    team            TEXT,
    ab              INTEGER,
    h               INTEGER,
    bb              INTEGER,
    so              INTEGER,
    rbi             INTEGER,
    r               INTEGER,
    hr              INTEGER,
    sb              INTEGER,
    lob             INTEGER,
    left_behind_lob INTEGER,
    source          TEXT NOT NULL DEFAULT 'rebas',
    UNIQUE(game_id, player_id)
);

CREATE TABLE IF NOT EXISTS pitcher_box (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES games(game_id),
    player_id     TEXT NOT NULL,
    team          TEXT,
    ip            REAL,
    pitch_count   INTEGER,
    h             INTEGER,
    r             INTEGER,
    er            INTEGER,
    bb            INTEGER,
    so            INTEGER,
    hr            INTEGER,
    source        TEXT NOT NULL DEFAULT 'rebas',
    UNIQUE(game_id, player_id)
);

-- ═══════════════════════════════════════════
-- 分析快取
-- ═══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS run_expectancy_matrix (
    year          INTEGER NOT NULL,
    base_state    TEXT NOT NULL,
    outs          INTEGER NOT NULL,
    expected_runs REAL NOT NULL,
    sample_size   INTEGER NOT NULL,
    PRIMARY KEY (year, base_state, outs)
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key     TEXT PRIMARY KEY,
    result_json   TEXT NOT NULL,
    computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ttl_seconds   INTEGER DEFAULT 86400
);

-- ═══════════════════════════════════════════
-- 索引
-- ═══════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_year ON games(year);

CREATE INDEX IF NOT EXISTS idx_pa_game ON plate_appearances(game_id);
CREATE INDEX IF NOT EXISTS idx_pa_batter ON plate_appearances(batter_id);
CREATE INDEX IF NOT EXISTS idx_pa_pitcher ON plate_appearances(pitcher_id);
CREATE INDEX IF NOT EXISTS idx_pa_situation ON plate_appearances(outs_before, runners_before);

CREATE INDEX IF NOT EXISTS idx_pitch_game ON pitch_events(game_id);
CREATE INDEX IF NOT EXISTS idx_pitch_pitcher ON pitch_events(pitcher_id);
CREATE INDEX IF NOT EXISTS idx_pitch_count ON pitch_events(pitcher_id, game_id, pitch_number_game);
CREATE INDEX IF NOT EXISTS idx_pitch_balls_strikes ON pitch_events(balls_before, strikes_before);

CREATE INDEX IF NOT EXISTS idx_batter_box_game ON batter_box(game_id);
CREATE INDEX IF NOT EXISTS idx_batter_box_player ON batter_box(player_id);
CREATE INDEX IF NOT EXISTS idx_pitcher_box_game ON pitcher_box(game_id);
CREATE INDEX IF NOT EXISTS idx_pitcher_box_player ON pitcher_box(player_id);
