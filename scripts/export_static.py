"""Export all API data as static JSON files for Cloudflare Pages deployment."""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import text

from src.db.engine import get_db, init_db
from src.analysis.lob_pct import compute_lob_leaderboard
from src.analysis.leverage import compute_clutch_leaderboard
from src.analysis.pitcher_fatigue import compute_fatigue_leaderboard, compute_pitcher_fatigue
from src.analysis.count_splits import compute_batter_count_splits as compute_batter_splits

OUT = Path("dashboard/static/api")


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, default=str))
    print(f"  {path} ({path.stat().st_size:,} bytes)")


def export_year(year: int) -> None:
    print(f"\n=== Exporting {year} ===")
    db = get_db().__enter__()

    # 1. LOB% leaderboard
    lob = compute_lob_leaderboard(db, year=year, min_ip=5.0)
    lob_data = [
        {
            "player_id": r.player_id, "player_name": r.player_name,
            "team": r.team, "games": r.games, "ip": r.ip,
            "h": r.h, "bb": r.bb, "hbp": r.hbp, "r": r.r, "hr": r.hr,
            "lob_pct": r.lob_pct, "league_avg": r.league_avg,
            "is_lucky": r.is_lucky, "is_unlucky": r.is_unlucky,
            "sample_note": r.sample_note,
        }
        for r in lob
    ]
    _write(OUT / f"analysis/lob_{year}.json", lob_data)

    # 2. Clutch leaderboard — 補 team 欄位（從 batter_box 查）
    clutch = compute_clutch_leaderboard(db, year=year, min_pa=50)
    team_map = {
        row.player_id: row.team
        for row in db.execute(text("""
            SELECT bb.player_id, MAX(bb.team) AS team
            FROM batter_box bb
            JOIN games g ON bb.game_id = g.game_id
            WHERE g.year = :year
            GROUP BY bb.player_id
        """), {"year": year}).fetchall()
    }
    clutch_data = [
        {
            "player_id": r.player_id, "player_name": r.player_name,
            "team": team_map.get(r.player_id, ""),
            "total_pa": r.total_pa, "high_leverage_pa": r.high_leverage_pa,
            "high_li_ba": r.high_li_ba, "overall_ba": r.overall_ba,
            "clutch_score": r.clutch_score, "sample_note": r.sample_note,
        }
        for r in clutch
        if r.high_li_ba is not None
    ]
    _write(OUT / f"analysis/clutch_{year}.json", clutch_data)

    # 3. Fatigue leaderboard + individual pitcher data
    fatigue = compute_fatigue_leaderboard(db, year=year, min_ip=20.0)
    fatigue_data = [
        {
            "pitcher_id": r.pitcher_id,
            "player_name": r.pitcher_id.replace("cpbl_", ""),
            "team": r.team, "year": r.year,
            "total_ip": r.total_ip, "games": r.games,
            "total_pitches": r.total_pitches,
            "fatigue_threshold_pitch": r.fatigue_threshold_pitch,
            "overall_ba_against": r.overall_ba_against,
            "overall_k_pct": r.overall_k_pct, "sample_note": r.sample_note,
        }
        for r in fatigue
    ]
    _write(OUT / f"analysis/fatigue_{year}.json", fatigue_data)

    # Individual pitcher fatigue
    pitcher_ids = {r.pitcher_id for r in fatigue}
    for pid in sorted(pitcher_ids):
        detail = compute_pitcher_fatigue(db, pid, year)
        if detail is None:
            continue
        detail_data = {
            "pitcher_id": detail.pitcher_id, "year": detail.year,
            "total_pitches": detail.total_pitches,
            "games_analyzed": detail.games_analyzed,
            "overall_ba_against": detail.overall_ba_against,
            "overall_k_pct": detail.overall_k_pct,
            "overall_bb_pct": detail.overall_bb_pct,
            "fatigue_threshold_pitch": detail.fatigue_threshold_pitch,
            "sample_note": detail.sample_note,
            "buckets": [
                {
                    "bucket_index": b.bucket_index,
                    "pitch_start": b.pitch_start, "pitch_end": b.pitch_end,
                    "batters_faced": b.batters_faced, "hits": b.hits,
                    "walks": b.walks, "strikeouts": b.strikeouts,
                    "ba_against": b.ba_against, "k_pct": b.k_pct,
                    "bb_pct": b.bb_pct, "is_fatigue_point": b.is_fatigue_point,
                }
                for b in detail.buckets
            ],
        }
        safe_pid = pid.replace("/", "_")
        _write(OUT / f"analysis/fatigue/{year}/{safe_pid}.json", detail_data)

    # 4. Count splits — export for all batters with >= 50 PA
    batter_rows = db.execute(text("""
        SELECT pa.batter_id, COUNT(*) AS pa_count
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        WHERE g.year = :year
        GROUP BY pa.batter_id
        HAVING COUNT(*) >= 50
    """), {"year": year}).fetchall()

    for row in batter_rows:
        splits = compute_batter_splits(db, row.batter_id, year)
        if splits is None:
            continue
        splits_data = {
            "player_id": splits.player_id, "player_name": splits.player_name,
            "role": splits.role, "total_pa": splits.total_pa,
            "ahead": _situation(splits.ahead),
            "behind": _situation(splits.behind),
            "even": _situation(splits.even),
            "two_strike": _situation(splits.two_strike),
            "first_pitch_swing_pct": splits.first_pitch_swing_pct,
            "by_count": [_situation(s) for s in splits.by_count],
        }
        safe_bid = row.batter_id.replace("/", "_")
        _write(OUT / f"analysis/counts/{year}/{safe_bid}.json", splits_data)

    print(f"\nDone: {len(lob_data)} LOB, {len(clutch_data)} clutch, "
          f"{len(fatigue_data)} fatigue, {len(batter_rows)} count splits")


def _situation(s) -> dict:
    if s is None:
        return {}
    return {
        "count": s.count, "pa": s.pa,
        "result_hit": s.result_hit, "result_out": s.result_out,
        "result_bb": s.result_bb, "result_k": s.result_k,
        "ba": s.ba, "k_pct": s.k_pct, "bb_pct": s.bb_pct,
    }


if __name__ == "__main__":
    init_db()
    export_year(2025)
    export_year(2026)
    print("\n✅ All static JSON exported")
