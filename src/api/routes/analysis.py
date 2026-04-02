"""Analysis endpoints — LOB%, Count Splits, Pitcher Fatigue, Clutch/Leverage."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.responses import (
    BatterLobResponse,
    CountSplitResponse,
    CountStatsResponse,
    FatigueBucketResponse,
    LeverageResponse,
    LobResponse,
    PitcherFatigueResponse,
)
from src.db.engine import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ─────────────────────────────────────────────
# LOB% — Pitcher leaderboard
# ─────────────────────────────────────────────

@router.get("/lob", response_model=list[LobResponse])
def lob_leaderboard(
    year: int = Query(default=2025, description="Season year"),
    min_ip: float = Query(default=5.0, ge=0, description="Minimum innings pitched"),
) -> list[LobResponse]:
    from src.analysis.lob_pct import compute_lob_leaderboard

    with get_db() as db:
        results = compute_lob_leaderboard(db, year=year, min_ip=min_ip)

    return [
        LobResponse(
            player_id=r.player_id, player_name=r.player_name, team=r.team,
            games=r.games, ip=r.ip, h=r.h, bb=r.bb, r=r.r, hr=r.hr,
            lob_pct=r.lob_pct, league_avg=r.league_avg,
            is_lucky=r.is_lucky, is_unlucky=r.is_unlucky, sample_note=r.sample_note,
        )
        for r in results
    ]


# ─────────────────────────────────────────────
# LOB% — Batter perspective
# ─────────────────────────────────────────────

@router.get("/lob/batters", response_model=list[BatterLobResponse])
def batter_lob(
    year: int = Query(default=2025, description="Season year"),
    min_pa: int = Query(default=10, ge=1),
) -> list[BatterLobResponse]:
    from src.analysis.lob_pct import compute_batter_lob

    with get_db() as db:
        results = compute_batter_lob(db, year=year, min_pa=min_pa)

    return [
        BatterLobResponse(
            player_id=r["player_id"], player_name=r["player_name"],
            games=r["games"], ab=r.get("ab"), h=r.get("h"), rbi=r.get("rbi"),
            lob=r.get("lob"), left_behind_lob=r.get("left_behind_lob"),
            lob_per_game=r["lob_per_game"],
        )
        for r in results
    ]


# ─────────────────────────────────────────────
# Count Splits
# ─────────────────────────────────────────────

def _count_stats_to_response(cs) -> CountStatsResponse | None:  # type: ignore[return]
    if cs is None:
        return None
    return CountStatsResponse(
        count=cs.count, pa=cs.pa,
        result_hit=cs.result_hit, result_out=cs.result_out,
        result_bb=cs.result_bb, result_k=cs.result_k,
        ba=cs.ba, k_pct=cs.k_pct, bb_pct=cs.bb_pct,
    )


@router.get("/count-splits/{batter_id}", response_model=CountSplitResponse)
def count_splits(
    batter_id: str,
    year: int = Query(default=2025, description="Season year"),
) -> CountSplitResponse:
    from src.analysis.count_splits import compute_batter_count_splits

    with get_db() as db:
        result = compute_batter_count_splits(db, batter_id=batter_id, year=year)

    if result is None:
        raise HTTPException(status_code=404, detail=f"No count-split data for '{batter_id}' in {year}")

    return CountSplitResponse(
        player_id=result.player_id, player_name=result.player_name,
        role=result.role, total_pa=result.total_pa,
        ahead=_count_stats_to_response(result.ahead),
        behind=_count_stats_to_response(result.behind),
        even=_count_stats_to_response(result.even),
        two_strike=_count_stats_to_response(result.two_strike),
        first_pitch_swing_pct=result.first_pitch_swing_pct,
        by_count=[_count_stats_to_response(c) for c in result.by_count],  # type: ignore[misc]
    )


# ─────────────────────────────────────────────
# Pitcher Fatigue — matches PitcherFatigueResult / FatigueBucket
# ─────────────────────────────────────────────

def _fatigue_result_to_response(r) -> PitcherFatigueResponse:
    return PitcherFatigueResponse(
        pitcher_id=r.pitcher_id, year=r.year,
        total_pitches=r.total_pitches, games_analyzed=r.games_analyzed,
        overall_ba_against=r.overall_ba_against, overall_k_pct=r.overall_k_pct,
        overall_bb_pct=r.overall_bb_pct,
        fatigue_threshold_pitch=r.fatigue_threshold_pitch,
        buckets=[
            FatigueBucketResponse(
                bucket_index=b.bucket_index, pitch_start=b.pitch_start, pitch_end=b.pitch_end,
                batters_faced=b.batters_faced, hits=b.hits, walks=b.walks, strikeouts=b.strikeouts,
                ba_against=b.ba_against, k_pct=b.k_pct, bb_pct=b.bb_pct,
                is_fatigue_point=b.is_fatigue_point,
            )
            for b in r.buckets
        ],
        sample_note=r.sample_note,
    )


@router.get("/pitcher-fatigue/{pitcher_id}", response_model=PitcherFatigueResponse)
def pitcher_fatigue(
    pitcher_id: str,
    year: int = Query(default=2025, description="Season year"),
) -> PitcherFatigueResponse:
    from src.analysis.pitcher_fatigue import compute_pitcher_fatigue

    with get_db() as db:
        result = compute_pitcher_fatigue(db, pitcher_id=pitcher_id, year=year)

    if result is None:
        raise HTTPException(status_code=404, detail=f"No fatigue data for '{pitcher_id}' in {year}")

    return _fatigue_result_to_response(result)


@router.get("/pitcher-fatigue", response_model=list[PitcherFatigueResponse])
def pitcher_fatigue_leaderboard(
    year: int = Query(default=2025, description="Season year"),
    min_ip: float = Query(default=20.0, ge=0, description="Minimum innings pitched"),
) -> list[PitcherFatigueResponse]:
    from src.analysis.pitcher_fatigue import compute_fatigue_leaderboard

    with get_db() as db:
        results = compute_fatigue_leaderboard(db, year=year, min_ip=min_ip)

    return [_fatigue_result_to_response(r) for r in results]


# ─────────────────────────────────────────────
# Clutch / Leverage — matches LeverageStats
# ─────────────────────────────────────────────

def _leverage_to_response(r) -> LeverageResponse:
    return LeverageResponse(
        player_id=r.player_id, player_name=r.player_name,
        total_pa=r.total_pa, high_leverage_pa=r.high_leverage_pa,
        high_li_ba=r.high_li_ba, overall_ba=r.overall_ba,
        clutch_score=r.clutch_score, high_li_ops=r.high_li_ops,
        sample_note=r.sample_note,
    )


@router.get("/clutch/{batter_id}", response_model=LeverageResponse)
def batter_clutch(
    batter_id: str,
    year: int = Query(default=2025, description="Season year"),
) -> LeverageResponse:
    from src.analysis.leverage import compute_batter_clutch

    with get_db() as db:
        result = compute_batter_clutch(db, batter_id=batter_id, year=year)

    if result is None:
        raise HTTPException(status_code=404, detail=f"No leverage data for '{batter_id}' in {year}")

    return _leverage_to_response(result)


@router.get("/clutch", response_model=list[LeverageResponse])
def clutch_leaderboard(
    year: int = Query(default=2025, description="Season year"),
    min_pa: int = Query(default=30, ge=1),
) -> list[LeverageResponse]:
    from src.analysis.leverage import compute_clutch_leaderboard

    with get_db() as db:
        results = compute_clutch_leaderboard(db, year=year, min_pa=min_pa)

    return [_leverage_to_response(r) for r in results]
