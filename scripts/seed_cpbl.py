"""整合 CPBL 官網公開資料 → SQLite。

Usage:
    cd ~/Documents/cpbl-analytics
    uv run python scripts/seed_cpbl.py --year 2026
    uv run python scripts/seed_cpbl.py --year 2026 --range 1-10
"""

import argparse

from src.db.engine import init_db, get_db
from src.etl.cpbl_client import CpblClient

from sqlalchemy import text


def seed_game(db, game_data) -> bool:
    """Insert a single game + batting + pitching into SQLite."""
    d = game_data.detail
    game_id = f"cpbl_{d.game_date}_{d.away_team}_vs_{d.home_team}"

    # Upsert game
    db.execute(text("""
        INSERT OR REPLACE INTO games (game_id, game_date, year, home_team, away_team, home_score, away_score, venue, cpbl_game_sno, source)
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
        db.execute(text("""
            INSERT OR REPLACE INTO batter_box (game_id, player_id, team, ab, h, bb, so, rbi, r, hr, sb, lob, left_behind_lob, source)
            VALUES (:gid, :pid, :team, :ab, :h, :bb, :so, :rbi, 0, :hr, :sb, :lob, :lblob, 'cpbl')
        """), {
            "gid": game_id, "pid": player_id, "team": b.team,
            "ab": b.ab, "h": b.h, "bb": b.bb, "so": b.so,
            "rbi": b.rbi, "hr": b.hr, "sb": b.sb,
            "lob": b.lob, "lblob": b.left_behind_lob,
        })

    # Insert pitching lines
    for p in game_data.pitching:
        player_id = f"cpbl_{p.player_name}"
        db.execute(text("""
            INSERT OR REPLACE INTO pitcher_box (game_id, player_id, team, ip, h, r, er, bb, so, hr, source)
            VALUES (:gid, :pid, :team, :ip, :h, :r, :er, :bb, :so, :hr, 'cpbl')
        """), {
            "gid": game_id, "pid": player_id, "team": p.team,
            "ip": p.ip, "h": p.h, "r": p.r, "er": p.er,
            "bb": p.bb, "so": p.so, "hr": p.hr,
        })

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
                print(f"  #{sno} {game.detail.away_team} vs {game.detail.home_team} "
                      f"({game.detail.away_score}-{game.detail.home_score})")
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
        print(f"\n📊 DB Summary: {result} games, {bat_count} batting lines, {pit_count} pitching lines")


if __name__ == "__main__":
    main()
