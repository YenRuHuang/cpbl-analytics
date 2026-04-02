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
    year: int = Query(default=2026, description="Season year"),
    min_ip: float = Query(default=5.0, ge=0, description="Minimum innings pitched"),
) -> list[LobResponse]:
    """Pitcher LOB% leaderboard for the given season."""
    from src.analysis.lob_pct import compute_lob_leaderboard

    with get_db() as db:
        results = compute_lob_leaderboard(db, year=year, min_ip=min_ip)

    return [
        LobResponse(
            player_id=r.player_id,
            player_name=r.player_name,
            team=r.team,
            games=r.games,
            ip=r.ip,
            h=r.h,
            bb=r.bb,
            r=r.r,
            hr=r.hr,
            lob_pct=r.lob_pct,
            league_avg=r.league_avg,
            is_lucky=r.is_lucky,
            is_unlucky=r.is_unlucky,
            sample_note=r.sample_note,
        )
        for r in results
    ]


# ─────────────────────────────────────────────
# LOB% — Batter perspective
# ─────────────────────────────────────────────

@router.get("/lob/batters", response_model=list[BatterLobResponse])
def batter_lob(
    year: int = Query(default=2026, description="Season year"),
    min_pa: int = Query(default=10, ge=1, description="Minimum plate appearances"),
) -> list[BatterLobResponse]:
    """Batter LOB analysis (runners left on base per game)."""
    from src.analysis.lob_pct import compute_batter_lob

    with get_db() as db:
        results = compute_batter_lob(db, year=year, min_pa=min_pa)

    return [
        BatterLobResponse(
            player_id=r["player_id"],
            player_name=r["player_name"],
            games=r["games"],
            ab=r.get("ab"),
            h=r.get("h"),
            rbi=r.get("rbi"),
            lob=r.get("lob"),
            left_behind_lob=r.get("left_behind_lob"),
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
        count=cs.count,
        pa=cs.pa,
        result_hit=cs.result_hit,
        result_out=cs.result_out,
        result_bb=cs.result_bb,
        result_k=cs.result_k,
        ba=cs.ba,
        k_pct=cs.k_pct,
        bb_pct=cs.bb_pct,
    )


@router.get("/count-splits/{batter_id}", response_model=CountSplitResponse)
def count_splits(
    batter_id: str,
    year: int = Query(default=2026, description="Season year"),
) -> CountSplitResponse:
    """Count-split breakdown for a single batter."""
    from src.analysis.count_splits import compute_batter_count_splits

    with get_db() as db:
        result = compute_batter_count_splits(db, batter_id=batter_id, year=year)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No count-split data for batter '{batter_id}' in {year}",
        )

    return CountSplitResponse(
        player_id=result.player_id,
        player_name=result.player_name,
        role=result.role,
        total_pa=result.total_pa,
        ahead=_count_stats_to_response(result.ahead),
        behind=_count_stats_to_response(result.behind),
        even=_count_stats_to_response(result.even),
        two_strike=_count_stats_to_response(result.two_strike),
        first_pitch_swing_pct=result.first_pitch_swing_pct,
        by_count=[_count_stats_to_response(c) for c in result.by_count],  # type: ignore[misc]
    )


# ─────────────────────────────────────────────
# Pitcher Fatigue
# ─────────────────────────────────────────────

@router.get("/pitcher-fatigue/{pitcher_id}", response_model=PitcherFatigueResponse)
def pitcher_fatigue(
    pitcher_id: str,
    year: int = Query(default=2026, description="Season year"),
) -> PitcherFatigueResponse:
    """Fatigue curve (15-pitch buckets) for a single pitcher."""
    from src.analysis.pitcher_fatigue import compute_pitcher_fatigue  # type: ignore[import]

    with get_db() as db:
        result = compute_pitcher_fatigue(db, pitcher_id=pitcher_id, year=year)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No fatigue data for pitcher '{pitcher_id}' in {year}",
        )

    buckets = [
        FatigueBucketResponse(
            bucket_label=b.bucket_label,
            pitch_start=b.pitch_start,
            pitch_end=b.pitch_end,
            batters_faced=b.batters_faced,
            hits=b.hits,
            walks=b.walks,
            strikeouts=b.strikeouts,
            ba_against=b.ba_against,
            k_pct=b.k_pct,
            bb_pct=b.bb_pct,
        )
        for b in result.buckets
    ]

    return PitcherFatigueResponse(
        pitcher_id=result.pitcher_id,
        name=result.name,
        buckets=buckets,
        fatigue_threshold=result.fatigue_threshold,
    )


