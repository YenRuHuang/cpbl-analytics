"""整合 CPBL 官網公開資料 → SQLite。

Usage:
    cd ~/Documents/cpbl-analytics
    uv run python scripts/seed_cpbl.py --year 2026
    uv run python scripts/seed_cpbl.py --year 2026 --range 1-10
"""

import argparse

from sqlalchemy import text

from src.db.engine import get_db, init_db
from src.etl.cpbl_client import CpblClient


def _runners_str(first: str, second: str, third: str) -> str:
    """Convert base runner names to '1_3' style string."""
    bits = []
    if first:
        bits.append("1")
    if second:
        bits.append("2")
    if third:
        bits.append("3")
    return "".join(bits) if bits else "000"


def _detect_pa_result(content: str, action: str, batting_action: str) -> str | None:
    """Detect plate appearance result from Content/ActionName fields.

    Returns result string if this entry ends a PA, None if it's mid-PA pitch.
    """
    c = (content or "").lower()
    a = (action or "")
    ba = (batting_action or "")

    # PA-ending keywords in Content
    pa_endings = [
        "出局", "安打", "全壘打", "三振", "四壞", "觸身",
        "飛球接殺", "接殺", "雙殺", "三殺", "野選",
        "失誤上壘", "犧牲", "犧飛", "內野", "高飛",
        "滾地", "平飛", "封殺", "刺殺", "保送",
    ]
    if any(kw in c or kw in a or kw in ba for kw in pa_endings):
        # Classify result
        if "全壘打" in c or "全壘打" in a:
            return "homer"
        if "三振" in c or "三振" in a:
            return "strikeout"
        if "四壞" in c or "保送" in c or "四壞" in a:
            return "walk"
        if "觸身" in c:
            return "hit_by_pitch"
        if "安打" in c or "安打" in a:
            if "二壘" in c:
                return "double"
            if "三壘" in c:
                return "triple"
            return "single"
        if "犧飛" in c or "犧飛" in a:
            return "sac_fly"
        if "犧牲" in c:
            return "sac_bunt"
        if "失誤" in c:
            return "error"
        if "野選" in c:
            return "fielders_choice"
        if any(kw in c or kw in a for kw in ["出局", "接殺", "雙殺", "封殺", "刺殺"]):
            return "out"
        # Generic out if we matched pa_endings
        return "out"
    return None


def _pitch_result(is_strike: int, is_ball: int, content: str) -> str:
    """Determine pitch result type."""
    c = (content or "").lower()
    if "擊出" in c or "打" in c:
        return "in_play"
    if "揮空" in c or "揮棒落空" in c:
        return "swinging_strike"
    if is_strike:
        if "好球" in c:
            return "called_strike"
        if "界外" in c or "擦棒" in c:
            return "foul"
        return "strike"
    if is_ball:
        return "ball"
    return "unknown"


