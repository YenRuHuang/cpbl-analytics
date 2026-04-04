"""
BABIP Regression Analysis — CPBL 2025
======================================
Compares first-half BABIP to second-half batting average change,
demonstrating regression to the mean.

BABIP = (H - HR) / (AB - K - HR)
  - SF not available in data, excluded (minimal impact)

Split point: 2025-07-01
  First half:  2025-03-29 ~ 2025-06-29
  Second half: 2025-07-04 ~ 2025-10+

Output: scatter plot data showing first-half BABIP vs second-half AVG change
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpbl.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'babip_regression_2025.json')

SPLIT_DATE = '2025-07-01'
MIN_PA_HALF = 50  # minimum PA per half to qualify


def calc_babip_regression():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get per-batter stats split by half
    cur.execute("""
        SELECT
            pa.batter_id,
            p.name_zh,
            p.team,
            CASE WHEN g.game_date < ? THEN 'first' ELSE 'second' END AS half,
            COUNT(*) AS pa,
            SUM(CASE WHEN pa.result = 'single' THEN 1 ELSE 0 END) AS s1b,
            SUM(CASE WHEN pa.result = 'double' THEN 1 ELSE 0 END) AS s2b,
            SUM(CASE WHEN pa.result = 'triple' THEN 1 ELSE 0 END) AS s3b,
            SUM(CASE WHEN pa.result = 'homer' THEN 1 ELSE 0 END) AS hr,
            SUM(CASE WHEN pa.result = 'walk' THEN 1 ELSE 0 END) AS bb,
            SUM(CASE WHEN pa.result = 'hit_by_pitch' THEN 1 ELSE 0 END) AS hbp,
            SUM(CASE WHEN pa.result = 'strikeout' THEN 1 ELSE 0 END) AS so,
            SUM(CASE WHEN pa.result = 'sac_bunt' THEN 1 ELSE 0 END) AS sac
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        LEFT JOIN players p ON pa.batter_id = p.player_id
        WHERE g.year = 2025
        GROUP BY pa.batter_id, half
    """, (SPLIT_DATE,))

    rows = cur.fetchall()

    # Get reliable team from batter_box
    cur2 = conn.cursor()
    cur2.execute("""
        SELECT player_id, team, COUNT(*) as cnt FROM batter_box
        WHERE team IS NOT NULL AND team != ''
        GROUP BY player_id, team
        ORDER BY player_id, cnt DESC
    """)
    player_teams = {}
    for r in cur2.fetchall():
        pid = r['player_id']
        if pid not in player_teams:
            player_teams[pid] = r['team']

    conn.close()

    # Organize by player
    players = {}
    for row in rows:
        pid = row['batter_id']
        if pid not in players:
            players[pid] = {
                'name_zh': row['name_zh'] or pid,
                'team': player_teams.get(pid, ''),
            }
        half = row['half']
        h = row['s1b'] + row['s2b'] + row['s3b'] + row['hr']
        ab = row['pa'] - row['bb'] - row['hbp'] - row['sac']
        so = row['so']
        hr = row['hr']

        # BABIP = (H - HR) / (AB - K - HR)
        babip_denom = ab - so - hr
        babip = (h - hr) / babip_denom if babip_denom > 0 else None
        avg = h / ab if ab > 0 else None

        players[pid][half] = {
            'pa': row['pa'],
            'ab': ab,
            'h': h,
            'hr': hr,
            'so': so,
            'avg': round(avg, 3) if avg is not None else None,
            'babip': round(babip, 3) if babip is not None else None,
        }

    # Filter: need both halves with enough PA
    scatter_data = []
    for pid, info in players.items():
        first = info.get('first')
        second = info.get('second')
        if not first or not second:
            continue
        if first['pa'] < MIN_PA_HALF or second['pa'] < MIN_PA_HALF:
            continue
        if first['babip'] is None or second['avg'] is None or first['avg'] is None:
            continue

        avg_change = round(second['avg'] - first['avg'], 3)

        scatter_data.append({
            'player_id': pid,
            'name_zh': info['name_zh'],
            'team': info['team'],
            'first_half': {
                'pa': first['pa'],
                'avg': first['avg'],
                'babip': first['babip'],
            },
            'second_half': {
                'pa': second['pa'],
                'avg': second['avg'],
                'babip': second.get('babip'),
            },
            'avg_change': avg_change,
        })

    # Sort by first-half BABIP descending
    scatter_data.sort(key=lambda x: x['first_half']['babip'], reverse=True)

    # Calculate league average BABIP
    all_babip = [d['first_half']['babip'] for d in scatter_data]
    lg_babip = round(sum(all_babip) / len(all_babip), 3) if all_babip else 0.300

    # Linear regression: first_half_babip vs avg_change
    n = len(scatter_data)
    if n > 2:
        x_vals = [d['first_half']['babip'] for d in scatter_data]
        y_vals = [d['avg_change'] for d in scatter_data]
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        ss_xx = sum((x - x_mean) ** 2 for x in x_vals)

        slope = ss_xy / ss_xx if ss_xx > 0 else 0
        intercept = y_mean - slope * x_mean

        # R-squared
        ss_yy = sum((y - y_mean) ** 2 for y in y_vals)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, y_vals))
        r_squared = 1 - (ss_res / ss_yy) if ss_yy > 0 else 0

        regression = {
            'slope': round(slope, 4),
            'intercept': round(intercept, 4),
            'r_squared': round(r_squared, 4),
            'n': n,
        }
    else:
        regression = None

    output = {
        'meta': {
            'year': 2025,
            'split_date': SPLIT_DATE,
            'min_pa_per_half': MIN_PA_HALF,
            'lg_babip_first_half': lg_babip,
            'qualified_batters': n,
            'regression': regression,
            'notes': [
                'BABIP = (H - HR) / (AB - K - HR)',
                'SF not in data, excluded from denominator',
                f'Split at {SPLIT_DATE}: first half = Mar-Jun, second half = Jul+',
                f'Min {MIN_PA_HALF} PA per half to qualify',
                'Negative slope = high BABIP tends to regress (AVG drops in 2nd half)',
            ],
        },
        'batters': scatter_data,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {n} qualified batters → {OUT_PATH}")
    print(f"League avg 1H BABIP: {lg_babip}")
    if regression:
        print(f"Regression: slope={regression['slope']}, R²={regression['r_squared']}")
    print(f"\n{'='*80}")
    print(f"  Top 10 Highest 1H BABIP → 2H AVG Change")
    print(f"{'='*80}")
    print(f"{'Name':<12} {'1H BABIP':>8} {'1H AVG':>7} {'2H AVG':>7} {'ΔAVG':>7}")
    print(f"{'-'*45}")
    for d in scatter_data[:10]:
        print(f"{d['name_zh']:<12} {d['first_half']['babip']:>8.3f} "
              f"{d['first_half']['avg']:>7.3f} {d['second_half']['avg']:>7.3f} "
              f"{d['avg_change']:>+7.3f}")

    print(f"\n  Bottom 10 Lowest 1H BABIP → 2H AVG Change")
    print(f"{'-'*45}")
    for d in scatter_data[-10:]:
        print(f"{d['name_zh']:<12} {d['first_half']['babip']:>8.3f} "
              f"{d['first_half']['avg']:>7.3f} {d['second_half']['avg']:>7.3f} "
              f"{d['avg_change']:>+7.3f}")

    return output


if __name__ == '__main__':
    calc_babip_regression()
