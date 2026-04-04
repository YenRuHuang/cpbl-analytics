"""
Calculate CPBL Park Factors (2025 Season)
==========================================
Park Factor = (Runs/Game at Home) / (Runs/Game on Road)

Uses team-based calculation:
  For each team, compare their home games RPG vs away games RPG.
  Then average home and away PF to get a single park factor.

Standard formula (Baseball Reference style):
  PF = ((homeRS + homeRA) / homeG) / ((roadRS + roadRA) / roadG)

Where:
  homeRS = runs scored by team at home
  homeRA = runs allowed by team at home
  roadRS = runs scored by team on road
  roadRA = runs allowed by team on road
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpbl.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'park_factors_2025.json')

# Team → Primary stadium mapping
TEAM_STADIUM = {
    '中信兄弟': '洲際',
    '樂天桃猿': '樂天桃園',
    '富邦悍將': '新莊',
    '味全龍':   '天母',
    '台鋼雄鷹': '澄清湖',
    '統一7-ELEVEn獅': '台南+澄清湖',
}

# Short team names for display
TEAM_SHORT = {
    '中信兄弟': '中信',
    '樂天桃猿': '樂天',
    '富邦悍將': '富邦',
    '味全龍':   '味全',
    '台鋼雄鷹': '台鋼',
    '統一7-ELEVEn獅': '統一獅',
}


def calc_park_factors():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    teams = [row[0] for row in cur.execute(
        "SELECT DISTINCT home_team FROM games ORDER BY home_team"
    ).fetchall()]

    results = []

    for team in teams:
        # Home games: team is home_team
        cur.execute("""
            SELECT COUNT(*) as g,
                   SUM(home_score) as rs,
                   SUM(away_score) as ra
            FROM games
            WHERE home_team = ? AND year = 2025
              AND home_score IS NOT NULL
        """, (team,))
        home = cur.fetchone()

        # Road games: team is away_team
        cur.execute("""
            SELECT COUNT(*) as g,
                   SUM(away_score) as rs,
                   SUM(home_score) as ra
            FROM games
            WHERE away_team = ? AND year = 2025
              AND home_score IS NOT NULL
        """, (team,))
        road = cur.fetchone()

        home_g = home['g'] or 0
        road_g = road['g'] or 0

        if home_g == 0 or road_g == 0:
            continue

        home_rpg = (home['rs'] + home['ra']) / home_g
        road_rpg = (road['rs'] + road['ra']) / road_g

        pf = home_rpg / road_rpg if road_rpg > 0 else 1.0

        results.append({
            'team': team,
            'team_short': TEAM_SHORT.get(team, team),
            'stadium': TEAM_STADIUM.get(team, '—'),
            'home_games': home_g,
            'road_games': road_g,
            'home_rpg': round(home_rpg, 3),
            'road_rpg': round(road_rpg, 3),
            'park_factor': round(pf, 3),
            'home_rs': home['rs'],
            'home_ra': home['ra'],
            'road_rs': road['rs'],
            'road_ra': road['ra'],
        })

    conn.close()

    # Also calculate venue-based PF for the big 5 stadiums
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    venue_results = []
    cur.execute("""
        SELECT venue, COUNT(*) as g,
               SUM(home_score + away_score) as total_runs,
               ROUND(1.0 * SUM(home_score + away_score) / COUNT(*), 3) as rpg
        FROM games
        WHERE venue IS NOT NULL AND home_score IS NOT NULL AND year = 2025
        GROUP BY venue
        HAVING COUNT(*) >= 10
        ORDER BY rpg DESC
    """)
    venue_rows = cur.fetchall()

    # League average RPG
    cur.execute("""
        SELECT ROUND(1.0 * SUM(home_score + away_score) / COUNT(*), 3)
        FROM games WHERE year = 2025 AND home_score IS NOT NULL
    """)
    lg_rpg = cur.fetchone()[0]

    for row in venue_rows:
        venue_pf = row[3] / lg_rpg if lg_rpg > 0 else 1.0
        venue_results.append({
            'venue': row[0],
            'games': row[1],
            'total_runs': row[2],
            'rpg': row[3],
            'park_factor': round(venue_pf, 3),
        })

    conn.close()

    # Sort by park factor descending
    results.sort(key=lambda x: x['park_factor'], reverse=True)
    venue_results.sort(key=lambda x: x['park_factor'], reverse=True)

    output = {
        'meta': {
            'year': 2025,
            'lg_rpg': lg_rpg,
            'method': 'team-based: (homeRS+homeRA)/homeG ÷ (roadRS+roadRA)/roadG',
            'notes': [
                'Team-based PF uses home vs road split per team',
                'Venue-based PF uses venue RPG vs league RPG',
                'Both methods provided for comparison',
                'Stadiums with <10 games excluded from venue analysis',
            ],
        },
        'team_park_factors': results,
        'venue_park_factors': venue_results,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved → {OUT_PATH}")
    print(f"\nLeague RPG: {lg_rpg}")
    print(f"\n{'='*70}")
    print(f"  CPBL 2025 Park Factors (Team-Based)")
    print(f"{'='*70}")
    print(f"{'Team':<12} {'Stadium':<12} {'HomeG':>5} {'RoadG':>5} "
          f"{'HomeRPG':>8} {'RoadRPG':>8} {'PF':>6}")
    print(f"{'-'*70}")
    for r in results:
        print(f"{r['team_short']:<12} {r['stadium']:<12} {r['home_games']:>5} {r['road_games']:>5} "
              f"{r['home_rpg']:>8.3f} {r['road_rpg']:>8.3f} {r['park_factor']:>6.3f}")

    print(f"\n{'='*70}")
    print(f"  CPBL 2025 Park Factors (Venue-Based)")
    print(f"{'='*70}")
    print(f"{'Venue':<12} {'Games':>5} {'RPG':>8} {'PF':>6}")
    print(f"{'-'*40}")
    for v in venue_results:
        print(f"{v['venue']:<12} {v['games']:>5} {v['rpg']:>8.3f} {v['park_factor']:>6.3f}")

    return output


if __name__ == '__main__':
    calc_park_factors()
