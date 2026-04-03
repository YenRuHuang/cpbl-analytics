"""Pitcher Fatigue Curve — 投手隨投球數增加的表現衰退分析。

每 15 球（可設定）為一個 bucket，追蹤被打率、K%、BB%。
自動偵測衰退臨界點：被打率上升 >20% 或 K% 下降 >20%。
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings

_settings = get_settings()
_BUCKET_SIZE = _settings.fatigue_bucket_size

# 樣本量警示閾值（投球數）
_WARN_SMALL = 200
_WARN_MEDIUM = 500

# 疲勞偵測：相對整體平均的變動幅度閾值
_BA_RISE_THRESHOLD = 0.20
_K_DROP_THRESHOLD = 0.20


@dataclass(frozen=True)
class FatigueBucket:
    bucket_index: int           # 0-based（第 0 個 = 投球數 1-15）
    pitch_start: int            # 此 bucket 起始投球數（inclusive）
    pitch_end: int              # 此 bucket 結束投球數（inclusive）
    batters_faced: int
    hits: int
    walks: int
    strikeouts: int
    ba_against: float | None    # 被打率
    k_pct: float | None         # K% = K / BF
    bb_pct: float | None        # BB% = BB / BF
    is_fatigue_point: bool      # 是否為衰退臨界點


@dataclass(frozen=True)
class PitcherFatigueResult:
    pitcher_id: str
    year: int
    total_pitches: int
    games_analyzed: int
    overall_ba_against: float | None
    overall_k_pct: float | None
    overall_bb_pct: float | None
    fatigue_threshold_pitch: int | None   # 偵測到衰退的投球數起點，None 表示未偵測到
    buckets: list[FatigueBucket]
    sample_note: str


@dataclass(frozen=True)
class PitcherFatigueSummary:
    pitcher_id: str
    team: str
    year: int
    total_ip: float
    games: int
    total_pitches: int
    fatigue_threshold_pitch: int | None
    overall_ba_against: float | None
    overall_k_pct: float | None
    sample_note: str


def _safe_divide(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)


def _build_sample_note(total_pitches: int) -> str:
    if total_pitches < _WARN_SMALL:
        return f"小樣本（< {_WARN_SMALL} 球），結果可信度低"
    if total_pitches < _WARN_MEDIUM:
        return f"中等樣本（< {_WARN_MEDIUM} 球），請謹慎解讀"
    return ""


def _detect_fatigue_threshold(
    buckets: list[FatigueBucket],
    overall_ba: float | None,
    overall_k: float | None,
) -> int | None:
    """找到第一個出現衰退跡象的 bucket 的投球數起點。

    用前期 bucket 當 baseline（而非全場平均），這樣不會被疲勞後的
    數據拉高平均，也不會讓第一個 bucket 誤判為疲勞點。
    - 3+ buckets → 前 2 個 bucket 當 baseline，從第 3 個開始偵測
    - 2 buckets → 第 1 個當 baseline，看第 2 個
    - 1 bucket → 不偵測
    """
    if len(buckets) < 2:
        return None

    # 決定 baseline 範圍
    if len(buckets) >= 3:
        baseline_buckets = buckets[:2]
        detect_from = 2
    else:
        baseline_buckets = buckets[:1]
        detect_from = 1

    # 計算 baseline BA 和 K%
    bl_bf = sum(b.batters_faced for b in baseline_buckets)
    bl_hits = sum(b.hits for b in baseline_buckets)
    bl_k = sum(b.strikeouts for b in baseline_buckets)
    bl_walks = sum(b.walks for b in baseline_buckets)
    bl_ab = bl_bf - bl_walks

    baseline_ba = _safe_divide(bl_hits, bl_ab)
    baseline_k = _safe_divide(bl_k, bl_bf)

    if baseline_ba is None and baseline_k is None:
        return None

    for bucket in buckets[detect_from:]:
        if bucket.batters_faced < 3:
            continue

        ba_triggered = (
            baseline_ba is not None
            and bucket.ba_against is not None
            and baseline_ba > 0
            and (bucket.ba_against - baseline_ba) / baseline_ba > _BA_RISE_THRESHOLD
        )
        k_triggered = (
            baseline_k is not None
            and bucket.k_pct is not None
            and baseline_k > 0
            and (baseline_k - bucket.k_pct) / baseline_k > _K_DROP_THRESHOLD
        )

        if ba_triggered or k_triggered:
            return bucket.pitch_start

    return None


def _mark_fatigue_buckets(
    buckets: list[FatigueBucket],
    fatigue_threshold_pitch: int | None,
) -> list[FatigueBucket]:
    """回傳標記了 is_fatigue_point 的新 bucket list（immutable 重建）。
    從疲勞起點開始，之後所有 bucket 都標為疲勞。
    """
    result: list[FatigueBucket] = []
    for b in buckets:
        is_fatigue = (
            fatigue_threshold_pitch is not None
            and b.pitch_start >= fatigue_threshold_pitch
        )
        result.append(FatigueBucket(
            bucket_index=b.bucket_index,
            pitch_start=b.pitch_start,
            pitch_end=b.pitch_end,
            batters_faced=b.batters_faced,
            hits=b.hits,
            walks=b.walks,
            strikeouts=b.strikeouts,
            ba_against=b.ba_against,
            k_pct=b.k_pct,
            bb_pct=b.bb_pct,
            is_fatigue_point=is_fatigue,
        ))
    return result


def _fetch_pitcher_pitch_events(
    db: Session,
    pitcher_id: str,
    year: int,
) -> list:
    """從 pitch_events + plate_appearances 取得投手每球資料含打席結果。

    只回傳每個 PA 的最後一球（有 PA result 的），用來計算 bucket 統計。
    """
    return db.execute(text("""
        SELECT
            pe.pitch_number_game,
            pa.result AS pa_result
        FROM pitch_events pe
        JOIN games g ON pe.game_id = g.game_id
        JOIN plate_appearances pa ON pe.game_id = pa.game_id
            AND pe.inning = pa.inning
            AND pe.top_bottom = pa.top_bottom
            AND pe.pa_seq = pa.pa_seq
        WHERE pe.pitcher_id = :pid
          AND g.year = :year
          AND pe.pitch_seq = (
              SELECT MAX(pe2.pitch_seq) FROM pitch_events pe2
              WHERE pe2.game_id = pe.game_id
                AND pe2.inning = pe.inning
                AND pe2.top_bottom = pe.top_bottom
                AND pe2.pa_seq = pe.pa_seq
          )
        ORDER BY pe.game_id, pe.pitch_number_game
    """), {"pid": pitcher_id, "year": year}).fetchall()


def _fetch_pitcher_box_summary(
    db: Session,
    pitcher_id: str,
    year: int,
) -> tuple[int, float]:
    """回傳 (game_count, total_ip)。"""
    row = db.execute(text("""
        SELECT
            COUNT(DISTINCT pb.game_id) AS games,
            SUM(pb.ip) AS total_ip
        FROM pitcher_box pb
        JOIN games g ON pb.game_id = g.game_id
        WHERE pb.player_id = :pid
          AND g.year = :year
    """), {"pid": pitcher_id, "year": year}).fetchone()

    if row is None:
        return 0, 0.0
    return (row.games or 0), (row.total_ip or 0.0)


def _aggregate_into_buckets(
    rows: list,
    bucket_size: int,
) -> list[FatigueBucket]:
    """將逐球資料聚合成 bucket list。

    pitch_result 約定：
    - 'hit' / 'single' / 'double' / 'triple' / 'homer' → 被安打
    - 'walk' / 'bb' → 四壞
    - 'strikeout' / 'k' → 三振
    - 'in_play_out' / 'out' → 出局（不計 BF 中的安打）
    BF 計算：每個 PA 只計一次（hit + bb + k + in_play_out）
    """
    # 用 pitch_number_game 分 bucket，BF 以每次打席最後一球判斷結果
    # pitch_events 以 pitch_number_game 排序，每球獨立，BF 取終結性結果
    bucket_data: dict[int, dict] = {}

    for row in rows:
        pnum = row.pitch_number_game or 0
        if pnum <= 0:
            continue

        b_idx = (pnum - 1) // bucket_size
        if b_idx not in bucket_data:
            bucket_data[b_idx] = {
                "hits": 0,
                "walks": 0,
                "strikeouts": 0,
                "batters_faced": 0,
            }

        result = (row.pa_result or "").lower()

        is_hit = result in ("single", "double", "triple", "homer")
        is_walk = result in ("walk", "hit_by_pitch", "bb", "ibb")
        is_k = result in ("strikeout", "k", "so")
        is_out = result in ("out", "error", "fielders_choice", "sac_fly", "sac_bunt")

        if is_hit:
            bucket_data[b_idx]["hits"] += 1
            bucket_data[b_idx]["batters_faced"] += 1
        elif is_walk:
            bucket_data[b_idx]["walks"] += 1
            bucket_data[b_idx]["batters_faced"] += 1
        elif is_k:
            bucket_data[b_idx]["strikeouts"] += 1
            bucket_data[b_idx]["batters_faced"] += 1
        elif is_out:
            bucket_data[b_idx]["batters_faced"] += 1

    buckets: list[FatigueBucket] = []
    for b_idx in sorted(bucket_data.keys()):
        d = bucket_data[b_idx]
        bf = d["batters_faced"]
        hits = d["hits"]
        walks = d["walks"]
        strikeouts = d["strikeouts"]
        ab = bf - walks

        buckets.append(FatigueBucket(
            bucket_index=b_idx,
            pitch_start=b_idx * bucket_size + 1,
            pitch_end=(b_idx + 1) * bucket_size,
            batters_faced=bf,
            hits=hits,
            walks=walks,
            strikeouts=strikeouts,
            ba_against=_safe_divide(hits, ab),
            k_pct=_safe_divide(strikeouts, bf),
            bb_pct=_safe_divide(walks, bf),
            is_fatigue_point=False,   # 稍後標記
        ))

    return buckets


def compute_pitcher_fatigue(
    db: Session,
    pitcher_id: str,
    year: int = 2026,
) -> "PitcherFatigueResult | None":
    """計算單一投手的疲勞曲線。

    Returns:
        PitcherFatigueResult，或 None（無資料）。
    """
    games, total_ip = _fetch_pitcher_box_summary(db, pitcher_id, year)
    if games == 0:
        return None

    rows = _fetch_pitcher_pitch_events(db, pitcher_id, year)
    if not rows:
        return None

    # 全季總投球數 = 每場最大 pitch_number_game 的加總
    game_pitches = db.execute(text("""
        SELECT pe.game_id, MAX(pe.pitch_number_game) AS max_pitch
        FROM pitch_events pe
        JOIN games g ON pe.game_id = g.game_id
        WHERE pe.pitcher_id = :pid AND g.year = :year
        GROUP BY pe.game_id
    """), {"pid": pitcher_id, "year": year}).fetchall()
    total_pitches = sum(r.max_pitch or 0 for r in game_pitches) if game_pitches else 0

    buckets = _aggregate_into_buckets(rows, _BUCKET_SIZE)
    if not buckets:
        return None

    # 計算整體平均（所有 bucket 加總）
    total_bf = sum(b.batters_faced for b in buckets)
    total_hits = sum(b.hits for b in buckets)
    total_walks = sum(b.walks for b in buckets)
    total_k = sum(b.strikeouts for b in buckets)
    total_ab = total_bf - total_walks

    overall_ba = _safe_divide(total_hits, total_ab)
    overall_k_pct = _safe_divide(total_k, total_bf)
    overall_bb_pct = _safe_divide(total_walks, total_bf)

    fatigue_threshold = _detect_fatigue_threshold(buckets, overall_ba, overall_k_pct)
    final_buckets = _mark_fatigue_buckets(buckets, fatigue_threshold)

    return PitcherFatigueResult(
        pitcher_id=pitcher_id,
        year=year,
        total_pitches=total_pitches,
        games_analyzed=games,
        overall_ba_against=overall_ba,
        overall_k_pct=overall_k_pct,
        overall_bb_pct=overall_bb_pct,
        fatigue_threshold_pitch=fatigue_threshold,
        buckets=final_buckets,
        sample_note=_build_sample_note(total_pitches),
    )


def compute_fatigue_leaderboard(
    db: Session,
    year: int = 2026,
    min_ip: float = 20.0,
) -> list[PitcherFatigueSummary]:
    """計算全聯盟投手疲勞臨界點排行。

    回傳按疲勞臨界點由低到高排序的摘要列表（臨界點越低代表越早疲勞）。
    沒有偵測到臨界點的投手排在最後。
    """
    pitcher_rows = db.execute(text("""
        SELECT
            pb.player_id,
            MAX(pb.team) AS team,
            COUNT(DISTINCT pb.game_id) AS games,
            SUM(pb.ip) AS total_ip,
            SUM(pb.pitch_count) AS total_pitches
        FROM pitcher_box pb
        JOIN games g ON pb.game_id = g.game_id
        WHERE g.year = :year
        GROUP BY pb.player_id
        HAVING SUM(pb.ip) >= :min_ip
        ORDER BY SUM(pb.ip) DESC
    """), {"year": year, "min_ip": min_ip}).fetchall()

    results: list[PitcherFatigueSummary] = []

    for prow in pitcher_rows:
        detail = compute_pitcher_fatigue(db, prow.player_id, year)
        if detail is None:
            continue

        results.append(PitcherFatigueSummary(
            pitcher_id=prow.player_id,
            team=prow.team or "",
            year=year,
            total_ip=prow.total_ip or 0.0,
            games=prow.games or 0,
            total_pitches=detail.total_pitches,
            fatigue_threshold_pitch=detail.fatigue_threshold_pitch,
            overall_ba_against=detail.overall_ba_against,
            overall_k_pct=detail.overall_k_pct,
            sample_note=detail.sample_note,
        ))

    # 有臨界點的排前面（臨界點越低越早疲勞），沒有的排後
    results.sort(
        key=lambda x: (
            x.fatigue_threshold_pitch is None,
            x.fatigue_threshold_pitch if x.fatigue_threshold_pitch is not None else 9999,
        )
    )
    return results
