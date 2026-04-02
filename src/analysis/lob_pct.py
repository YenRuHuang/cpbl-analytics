"""LOB% 殘壘效率分析 — 投手讓壘上跑者未得分的比率。

LOB% = (H + BB + HBP - R) / (H + BB + HBP - 1.4 × HR)
聯盟平均約 70%，> 78% 偏幸運，< 65% 偏不幸運。
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class LobResult:
    player_id: str
    player_name: str
    team: str
    games: int
    ip: float
    h: int
    bb: int
    r: int
    hr: int
    lob_pct: float | None       # 0.0 ~ 1.0
    league_avg: float
    is_lucky: bool               # > 0.78
    is_unlucky: bool             # < 0.65
    sample_note: str             # 樣本量警示


LEAGUE_AVG_LOB = 0.70


def _calc_lob_pct(h: int, bb: int, r: int, hr: int, hbp: int = 0) -> float | None:
    """計算 LOB%。分母 <= 0 時回傳 None。"""
    numerator = h + bb + hbp - r
    denominator = h + bb + hbp - 1.4 * hr
    if denominator <= 0:
        return None
    raw = numerator / denominator
    return max(0.0, min(1.0, raw))


def compute_lob_leaderboard(
    db: Session,
    year: int = 2026,
    min_ip: float = 5.0,
) -> list[LobResult]:
    """計算全聯盟 LOB% 排行。"""
    rows = db.execute(text("""
        SELECT
            pb.player_id,
            REPLACE(pb.player_id, 'cpbl_', '') as player_name,
            pb.team,
            COUNT(DISTINCT pb.game_id) as games,
            SUM(pb.ip) as total_ip,
            SUM(pb.h) as total_h,
            SUM(pb.bb) as total_bb,
            SUM(pb.r) as total_r,
            SUM(pb.er) as total_er,
            SUM(pb.hr) as total_hr
        FROM pitcher_box pb
        JOIN games g ON pb.game_id = g.game_id
        WHERE g.year = :year
        GROUP BY pb.player_id
        HAVING SUM(pb.ip) >= :min_ip
        ORDER BY SUM(pb.ip) DESC
    """), {"year": year, "min_ip": min_ip}).fetchall()

    results: list[LobResult] = []
    for row in rows:
        lob = _calc_lob_pct(
            h=row.total_h or 0,
            bb=row.total_bb or 0,
            r=row.total_r or 0,
            hr=row.total_hr or 0,
        )

        ip = row.total_ip or 0
        sample_note = ""
        if ip < 10:
            sample_note = "⚠️ 極小樣本（< 10 IP）"
        elif ip < 30:
            sample_note = "📊 小樣本（< 30 IP）"

        results.append(LobResult(
            player_id=row.player_id,
            player_name=row.player_name,
            team=row.team or "",
            games=row.games,
            ip=ip,
            h=row.total_h or 0,
            bb=row.total_bb or 0,
            r=row.total_r or 0,
            hr=row.total_hr or 0,
            lob_pct=lob,
            league_avg=LEAGUE_AVG_LOB,
            is_lucky=lob is not None and lob > 0.78,
            is_unlucky=lob is not None and lob < 0.65,
            sample_note=sample_note,
        ))

    # Sort by LOB% descending (None at end)
    results.sort(key=lambda x: x.lob_pct if x.lob_pct is not None else -1, reverse=True)
    return results


def compute_batter_lob(
    db: Session,
    year: int = 2026,
    min_pa: int = 10,
) -> list[dict]:
    """打者角度的殘壘分析（使用 CPBL API 的 Lobs/LeftBehindLobs）。"""
    rows = db.execute(text("""
        SELECT
            bb.player_id,
            REPLACE(bb.player_id, 'cpbl_', '') as player_name,
            COUNT(DISTINCT bb.game_id) as games,
            SUM(bb.ab) as total_ab,
            SUM(bb.h) as total_h,
            SUM(bb.rbi) as total_rbi,
            SUM(bb.lob) as total_lob,
            SUM(bb.left_behind_lob) as total_left_lob
        FROM batter_box bb
        JOIN games g ON bb.game_id = g.game_id
        WHERE g.year = :year
        GROUP BY bb.player_id
        HAVING SUM(bb.ab) >= :min_pa
        ORDER BY SUM(bb.left_behind_lob) DESC
    """), {"year": year, "min_pa": min_pa}).fetchall()

    return [
        {
            "player_id": r.player_id,
            "player_name": r.player_name,
            "games": r.games,
            "ab": r.total_ab,
            "h": r.total_h,
            "rbi": r.total_rbi,
            "lob": r.total_lob,
            "left_behind_lob": r.total_left_lob,
            "lob_per_game": round((r.total_lob or 0) / max(r.games, 1), 2),
        }
        for r in rows
    ]
