"""Pydantic v2 response models for CPBL Analytics API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

# ─────────────────────────────────────────────
# Generic wrapper
# ─────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Paginated response envelope."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[Any]
    total: int
    page: int
    per_page: int


# ─────────────────────────────────────────────
# Core entities
# ─────────────────────────────────────────────

class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: str
    game_date: str
    year: int
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    venue: str | None
    kind_code: str
    source: str


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: str
    name_zh: str
    name_en: str | None
    team: str | None
    position: str | None
    bats: str | None
    throws: str | None


# ─────────────────────────────────────────────
# LOB%
# ─────────────────────────────────────────────

class LobResponse(BaseModel):
    """Pitcher LOB% leaderboard entry — mirrors LobResult dataclass."""

    player_id: str
    player_name: str
    team: str
    games: int
    ip: float
    h: int
    bb: int
    r: int
    hr: int
    lob_pct: float | None
    league_avg: float
    is_lucky: bool
    is_unlucky: bool
    sample_note: str


class BatterLobResponse(BaseModel):
    """Batter LOB analysis entry."""

    player_id: str
    player_name: str
    games: int
    ab: int | None
    h: int | None
    rbi: int | None
    lob: int | None
    left_behind_lob: int | None
    lob_per_game: float


# ─────────────────────────────────────────────
# Count Splits
# ─────────────────────────────────────────────

class CountStatsResponse(BaseModel):
    """Stats for a single count bucket (e.g. '0-0', '2-1')."""

    count: str
    pa: int
    result_hit: int
    result_out: int
    result_bb: int
    result_k: int
    ba: float | None
    k_pct: float | None
    bb_pct: float | None


class CountSplitResponse(BaseModel):
    """Full count-split result for one batter."""

    player_id: str
    player_name: str
    role: str
    total_pa: int
    ahead: CountStatsResponse | None
    behind: CountStatsResponse | None
    even: CountStatsResponse | None
    two_strike: CountStatsResponse | None
    first_pitch_swing_pct: float | None
    by_count: list[CountStatsResponse]


# ─────────────────────────────────────────────
# Pitcher Fatigue
# ─────────────────────────────────────────────

class FatigueBucketResponse(BaseModel):
    """Performance stats for a 15-pitch bucket."""

    bucket_label: str          # e.g. "1-15", "16-30"
    pitch_start: int
    pitch_end: int
    batters_faced: int
    hits: int
    walks: int
    strikeouts: int
    ba_against: float | None
    k_pct: float | None
    bb_pct: float | None


class PitcherFatigueResponse(BaseModel):
    """Pitcher fatigue curve across pitch count buckets."""

    pitcher_id: str
    name: str
    buckets: list[FatigueBucketResponse]
    fatigue_threshold: int | None    # pitch count where decline detected; None if not found


# ─────────────────────────────────────────────
# Leverage / Clutch
# ─────────────────────────────────────────────

class LeverageResponse(BaseModel):
    """Clutch / leverage stats for one batter — mirrors LeverageStats fields."""

    player_id: str
    player_name: str
    team: str | None
    total_pa: int
    clutch_pa: int               # PA where LI > threshold
    overall_ba: float | None
    clutch_ba: float | None
    overall_ops: float | None
    clutch_ops: float | None
    clutch_score: float | None   # clutch_ba - overall_ba (positive = clutch)
    leverage_threshold: float
    sample_note: str
