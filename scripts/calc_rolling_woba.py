"""
Rolling wOBA — CPBL 2025
=========================
Calculate 50-PA rolling wOBA for each qualified batter.
Output: per-batter time series for line chart visualization.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpbl.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'rolling_woba_2025.json')

W_BB  = 0.69
W_HBP = 0.72
W_1B  = 0.87
W_2B  = 1.22
W_3B  = 1.56
W_HR  = 1.95

MIN_PA = 100
WINDOW = 50


def calc_rolling_woba():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all PA for 2025, ordered by date for each batter
    cur.execute("""
        SELECT
            pa.batter_id,
            g.game_date,
            pa.result
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        WHERE g.year = 2025
        ORDER BY pa.batter_id, g.game_date, pa.pa_seq
    """)
    rows = cur.fetchall()

    # Get player info
    cur.execute("SELECT player_id, name_zh FROM players")
    name_map = {r['player_id']: r['name_zh'] for r in cur.fetchall()}

    # Get team from batter_box
    cur2 = conn.cursor()
    cur2.execute("""
        SELECT player_id, team, COUNT(*) as cnt FROM batter_box
        WHERE team IS NOT NULL AND team != ''
        GROUP BY player_id, team
        ORDER BY player_id, cnt DESC
    """)
    team_map = {}
    for r in cur2.fetchall():
        if r['player_id'] not in team_map:
            team_map[r['player_id']] = r['team']

    conn.close()

    # Group PA by batter
    batter_pas = {}
    for row in rows:
        bid = row['batter_id']
        if bid not in batter_pas:
            batter_pas[bid] = []
        batter_pas[bid].append({
            'date': row['game_date'],
            'result': row['result'],
        })

    # Calculate rolling wOBA for qualified batters
    result_weights = {
        'walk': W_BB,
        'hit_by_pitch': W_HBP,
        'single': W_1B,
        'double': W_2B,
        'triple': W_3B,
        'homer': W_HR,
    }

    players_data = []

    for bid, pas in batter_pas.items():
        if len(pas) < MIN_PA:
            continue

        # Calculate wOBA for each PA
        pa_values = []
        for pa in pas:
            r = pa['result']
            # wOBA numerator contribution
            woba_num = result_weights.get(r, 0)
            # Is this PA in the denominator? (AB + BB + HBP, excluding sac_bunt)
            in_denom = r not in ('sac_bunt',)
            pa_values.append({
                'date': pa['date'],
                'woba_num': woba_num,
                'in_denom': in_denom,
                'is_hit': r in ('single', 'double', 'triple', 'homer'),
                'is_ab': r not in ('walk', 'hit_by_pitch', 'sac_bunt'),
            })

        # Rolling window calculation
        series = []
        for i in range(WINDOW - 1, len(pa_values)):
            window = pa_values[i - WINDOW + 1:i + 1]
            w_num = sum(p['woba_num'] for p in window)
            w_den = sum(1 for p in window if p['in_denom'])
            w_hits = sum(1 for p in window if p['is_hit'])
            w_ab = sum(1 for p in window if p['is_ab'])

            woba = w_num / w_den if w_den > 0 else 0
            avg = w_hits / w_ab if w_ab > 0 else 0

            series.append({
                'pa_num': i + 1,
                'date': pa_values[i]['date'],
                'woba': round(woba, 4),
                'avg': round(avg, 3),
            })

        name = name_map.get(bid, bid)
        players_data.append({
            'player_id': bid,
            'name_zh': name,
            'team': team_map.get(bid, ''),
            'total_pa': len(pas),
            'series': series,
        })

    # Sort by total PA descending
    players_data.sort(key=lambda x: x['total_pa'], reverse=True)

    # League average rolling wOBA (aggregate all PAs)
    all_pas_sorted = []
    for bid, pas in batter_pas.items():
        for pa in pas:
            all_pas_sorted.append(pa)
    all_pas_sorted.sort(key=lambda x: x['date'])

    output = {
        'meta': {
            'year': 2025,
            'window': WINDOW,
            'min_pa': MIN_PA,
            'qualified_batters': len(players_data),
            'woba_weights': {
                'wBB': W_BB, 'wHBP': W_HBP,
                'w1B': W_1B, 'w2B': W_2B, 'w3B': W_3B, 'wHR': W_HR,
            },
        },
        'players': players_data,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(players_data)} batters → {OUT_PATH}")
    print(f"Window: {WINDOW} PA")

    # Show top 5 by PA
    for p in players_data[:5]:
        last = p['series'][-1] if p['series'] else {}
        print(f"  {p['name_zh']:<12} PA={p['total_pa']:>4}  "
              f"final wOBA={last.get('woba', 0):.4f}  "
              f"points={len(p['series'])}")

    return output


if __name__ == '__main__':
    calc_rolling_woba()