def seed_plays(db, game_id: str, plays: list) -> dict:
    """Parse LiveLogJson entries into pitch_events + plate_appearances.

    Returns {"pitches": N, "pa": N} counts.
    """
    if not plays:
        return {"pitches": 0, "pa": 0}

    pitch_count = 0
    pa_count = 0
    # Track pitch_number_game per pitcher
    pitcher_pitch_counts: dict[str, int] = {}
    # Track PA sequence per half-inning
    current_pa_key = None  # (inning, top_bottom, batter_acnt)
    pa_seq = 0
    pitch_seq_in_pa = 0
    last_inning = None
    last_vhtype = None

    for entry in plays:
        inning = int(entry.get("InningSeq", 0) or 0)
        vh = entry.get("VisitingHomeType")
        top_bottom = "top" if str(vh) == "1" else "bottom"
        batter_name = entry.get("HitterName", "")
        batter_acnt = entry.get("HitterAcnt", "")
        pitcher_name = entry.get("PitcherName", "")
        pitcher_acnt = entry.get("PitcherAcnt", "")
        content = entry.get("Content", "")
        action = entry.get("ActionName", "")
        batting_action = entry.get("BattingActionName", "")

        batter_id = f"cpbl_{batter_name}" if batter_name else f"cpbl_{batter_acnt}"
        pitcher_id = f"cpbl_{pitcher_name}" if pitcher_name else f"cpbl_{pitcher_acnt}"

        # Reset PA seq on half-inning change
        if inning != last_inning or top_bottom != last_vhtype:
            pa_seq = 0
            last_inning = inning
            last_vhtype = top_bottom
            current_pa_key = None

        # Detect new PA (new batter)
        pa_key = (inning, top_bottom, batter_acnt)
        if pa_key != current_pa_key:
            pa_seq += 1
            pitch_seq_in_pa = 0
            current_pa_key = pa_key

        # Skip non-pitch entries (substitutions, etc.)
        is_strike = int(entry.get("IsStrike", 0) or 0)
        is_ball = int(entry.get("IsBall", 0) or 0)
        is_change = int(entry.get("IsChangePlayer", 0) or 0)

        if is_change and not is_strike and not is_ball:
            # Pure substitution, no pitch
            continue

        # Count this pitch
        pitch_seq_in_pa += 1
        pitcher_pitch_counts[pitcher_id] = pitcher_pitch_counts.get(pitcher_id, 0) + 1

        balls_before = int(entry.get("BallCnt", 0) or 0)
        strikes_before = int(entry.get("StrikeCnt", 0) or 0)
        # BallCnt/StrikeCnt in CPBL API is AFTER this pitch
        if is_ball and balls_before > 0:
            balls_before -= 1
        if is_strike and strikes_before > 0:
            strikes_before -= 1

        p_result = _pitch_result(is_strike, is_ball, content)

        # Insert pitch_event
        db.execute(text("""
            INSERT OR IGNORE INTO pitch_events
            (game_id, inning, top_bottom, pa_seq, pitch_seq, pitcher_id, batter_id,
             pitch_result, balls_before, strikes_before, pitch_number_game, source)
            VALUES (:gid, :inn, :tb, :paseq, :pseq, :pid, :bid,
                    :presult, :bb, :sb, :png, 'cpbl')
        """), {
            "gid": game_id, "inn": inning, "tb": top_bottom,
            "paseq": pa_seq, "pseq": pitch_seq_in_pa,
            "pid": pitcher_id, "bid": batter_id,
            "presult": p_result,
            "bb": balls_before, "sb": strikes_before,
            "png": pitcher_pitch_counts[pitcher_id],
        })
        pitch_count += 1

        # Check if this ends a PA
        pa_result = _detect_pa_result(content, action, batting_action)
        if pa_result:
            runners_before = _runners_str(
                entry.get("FirstBase", ""),
                entry.get("SecondBase", ""),
                entry.get("ThirdBase", ""),
            )
            outs_before = int(entry.get("OutCnt", 0) or 0)
            runs_scored = int(entry.get("IsScoreCnt", 0) or 0)

            db.execute(text("""
                INSERT OR IGNORE INTO plate_appearances
                (game_id, inning, top_bottom, pa_seq, batter_id, pitcher_id,
                 runners_before, outs_before, result, runners_after, outs_after,
                 runs_scored, rbi, source)
                VALUES (:gid, :inn, :tb, :paseq, :bid, :pid,
                        :rb, :ob, :result, :ra, :oa, :rs, 0, 'cpbl')
            """), {
                "gid": game_id, "inn": inning, "tb": top_bottom,
                "paseq": pa_seq, "bid": batter_id, "pid": pitcher_id,
                "rb": runners_before, "ob": outs_before,
                "result": pa_result, "ra": runners_before, "oa": outs_before,
                "rs": runs_scored,
            })
            pa_count += 1

    return {"pitches": pitch_count, "pa": pa_count}


