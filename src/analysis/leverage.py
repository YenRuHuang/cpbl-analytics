"""Clutch Hitting / Leverage Index 分析。

Leverage Index（LI）衡量每個打席的情境壓力。
Clutch Score = 高壓打席 BA（LI > 1.5）- 整體 BA。
正值表示球員在高壓情境下表現優於整體，負值反之。

DB 依賴：
  plate_appearances (game_id, inning, top_bottom, pa_seq,
                     batter_id, pitcher_id, runners_before,
                     outs_before, result, runs_scored)
  games             (game_id, year, home_score, away_score)
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.utils.run_expectancy import compute_leverage_index

# 高壓打席的 LI 門檻
HIGH_LEVERAGE_THRESHOLD = 1.5

# 樣本量警示門檻
SAMPLE_WARN_CRITICAL = 10
SAMPLE_WARN_LOW = 20


@dataclass(frozen=True)
class LeverageStats:
    """球員 Leverage Index / Clutch 統計。"""

    player_id: str
    player_name: str
    total_pa: int
    high_leverage_pa: int           # LI > 1.5 的打席數
    high_li_ba: float | None        # 高壓打席打擊率
    overall_ba: float | None        # 整體打擊率
    clutch_score: float | None      # high_li_ba - overall_ba
    high_li_ops: float | None       # 高壓打席 OPS（如有資料）
    sample_note: str                # 樣本量警示文字


def _is_hit(result: str | None) -> bool:
    """判斷打席結果是否為安打。"""
    if result is None:
        return False
    result_upper = result.upper()
    # 常見安打代碼：1B, 2B, 3B, HR
    return any(code in result_upper for code in ("1B", "2B", "3B", "HR"))


def _is_at_bat(result: str | None) -> bool:
    """判斷打席是否計入打數（排除 BB/HBP/SAC）。"""
    if result is None:
        return False
    result_upper = result.upper()
    # 排除不計打數的打席
    exclude = ("BB", "HBP", "SAC", "IBB", "SF")
    return not any(code in result_upper for code in exclude)


def _sample_note(high_li_pa: int) -> str:
    """根據高壓打席數回傳樣本量警示。"""
    if high_li_pa < SAMPLE_WARN_CRITICAL:
        return f"⚠️ 極小樣本（高壓打席僅 {high_li_pa} 個，結論不可靠）"
    if high_li_pa < SAMPLE_WARN_LOW:
        return f"📊 小樣本（高壓打席 {high_li_pa} 個，謹慎解讀）"
    return ""


def _calc_ba(hits: int, at_bats: int) -> float | None:
    """計算打擊率；打數為 0 時回傳 None。"""
    if at_bats <= 0:
        return None
    return round(hits / at_bats, 3)


def _build_leverage_stats(
    player_id: str,
    player_name: str,
    pa_rows: list,
) -> LeverageStats:
    """從打席資料列表計算 LeverageStats。"""
    total_hits = 0
    total_ab = 0
    hi_hits = 0
    hi_ab = 0
    hi_pa_count = 0

    for row in pa_rows:
        base_state: str = row.runners_before or "000"
        outs: int = row.outs_before or 0
        inning: int = row.inning or 1
        score_diff: int = row.score_diff or 0
        result: str | None = row.result

        try:
            li = compute_leverage_index(base_state, outs, inning, score_diff)
        except KeyError:
            # base_state 格式異常，略過此打席
            li = 1.0

        is_ab = _is_at_bat(result)
        is_h = _is_hit(result)

        if is_ab:
            total_ab += 1
            if is_h:
                total_hits += 1

        if li >= HIGH_LEVERAGE_THRESHOLD:
            hi_pa_count += 1
            if is_ab:
                hi_ab += 1
                if is_h:
                    hi_hits += 1

    overall_ba = _calc_ba(total_hits, total_ab)
    high_li_ba = _calc_ba(hi_hits, hi_ab)
    clutch_score: float | None = None
    if high_li_ba is not None and overall_ba is not None:
        clutch_score = round(high_li_ba - overall_ba, 3)

    return LeverageStats(
        player_id=player_id,
        player_name=player_name,
        total_pa=len(pa_rows),
        high_leverage_pa=hi_pa_count,
        high_li_ba=high_li_ba,
        overall_ba=overall_ba,
        clutch_score=clutch_score,
        high_li_ops=None,   # 需 SLG 資料，目前留空
        sample_note=_sample_note(hi_pa_count),
    )


def compute_batter_clutch(
    db: Session,
    batter_id: str,
    year: int = 2026,
) -> LeverageStats | None:
    """計算單一打者的 Clutch 表現。

    Args:
        db: SQLAlchemy session。
        batter_id: 球員 ID。
        year: 賽季年份。

    Returns:
        LeverageStats，若無打席資料則回傳 None。
    """
    rows = db.execute(text("""
        SELECT
            pa.batter_id,
            pa.inning,
            pa.outs_before,
            pa.runners_before,
            pa.result,
            pa.runs_scored,
            CASE
                WHEN pa.top_bottom = 'top'
                    THEN g.home_score - g.away_score
                ELSE g.away_score - g.home_score
            END AS score_diff
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        WHERE pa.batter_id = :batter_id
          AND g.year = :year
        ORDER BY pa.game_id, pa.pa_seq
    """), {"batter_id": batter_id, "year": year}).fetchall()

    if not rows:
        return None

    # player_name 暫用 batter_id，待 player_mapping 整合後替換
    player_name = batter_id.replace("cpbl_", "")
    return _build_leverage_stats(batter_id, player_name, rows)


def compute_clutch_leaderboard(
    db: Session,
    year: int = 2026,
    min_pa: int = 50,
) -> list[LeverageStats]:
    """計算全聯盟打者 Clutch 排行榜。

    Args:
        db: SQLAlchemy session。
        year: 賽季年份。
        min_pa: 最低打席數門檻。

    Returns:
        LeverageStats 列表，依 clutch_score 降序排列（None 排末尾）。
    """
    # 先取得符合最低打席數的球員清單
    batter_ids_rows = db.execute(text("""
        SELECT pa.batter_id, COUNT(*) AS pa_count
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        WHERE g.year = :year
        GROUP BY pa.batter_id
        HAVING COUNT(*) >= :min_pa
    """), {"year": year, "min_pa": min_pa}).fetchall()

    results: list[LeverageStats] = []
    for id_row in batter_ids_rows:
        stats = compute_batter_clutch(db, id_row.batter_id, year)
        if stats is not None:
            results.append(stats)

    # 依 clutch_score 降序，None 排末尾
    results.sort(
        key=lambda x: x.clutch_score if x.clutch_score is not None else float("-inf"),
        reverse=True,
    )
    return results