@router.get("/pitcher-fatigue", response_model=list[PitcherFatigueResponse])
def pitcher_fatigue_leaderboard(
    year: int = Query(default=2026, description="Season year"),
    min_pitches: int = Query(default=100, ge=1, description="Minimum total pitches thrown"),
) -> list[PitcherFatigueResponse]:
    """Fatigue summary leaderboard for all qualifying pitchers."""
    from src.analysis.pitcher_fatigue import compute_fatigue_leaderboard  # type: ignore[import]

    with get_db() as db:
        results = compute_fatigue_leaderboard(db, year=year, min_pitches=min_pitches)

    return [
        PitcherFatigueResponse(
            pitcher_id=r.pitcher_id,
            name=r.name,
            buckets=[
                FatigueBucketResponse(
                    bucket_label=b.bucket_label,
                    pitch_start=b.pitch_start,
                    pitch_end=b.pitch_end,
                    batters_faced=b.batters_faced,
                    hits=b.hits,
                    walks=b.walks,
                    strikeouts=b.strikeouts,
                    ba_against=b.ba_against,
                    k_pct=b.k_pct,
                    bb_pct=b.bb_pct,
                )
                for b in r.buckets
            ],
            fatigue_threshold=r.fatigue_threshold,
        )
        for r in results
    ]


# ─────────────────────────────────────────────
# Clutch / Leverage
# ─────────────────────────────────────────────

@router.get("/clutch/{batter_id}", response_model=LeverageResponse)
def batter_clutch(
    batter_id: str,
    year: int = Query(default=2026, description="Season year"),
    leverage_threshold: float = Query(default=1.5, ge=0.1, description="LI threshold for 'clutch' PA"),
) -> LeverageResponse:
    """Clutch score for a single batter (high-leverage vs overall performance)."""
    from src.analysis.leverage import compute_batter_clutch  # type: ignore[import]

    with get_db() as db:
        result = compute_batter_clutch(
            db,
            batter_id=batter_id,
            year=year,
            leverage_threshold=leverage_threshold,
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No leverage data for batter '{batter_id}' in {year}",
        )

    return LeverageResponse(
        player_id=result.player_id,
        player_name=result.player_name,
        team=result.team,
        total_pa=result.total_pa,
        clutch_pa=result.clutch_pa,
        overall_ba=result.overall_ba,
        clutch_ba=result.clutch_ba,
        overall_ops=result.overall_ops,
        clutch_ops=result.clutch_ops,
        clutch_score=result.clutch_score,
        leverage_threshold=result.leverage_threshold,
        sample_note=result.sample_note,
    )


@router.get("/clutch", response_model=list[LeverageResponse])
def clutch_leaderboard(
    year: int = Query(default=2026, description="Season year"),
    min_pa: int = Query(default=30, ge=1, description="Minimum plate appearances"),
    leverage_threshold: float = Query(default=1.5, ge=0.1, description="LI threshold for 'clutch' PA"),
) -> list[LeverageResponse]:
    """Clutch leaderboard for all qualifying batters."""
    from src.analysis.leverage import compute_clutch_leaderboard  # type: ignore[import]

    with get_db() as db:
        results = compute_clutch_leaderboard(
            db,
            year=year,
            min_pa=min_pa,
            leverage_threshold=leverage_threshold,
        )

    return [
        LeverageResponse(
            player_id=r.player_id,
            player_name=r.player_name,
            team=r.team,
            total_pa=r.total_pa,
            clutch_pa=r.clutch_pa,
            overall_ba=r.overall_ba,
            clutch_ba=r.clutch_ba,
            overall_ops=r.overall_ops,
            clutch_ops=r.clutch_ops,
            clutch_score=r.clutch_score,
            leverage_threshold=r.leverage_threshold,
            sample_note=r.sample_note,
        )
        for r in results
    ]