def seed_game(db, game_data) -> bool:
    """Insert a single game + batting + pitching + plays into SQLite."""
    d = game_data.detail

    # Skip unplayed games
    if d.home_score == 0 and d.away_score == 0 and d.status != "final":
        return False

    game_id = f"cpbl_{d.game_date}_{d.away_team}_vs_{d.home_team}"

    # Upsert game
    db.execute(text("""
        INSERT OR REPLACE INTO games (game_id, game_date, year, home_team, away_team,
            home_score, away_score, venue, cpbl_game_sno, source)
        VALUES (:gid, :date, :year, :home, :away, :hs, :as_, :venue, :sno, 'cpbl')
    """), {
        "gid": game_id, "date": d.game_date, "year": int(d.game_date[:4]),
        "home": d.home_team, "away": d.away_team,
        "hs": d.home_score, "as_": d.away_score,
        "venue": d.venue, "sno": d.game_sno,
    })

    # Insert batting lines
    for b in game_data.batting:
        player_id = f"cpbl_{b.player_name}"
        team_name = d.home_team if b.team == "home" else d.away_team
        db.execute(text("""
            INSERT OR REPLACE INTO batter_box (game_id, player_id, team, ab, h, bb, so,
                rbi, r, hr, sb, lob, left_behind_lob, source)
            VALUES (:gid, :pid, :team, :ab, :h, :bb, :so,
                :rbi, 0, :hr, :sb, :lob, :lblob, 'cpbl')
        """), {
            "gid": game_id, "pid": player_id, "team": team_name,
            "ab": b.ab, "h": b.h, "bb": b.bb, "so": b.so,
            "rbi": b.rbi, "hr": b.hr, "sb": b.sb,
            "lob": b.lob, "lblob": b.left_behind_lob,
        })

    # Insert pitching lines
    for p in game_data.pitching:
        player_id = f"cpbl_{p.player_name}"
        team_name = d.home_team if p.team == "home" else d.away_team
        db.execute(text("""
            INSERT OR REPLACE INTO pitcher_box (game_id, player_id, team, ip,
                h, r, er, bb, so, hr, source)
            VALUES (:gid, :pid, :team, :ip, :h, :r, :er, :bb, :so, :hr, 'cpbl')
        """), {
            "gid": game_id, "pid": player_id, "team": team_name,
            "ip": p.ip, "h": p.h, "r": p.r, "er": p.er,
            "bb": p.bb, "so": p.so, "hr": p.hr,
        })

    # Insert play-by-play → pitch_events + plate_appearances
    # Use raw JSON instead of parsed PlayByPlay dataclasses
    import json
    raw_plays = game_data.raw_json.get("LiveLogJson", "[]")
    if isinstance(raw_plays, str):
        try:
            raw_plays = json.loads(raw_plays)
        except json.JSONDecodeError:
            raw_plays = []
    seed_plays(db, game_id, raw_plays or [])

    return True


def main():
    parser = argparse.ArgumentParser(description="整合 CPBL 官網公開資料")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--range", type=str, help="場次範圍，如 1-10")
    parser.add_argument("--kind", type=str, default="A", help="A=一軍, B=二軍")
    args = parser.parse_args()

    print(f"=== CPBL 官網公開資料整合 ({args.year}) ===")

    # Init DB
    init_db()
    print("✅ Database initialized")

    client = CpblClient()

    if args.range:
        start, end = map(int, args.range.split("-"))
        games = []
        for sno in range(start, end + 1):
            game = client.fetch_game(args.year, sno, args.kind)
            if game:
                games.append(game)
                d = game.detail
                if d.home_score > 0 or d.away_score > 0:
                    print(f"  #{sno} {d.away_team} vs {d.home_team} "
                          f"({d.away_score}-{d.home_score}) ✓")
    else:
        print("Fetching full season...")
        games = client.fetch_season(args.year, args.kind)

    print(f"\n📥 {len(games)} games fetched")

    # Insert into DB
    with get_db() as db:
        inserted = 0
        for game in games:
            if seed_game(db, game):
                inserted += 1
        print(f"✅ {inserted} games inserted into SQLite")

    # Summary
    with get_db() as db:
        result = db.execute(text("SELECT COUNT(*) FROM games")).scalar()
        bat_count = db.execute(text("SELECT COUNT(*) FROM batter_box")).scalar()
        pit_count = db.execute(text("SELECT COUNT(*) FROM pitcher_box")).scalar()
        pa_count = db.execute(text("SELECT COUNT(*) FROM plate_appearances")).scalar()
        pe_count = db.execute(text("SELECT COUNT(*) FROM pitch_events")).scalar()
        print("\n📊 DB Summary:")
        print(f"   {result} games, {bat_count} batting, {pit_count} pitching")
        print(f"   {pa_count} plate appearances, {pe_count} pitch events")


if __name__ == "__main__":
    main()
