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
# Pitcher Fatigue — matches FatigueBucket / PitcherFatigueResult
# ─────────────────────────────────────────────

class FatigueBucketResponse(BaseModel):
    bucket_index: int
    pitch_start: int
    pitch_end: int
    batters_faced: int
    hits: int
    walks: int
    strikeouts: int
    ba_against: float | None
    k_pct: float | None
    bb_pct: float | None
    is_fatigue_point: bool


class PitcherFatigueResponse(BaseModel):
    pitcher_id: str
    year: int
    total_pitches: int
    games_analyzed: int
    overall_ba_against: float | None
    overall_k_pct: float | None
    overall_bb_pct: float | None
    fatigue_threshold_pitch: int | None
    buckets: list[FatigueBucketResponse]
    sample_note: str


# ─────────────────────────────────────────────
# Leverage / Clutch — matches LeverageStats
# ─────────────────────────────────────────────

class LeverageResponse(BaseModel):
    player_id: str
    player_name: str
    total_pa: int
    high_leverage_pa: int
    high_li_ba: float | None
    overall_ba: float | None
    clutch_score: float | None
    high_li_ops: float | None
    sample_note: str
