"""
First/Second Half Splits — CPBL 2025
=====================================
Split 2025 season at July 1:
  First half:  Mar-Jun (spring → mid-season)
  Second half: Jul-Oct (mid-season → end)

For each qualified batter, compare wOBA, OPS, AVG between halves.
Identify breakout and collapse candidates.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpbl.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'half_splits_2025.json')

SPLIT_DATE = '2025-07-01'
MIN_PA_HALF = 50

# wOBA weights (same as wRC+ calculation)
W_BB  = 0.69
W_HBP = 0.72
W_1B  = 0.87
W_2B  = 1.22
W_3B  = 1.56
W_HR  = 1.95


def calc_half_stats(rows):
    """Calculate batting stats from aggregated PA data."""
    pa = rows['pa']
    bb = rows['bb']
    hbp = rows['hbp']
    sac = rows['sac']
    s1b = rows['s1b']
    s2b = rows['s2b']
    s3b = rows['s3b']
    hr = rows['hr']
    so = rows['so']

    ab = pa - bb - hbp - sac
    h = s1b + s2b + s3b + hr

    avg = h / ab if ab > 0 else 0
    obp_denom = ab + bb + hbp
    obp = (h + bb + hbp) / obp_denom if obp_denom > 0 else 0
    slg = (s1b + 2*s2b + 3*s3b + 4*hr) / ab if ab > 0 else 0
    ops = obp + slg

    woba_num = W_BB*bb + W_HBP*hbp + W_1B*s1b + W_2B*s2b + W_3B*s3b + W_HR*hr
    woba = woba_num / obp_denom if obp_denom > 0 else 0

    babip_denom = ab - so - hr
    babip = (h - hr) / babip_denom if babip_denom > 0 else None

    return {
        'pa': pa, 'ab': ab, 'h': h,
        'bb': bb, 'so': so, 'hr': hr,
        'avg': round(avg, 3),
        'obp': round(obp, 3),
        'slg': round(slg, 3),
        'ops': round(ops, 3),
        'woba': round(woba, 4),
        'babip': round(babip, 3) if babip is not None else None,
    }


def calc_half_splits():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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
        players[pid][half + '_raw'] = {
            'pa': row['pa'], 'bb': row['bb'], 'hbp': row['hbp'],
            'sac': row['sac'], 's1b': row['s1b'], 's2b': row['s2b'],
            's3b': row['s3b'], 'hr': row['hr'], 'so': row['so'],
        }

    # Build split comparison
    split_data = []
    for pid, info in players.items():
        first_raw = info.get('first_raw')
        second_raw = info.get('second_raw')
        if not first_raw or not second_raw:
            continue
        if first_raw['pa'] < MIN_PA_HALF or second_raw['pa'] < MIN_PA_HALF:
            continue

        first = calc_half_stats(first_raw)
        second = calc_half_stats(second_raw)

        delta_woba = round(second['woba'] - first['woba'], 4)
        delta_ops = round(second['ops'] - first['ops'], 3)
        delta_avg = round(second['avg'] - first['avg'], 3)

        split_data.append({
            'player_id': pid,
            'name_zh': info['name_zh'],
            'team': info['team'],
            'first_half': first,
            'second_half': second,
            'delta': {
                'woba': delta_woba,
                'ops': delta_ops,
                'avg': delta_avg,
            },
        })

    # Sort by wOBA change (biggest improvement first)
    split_data.sort(key=lambda x: x['delta']['woba'], reverse=True)

    output = {
        'meta': {
            'year': 2025,
            'split_date': SPLIT_DATE,
            'min_pa_per_half': MIN_PA_HALF,
            'qualified_batters': len(split_data),
            'woba_weights': {
                'wBB': W_BB, 'wHBP': W_HBP,
                'w1B': W_1B, 'w2B': W_2B, 'w3B': W_3B, 'wHR': W_HR,
            },
            'notes': [
                f'Split at {SPLIT_DATE}: first half = Mar-Jun, second half = Jul+',
                f'Min {MIN_PA_HALF} PA per half to qualify',
                'Positive delta = second-half improvement (breakout)',
                'Negative delta = second-half decline (collapse)',
                'wOBA weights same as wRC+ calculation (FanGraphs 2024 MLB)',
            ],
        },
        'batters': split_data,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(split_data)} qualified batters → {OUT_PATH}")
    print(f"\n{'='*80}")
    print(f"  Top 10 Second-Half Breakout (ΔwOBA)")
    print(f"{'='*80}")
    print(f"{'Name':<12} {'1H wOBA':>8} {'2H wOBA':>8} {'ΔwOBA':>7} {'1H OPS':>7} {'2H OPS':>7} {'ΔOPS':>6}")
    print(f"{'-'*60}")
    for d in split_data[:10]:
        print(f"{d['name_zh']:<12} "
              f"{d['first_half']['woba']:>8.4f} {d['second_half']['woba']:>8.4f} {d['delta']['woba']:>+7.4f} "
              f"{d['first_half']['ops']:>7.3f} {d['second_half']['ops']:>7.3f} {d['delta']['ops']:>+6.3f}")

    print(f"\n  Top 10 Second-Half Collapse (ΔwOBA)")
    print(f"{'-'*60}")
    for d in split_data[-10:]:
        print(f"{d['name_zh']:<12} "
              f"{d['first_half']['woba']:>8.4f} {d['second_half']['woba']:>8.4f} {d['delta']['woba']:>+7.4f} "
              f"{d['first_half']['ops']:>7.3f} {d['second_half']['ops']:>7.3f} {d['delta']['ops']:>+6.3f}")

    return output


if __name__ == '__main__':
    calc_half_splits()
