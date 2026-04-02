"""Rebas Open Data JSON → SQLite loader.

Data source: https://github.com/rebas-tw/rebas.tw-open-data
License: ODC-By (attribution required)

Each JSON file contains one game with nested sections:
    game, batterBox, pitcherBox, PA, event, runner
"""

import json
import logging
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─── Download ────────────────────────────────────────────────────────────────

REBAS_REPO_URL = "https://github.com/rebas-tw/rebas.tw-open-data.git"


def download_rebas_data(target_dir: str | Path) -> Path:
    """Clone or pull the Rebas Open Data repo into target_dir.

    Returns the resolved path to the data directory.
    Falls back to plain directory scan if git is unavailable.
    """
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    repo_dir = target / "rebas.tw-open-data"

    if repo_dir.exists():
        logger.info("Rebas repo already exists at %s — pulling latest", repo_dir)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("git pull failed: %s", result.stderr.strip())
    else:
        logger.info("Cloning Rebas Open Data repo into %s", repo_dir)
        result = subprocess.run(
            ["git", "clone", "--depth=1", REBAS_REPO_URL, str(repo_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("git clone failed: %s", result.stderr.strip())
            raise RuntimeError(f"Failed to clone Rebas repo: {result.stderr.strip()}")

    logger.info("Rebas data available at %s", repo_dir)
    return repo_dir


# ─── Field extraction helpers ────────────────────────────────────────────────

def _safe_int(val: object, default: int = 0) -> int:
    try:
        return int(val or default)
    except (TypeError, ValueError):
        return default


def _safe_float(val: object, default: float = 0.0) -> float:
    try:
        return float(val or default)
    except (TypeError, ValueError):
        return default


def _runners_to_str(runner_list: list[dict]) -> str:
    """Encode runner positions as a compact string, e.g. '1__', '_2_', '123'."""
    bases = ["_", "_", "_"]
    for r in runner_list:
        base = _safe_int(r.get("base") or r.get("beforeBase") or r.get("startBase"), 0)
        if 1 <= base <= 3:
            bases[base - 1] = str(base)
    return "".join(bases)


# ─── Per-section parsers ─────────────────────────────────────────────────────

def _insert_game(db: Session, raw: dict, filepath: Path) -> str | None:
    """Parse game-level info and insert into games table. Returns game_id."""
    game_section = raw.get("game") or raw.get("Game") or {}

    # Flexible field name mapping — Rebas uses camelCase
    game_id: str = (
        str(game_section.get("gameId") or game_section.get("id") or "")
        or filepath.stem
    )
    game_date: str = str(
        game_section.get("gameDate") or game_section.get("date") or ""
    )[:10]
    year: int = _safe_int(game_date[:4]) if game_date else 0
    home_team: str = str(game_section.get("homeTeam") or game_section.get("home") or "")
    away_team: str = str(game_section.get("awayTeam") or game_section.get("away") or "")
    home_score: int = _safe_int(game_section.get("homeScore") or game_section.get("homeRuns"))
    away_score: int = _safe_int(game_section.get("awayScore") or game_section.get("awayRuns"))
    venue: str = str(game_section.get("venue") or game_section.get("stadium") or "")

    if not game_id:
        logger.warning("Cannot determine game_id from %s", filepath)
        return None

    db.execute(
        text("""
            INSERT OR IGNORE INTO games
                (game_id, game_date, year, home_team, away_team,
                 home_score, away_score, venue, source)
            VALUES
                (:gid, :date, :year, :home, :away,
                 :hs, :as_, :venue, 'rebas')
        """),
        {
            "gid": game_id, "date": game_date, "year": year,
            "home": home_team, "away": away_team,
            "hs": home_score, "as_": away_score,
            "venue": venue,
        },
    )
    return game_id


def _insert_batter_box(db: Session, game_id: str, raw: dict) -> int:
    """Insert batter box rows. Returns count inserted."""
    rows: list[dict] = (
        raw.get("batterBox") or raw.get("BatterBox") or raw.get("hitterBox") or []
    )
    if not isinstance(rows, list):
        return 0

    count = 0
    for row in rows:
        player_id = str(row.get("playerId") or row.get("id") or row.get("playerName") or "")
        if not player_id:
            continue

        # Upsert player record if we have a name
        name = str(row.get("playerName") or row.get("name") or player_id)
        db.execute(
            text("""
                INSERT OR IGNORE INTO players (player_id, name_zh)
                VALUES (:pid, :name)
            """),
            {"pid": player_id, "name": name},
        )

        team = str(row.get("team") or row.get("teamName") or "")
        db.execute(
            text("""
                INSERT OR IGNORE INTO batter_box
                    (game_id, player_id, team, ab, h, bb, so, rbi, r, hr, sb,
                     lob, left_behind_lob, source)
                VALUES
                    (:gid, :pid, :team, :ab, :h, :bb, :so, :rbi, :r, :hr, :sb,
                     :lob, :lblob, 'rebas')
            """),
            {
                "gid": game_id, "pid": player_id, "team": team,
                "ab": _safe_int(row.get("ab") or row.get("atBat")),
                "h": _safe_int(row.get("h") or row.get("hit")),
                "bb": _safe_int(row.get("bb") or row.get("walk")),
                "so": _safe_int(row.get("so") or row.get("strikeOut") or row.get("k")),
                "rbi": _safe_int(row.get("rbi")),
                "r": _safe_int(row.get("r") or row.get("run")),
                "hr": _safe_int(row.get("hr") or row.get("homeRun")),
                "sb": _safe_int(row.get("sb") or row.get("stolenBase")),
                "lob": _safe_int(row.get("lob") or row.get("leftOnBase")),
                "lblob": _safe_int(row.get("leftBehindLob") or row.get("leftBehindLOB")),
            },
        )
        count += 1
    return count


def _insert_pitcher_box(db: Session, game_id: str, raw: dict) -> int:
    """Insert pitcher box rows. Returns count inserted."""
    rows: list[dict] = (
        raw.get("pitcherBox") or raw.get("PitcherBox") or []
    )
    if not isinstance(rows, list):
        return 0

    count = 0
    for row in rows:
        player_id = str(row.get("playerId") or row.get("id") or row.get("playerName") or "")
        if not player_id:
            continue

        name = str(row.get("playerName") or row.get("name") or player_id)
        db.execute(
            text("""
                INSERT OR IGNORE INTO players (player_id, name_zh)
                VALUES (:pid, :name)
            """),
            {"pid": player_id, "name": name},
        )

        team = str(row.get("team") or row.get("teamName") or "")
        db.execute(
            text("""
                INSERT OR IGNORE INTO pitcher_box
                    (game_id, player_id, team, ip, pitch_count, h, r, er, bb, so, hr, source)
                VALUES
                    (:gid, :pid, :team, :ip, :pc, :h, :r, :er, :bb, :so, :hr, 'rebas')
            """),
            {
                "gid": game_id, "pid": player_id, "team": team,
                "ip": _safe_float(row.get("ip") or row.get("inningPitched")),
                "pc": _safe_int(row.get("pitchCount") or row.get("np") or row.get("numberOfPitches")),
                "h": _safe_int(row.get("h") or row.get("hit")),
                "r": _safe_int(row.get("r") or row.get("run")),
                "er": _safe_int(row.get("er") or row.get("earnedRun")),
                "bb": _safe_int(row.get("bb") or row.get("walk")),
                "so": _safe_int(row.get("so") or row.get("strikeOut") or row.get("k")),
                "hr": _safe_int(row.get("hr") or row.get("homeRun")),
            },
        )
        count += 1
    return count


def _insert_plate_appearances(db: Session, game_id: str, raw: dict) -> int:
    """Insert plate appearance rows. Returns count inserted."""
    rows: list[dict] = raw.get("PA") or raw.get("pa") or raw.get("plateAppearance") or []
    if not isinstance(rows, list):
        return 0

    count = 0
    for row in rows:
        inning = _safe_int(row.get("inning") or row.get("inn"))
        top_bottom = str(row.get("topBottom") or row.get("half") or "top")
        pa_seq = _safe_int(row.get("paSeq") or row.get("seq") or row.get("paNumber"))
        batter_id = str(row.get("batterId") or row.get("hitterId") or row.get("batterName") or "")
        pitcher_id = str(row.get("pitcherId") or row.get("pitcherName") or "")

        if not batter_id or not pitcher_id:
            continue

        runners_raw = row.get("runnersBefore") or row.get("runners") or []
        runners_before = (
            _runners_to_str(runners_raw)
            if isinstance(runners_raw, list)
            else str(runners_raw or "___")
        )
        runners_after_raw = row.get("runnersAfter") or []
        runners_after = (
            _runners_to_str(runners_after_raw)
            if isinstance(runners_after_raw, list)
            else str(runners_after_raw or "___")
        )

        db.execute(
            text("""
                INSERT OR IGNORE INTO plate_appearances
                    (game_id, inning, top_bottom, pa_seq, batter_id, pitcher_id,
                     runners_before, outs_before, result, runners_after, outs_after,
                     runs_scored, rbi, source)
                VALUES
                    (:gid, :inn, :tb, :seq, :bat, :pit,
                     :rbef, :obef, :result, :raft, :oaft,
                     :runs, :rbi, 'rebas')
            """),
            {
                "gid": game_id, "inn": inning, "tb": top_bottom, "seq": pa_seq,
                "bat": batter_id, "pit": pitcher_id,
                "rbef": runners_before,
                "obef": _safe_int(row.get("outsBefore") or row.get("outs")),
                "result": str(row.get("result") or row.get("paResult") or ""),
                "raft": runners_after,
                "oaft": _safe_int(row.get("outsAfter")),
                "runs": _safe_int(row.get("runsScored") or row.get("runs")),
                "rbi": _safe_int(row.get("rbi")),
            },
        )
        count += 1
    return count


def _insert_pitch_events(
    db: Session, game_id: str, raw: dict
) -> int:
    """Insert pitch event rows with computed pitch_number_game. Returns count inserted."""
    rows: list[dict] = (
        raw.get("event") or raw.get("Event")
        or raw.get("pitchEvent") or raw.get("pitchEvents")
        or []
    )
    if not isinstance(rows, list):
        return 0

    # Compute pitch_number_game: per-pitcher sequential pitch counter within game
    pitcher_pitch_counter: dict[str, int] = {}

    count = 0
    for row in rows:
        inning = _safe_int(row.get("inning") or row.get("inn"))
        top_bottom = str(row.get("topBottom") or row.get("half") or "top")
        pa_seq = _safe_int(row.get("paSeq") or row.get("paNumber"))
        pitch_seq = _safe_int(row.get("pitchSeq") or row.get("seq") or row.get("pitchNumber"))
        pitcher_id = str(row.get("pitcherId") or row.get("pitcherName") or "")
        batter_id = str(row.get("batterId") or row.get("hitterId") or row.get("batterName") or "")

        if not pitcher_id or not batter_id:
            continue

        # Increment per-pitcher pitch counter
        pitcher_pitch_counter[pitcher_id] = pitcher_pitch_counter.get(pitcher_id, 0) + 1
        pitch_number_game = pitcher_pitch_counter[pitcher_id]

        db.execute(
            text("""
                INSERT OR IGNORE INTO pitch_events
                    (game_id, inning, top_bottom, pa_seq, pitch_seq,
                     pitcher_id, batter_id, pitch_result,
                     balls_before, strikes_before, pitch_number_game, source)
                VALUES
                    (:gid, :inn, :tb, :pa, :ps,
                     :pit, :bat, :result,
                     :balls, :strikes, :pnum, 'rebas')
            """),
            {
                "gid": game_id, "inn": inning, "tb": top_bottom,
                "pa": pa_seq, "ps": pitch_seq,
                "pit": pitcher_id, "bat": batter_id,
                "result": str(row.get("pitchResult") or row.get("result") or ""),
                "balls": _safe_int(row.get("ballsBefore") or row.get("balls")),
                "strikes": _safe_int(row.get("strikesBefore") or row.get("strikes")),
                "pnum": pitch_number_game,
            },
        )
        count += 1
    return count


# ─── Public API ──────────────────────────────────────────────────────────────

def load_game_file(db: Session, filepath: Path) -> str | None:
    """Parse one Rebas JSON file and insert into all relevant tables.

    Returns game_id on success, None if skipped (already exists) or invalid.
    Uses INSERT OR IGNORE for idempotency.
    """
    try:
        raw: dict = json.loads(filepath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Cannot read %s: %s", filepath, exc)
        return None

    if not isinstance(raw, dict):
        logger.warning("Unexpected JSON structure in %s (expected dict)", filepath)
        return None

    try:
        game_id = _insert_game(db, raw, filepath)
        if game_id is None:
            return None

        # Check if game already existed (INSERT OR IGNORE → rowcount 0 means skip)
        existing = db.execute(
            text("SELECT COUNT(*) FROM batter_box WHERE game_id = :gid"),
            {"gid": game_id},
        ).scalar()
        if existing and existing > 0:
            logger.debug("Game %s already loaded — skipping box data", game_id)
            return None

        _insert_batter_box(db, game_id, raw)
        _insert_pitcher_box(db, game_id, raw)
        _insert_plate_appearances(db, game_id, raw)
        _insert_pitch_events(db, game_id, raw)

        logger.debug("Loaded game %s from %s", game_id, filepath.name)
        return game_id

    except Exception as exc:
        logger.error("Error loading %s: %s", filepath, exc, exc_info=True)
        raise


def load_all_games(
    db: Session, data_dir: str | Path
) -> dict[str, int]:
    """Walk data_dir recursively and load all JSON files.

    Returns stats dict: {"loaded": N, "skipped": N, "errors": N}
    """
    data_path = Path(data_dir).resolve()
    if not data_path.exists():
        logger.warning("Data directory does not exist: %s", data_path)
        return {"loaded": 0, "skipped": 0, "errors": 0}

    json_files = sorted(data_path.rglob("*.json"))
    logger.info("Found %d JSON files in %s", len(json_files), data_path)

    stats = {"loaded": 0, "skipped": 0, "errors": 0}

    for filepath in json_files:
        try:
            result = load_game_file(db, filepath)
            if result is not None:
                stats["loaded"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            logger.error("Failed to load %s: %s", filepath, exc)
            stats["errors"] += 1

    logger.info(
        "Rebas load complete — loaded=%d skipped=%d errors=%d",
        stats["loaded"], stats["skipped"], stats["errors"],
    )
    return stats
