"""Count Splits 球數分裂 — 打者/投手在不同球數下的表現差異。

分類：
- Ahead（打者有利）：1-0, 2-0, 2-1, 3-0, 3-1
- Behind（投手有利）：0-1, 0-2, 1-2
- Even：0-0, 1-1, 2-2, 3-2
- Two-strike：0-2, 1-2, 2-2, 3-2
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.utils.constants import COUNT_AHEAD, COUNT_BEHIND, COUNT_EVEN, COUNT_TWO_STRIKE


@dataclass(frozen=True)
class CountStats:
    count: str
    pa: int
    result_hit: int
    result_out: int
    result_bb: int
    result_k: int
    ba: float | None
    k_pct: float | None
    bb_pct: float | None


@dataclass(frozen=True)
class CountSplitResult:
    player_id: str
    player_name: str
    role: str                         # 'batter' | 'pitcher'
    total_pa: int
    ahead: CountStats | None
    behind: CountStats | None
    even: CountStats | None
    two_strike: CountStats | None
    first_pitch_swing_pct: float | None
    by_count: list[CountStats]        # 逐 count 細節


def _classify_count(balls: int, strikes: int) -> str:
    """回傳 count 字串 'B-S' 格式。"""
    return f"{balls}-{strikes}"


def _aggregate_counts(rows: list, count_set: set[str]) -> CountStats | None:
    """將特定 count 集合的 rows 聚合。"""
    filtered = [r for r in rows if r["count"] in count_set]
    if not filtered:
        return None

    total_pa = sum(r["pa"] for r in filtered)
    total_hit = sum(r["hits"] for r in filtered)
    total_out = sum(r["outs"] for r in filtered)
    total_bb = sum(r["bb"] for r in filtered)
    total_k = sum(r["k"] for r in filtered)

    ab = total_hit + total_out  # 簡化：AB ≈ hits + outs
    return CountStats(
        count=",".join(sorted(count_set)),
        pa=total_pa,
        result_hit=total_hit,
        result_out=total_out,
        result_bb=total_bb,
        result_k=total_k,
        ba=round(total_hit / ab, 3) if ab > 0 else None,
        k_pct=round(total_k / total_pa, 3) if total_pa > 0 else None,
        bb_pct=round(total_bb / total_pa, 3) if total_pa > 0 else None,
    )


def compute_batter_count_splits(
    db: Session,
    batter_id: str,
    year: int = 2026,
) -> CountSplitResult | None:
    """計算單一打者的球數分裂。

    使用 pitch_events 的 balls_before/strikes_before 配合 plate_appearances 的結果。
    因為目前 pitch_events 可能還沒有資料（需要 Rebas Open Data），
    先用 CPBL LiveLogJson 的逐球資料做簡化版。
    """
    # 從 pitch_events 查（如果有資料）
    rows = db.execute(text("""
        SELECT
            pe.balls_before,
            pe.strikes_before,
            pe.pitch_result,
            pa.result
        FROM pitch_events pe
        JOIN plate_appearances pa ON pe.game_id = pa.game_id
            AND pe.inning = pa.inning
            AND pe.top_bottom = pa.top_bottom
            AND pe.pa_seq = pa.pa_seq
        JOIN games g ON pe.game_id = g.game_id
        WHERE pe.batter_id = :bid AND g.year = :year
    """), {"bid": batter_id, "year": year}).fetchall()

    if not rows:
        return None

    # 聚合每個 count 的最終打席結果（只看每個 PA 的最後一球）
    # 簡化：用 pitch_events 的結果分類
    count_map: dict[str, dict] = {}

    for row in rows:
        count = _classify_count(row.balls_before, row.strikes_before)
        if count not in count_map:
            count_map[count] = {"count": count, "pa": 0, "hits": 0, "outs": 0, "bb": 0, "k": 0}

        result = (row.result or "").lower()
        if "in_play" in (row.pitch_result or "").lower():
            count_map[count]["pa"] += 1
            if any(h in result for h in ["single", "double", "triple", "homer", "hit"]):
                count_map[count]["hits"] += 1
            else:
                count_map[count]["outs"] += 1
        elif "strikeout" in result or result == "k":
            count_map[count]["pa"] += 1
            count_map[count]["k"] += 1
            count_map[count]["outs"] += 1
        elif "walk" in result or result == "bb":
            count_map[count]["pa"] += 1
            count_map[count]["bb"] += 1

    count_list = list(count_map.values())
    total_pa = sum(c["pa"] for c in count_list)

    # Build per-count stats
    by_count = []
    for c in sorted(count_list, key=lambda x: x["count"]):
        ab = c["hits"] + c["outs"]
        by_count.append(CountStats(
            count=c["count"],
            pa=c["pa"],
            result_hit=c["hits"],
            result_out=c["outs"],
            result_bb=c["bb"],
            result_k=c["k"],
            ba=round(c["hits"] / ab, 3) if ab > 0 else None,
            k_pct=round(c["k"] / c["pa"], 3) if c["pa"] > 0 else None,
            bb_pct=round(c["bb"] / c["pa"], 3) if c["pa"] > 0 else None,
        ))

    return CountSplitResult(
        player_id=batter_id,
        player_name=batter_id.replace("cpbl_", ""),
        role="batter",
        total_pa=total_pa,
        ahead=_aggregate_counts(count_list, COUNT_AHEAD),
        behind=_aggregate_counts(count_list, COUNT_BEHIND),
        even=_aggregate_counts(count_list, COUNT_EVEN),
        two_strike=_aggregate_counts(count_list, COUNT_TWO_STRIKE),
        first_pitch_swing_pct=None,  # 需要逐球 swing 資料
        by_count=by_count,
    )
