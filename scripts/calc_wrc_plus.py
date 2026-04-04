"""
Calculate wRC+ for CPBL 2025 Season
====================================
Uses plate_appearances table to reconstruct counting stats.

Notes:
- wOBA linear weights use FanGraphs-style MLB approximations
  (CPBL-specific weights not available)
- SF (sacrifice fly) not in data → treated as 0 in denominator
  (slight overestimate of PA denominator, minimal impact)
- IBB not distinguished from BB → treated as regular BB
  (standard practice; IBB should be excluded from wOBA numerator,
   but CPBL IBB frequency is low)
- Park factors not applied (single-park-factor adjustment would
  require per-stadium run environment data)

Formula:
  wOBA = (wBB*BB + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR)
         / (AB + BB + SF + HBP)
  where AB = PA - BB - HBP - sac_bunt - sac_fly

  lgwOBA = league-wide wOBA (same formula, all batters aggregated)
  lgR_PA = total league runs / total league PA
  wOBAscale = lgwOBA / lgR_PA

  wRC+ = ((wOBA - lgwOBA) / wOBAscale + lgR_PA) / lgR_PA * 100
"""

import sqlite3
import json
import os

# ── wOBA linear weights (FanGraphs 2024 approximation) ──────────────────────
W_BB  = 0.69
W_HBP = 0.72
W_1B  = 0.87
W_2B  = 1.22
W_3B  = 1.56
W_HR  = 1.95

MIN_PA = 100  # minimum PA threshold for leaderboard

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cpbl.db')
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'wrc_plus_2025.json')


def calc_wrc_plus():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── 1. Aggregate PA results per batter ──────────────────────────────────
    cur.execute("""
        SELECT
            pa.batter_id,
            p.name_zh,
            p.name_en,
            p.team,
            COUNT(*) AS pa,
            SUM(CASE WHEN pa.result = 'single'       THEN 1 ELSE 0 END) AS s1b,
            SUM(CASE WHEN pa.result = 'double'       THEN 1 ELSE 0 END) AS s2b,
            SUM(CASE WHEN pa.result = 'triple'       THEN 1 ELSE 0 END) AS s3b,
            SUM(CASE WHEN pa.result = 'homer'        THEN 1 ELSE 0 END) AS hr,
            SUM(CASE WHEN pa.result = 'walk'         THEN 1 ELSE 0 END) AS bb,
            SUM(CASE WHEN pa.result = 'hit_by_pitch' THEN 1 ELSE 0 END) AS hbp,
            SUM(CASE WHEN pa.result = 'strikeout'    THEN 1 ELSE 0 END) AS so,
            SUM(CASE WHEN pa.result = 'sac_bunt'     THEN 1 ELSE 0 END) AS sac_bunt,
            SUM(CASE WHEN pa.result = 'error'        THEN 1 ELSE 0 END) AS reach_on_error
        FROM plate_appearances pa
        JOIN games g ON pa.game_id = g.game_id
        LEFT JOIN players p ON pa.batter_id = p.player_id
        WHERE g.year = 2025
        GROUP BY pa.batter_id
    """)
    rows = cur.fetchall()

    # ── 2. Total 2025 runs from games table ──────────────────────────────────
    cur.execute("""
        SELECT SUM(home_score + away_score) FROM games WHERE year = 2025
    """)
    total_runs = cur.fetchone()[0] or 0
    conn.close()

    # ── 3. Build batter records ──────────────────────────────────────────────
    batters = []
    for row in rows:
        pa   = row['pa']
        bb   = row['bb']
        hbp  = row['hbp']
        s1b  = row['s1b']
        s2b  = row['s2b']
        s3b  = row['s3b']
        hr   = row['hr']
        sac  = row['sac_bunt']
        roe  = row['reach_on_error']

        # AB = PA - BB - HBP - SacBunt  (SF treated as 0)
        ab = pa - bb - hbp - sac

        # wOBA denominator
        denom = ab + bb + hbp  # + SF (=0)
        if denom == 0:
            continue

        woba_num = (W_BB * bb + W_HBP * hbp + W_1B * s1b
                    + W_2B * s2b + W_3B * s3b + W_HR * hr)
        woba = woba_num / denom

        h = s1b + s2b + s3b + hr
        avg = h / ab if ab > 0 else 0.0
        obp = (h + bb + hbp) / denom if denom > 0 else 0.0
        slg_num = s1b + 2*s2b + 3*s3b + 4*hr
        slg = slg_num / ab if ab > 0 else 0.0

        batters.append({
            'player_id': row['batter_id'],
            'name_zh':   row['name_zh'] or row['batter_id'],
            'name_en':   row['name_en'] or '',
            'team':      row['team'] or '',
            'pa': pa, 'ab': ab, 'h': h,
            'bb': bb, 'hbp': hbp,
            '1b': s1b, '2b': s2b, '3b': s3b, 'hr': hr,
            'so': row['so'],
            'sac_bunt': sac,
            'reach_on_error': roe,
            'avg': round(avg, 3),
            'obp': round(obp, 3),
            'slg': round(slg, 3),
            'ops': round(obp + slg, 3),
            'woba': round(woba, 4),
            'woba_num': round(woba_num, 4),
            'woba_denom': denom,
        })

    # ── 4. League averages ───────────────────────────────────────────────────
    lg_woba_num   = sum(b['woba_num']   for b in batters)
    lg_woba_denom = sum(b['woba_denom'] for b in batters)
    lg_pa_total   = sum(b['pa']         for b in batters)

    lg_woba  = lg_woba_num / lg_woba_denom if lg_woba_denom > 0 else 0
    lg_r_pa  = total_runs / lg_pa_total    if lg_pa_total > 0   else 0
    woba_scale = lg_woba / lg_r_pa         if lg_r_pa > 0       else 1

    # ── 5. wRC+ per batter ───────────────────────────────────────────────────
    for b in batters:
        wrc_plus = ((b['woba'] - lg_woba) / woba_scale + lg_r_pa) / lg_r_pa * 100
        b['wrc_plus'] = round(wrc_plus, 1)

    # ── 6. Sort and annotate rank ────────────────────────────────────────────
    batters.sort(key=lambda x: x['wrc_plus'], reverse=True)
    for i, b in enumerate(batters, 1):
        b['rank'] = i

    # ── 7. Save JSON ─────────────────────────────────────────────────────────
    output = {
        'meta': {
            'year': 2025,
            'total_runs': total_runs,
            'total_pa': lg_pa_total,
            'lg_woba': round(lg_woba, 4),
            'lg_r_pa': round(lg_r_pa, 4),
            'woba_scale': round(woba_scale, 4),
            'woba_weights': {
                'wBB': W_BB, 'wHBP': W_HBP,
                'w1B': W_1B, 'w2B': W_2B, 'w3B': W_3B, 'wHR': W_HR,
            },
            'notes': [
                'wOBA weights are FanGraphs MLB approximations (2024)',
                'SF not in source data, treated as 0',
                'IBB not distinguished from BB',
                'No park factor adjustment',
            ]
        },
        'batters': batters,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(batters)} batters → {OUT_PATH}")

    # ── 8. Print top-20 leaderboard ─────────────────────────────────────────
    qualifiers = [b for b in batters if b['pa'] >= MIN_PA]
    print(f"\n{'='*80}")
    print(f"  CPBL 2025 wRC+ Leaderboard  (min {MIN_PA} PA)")
    print(f"  League wOBA: {lg_woba:.4f}  |  lgR/PA: {lg_r_pa:.4f}  |  wOBAscale: {woba_scale:.4f}")
    print(f"{'='*80}")
    print(f"{'Rk':>3} {'Name':<12} {'Team':<6} {'PA':>4} {'AB':>4} {'H':>4} "
          f"{'HR':>3} {'BB':>3} {'AVG':>5} {'OBP':>5} {'SLG':>5} {'OPS':>5} "
          f"{'wOBA':>6} {'wRC+':>6}")
    print(f"{'-'*80}")
    for b in qualifiers[:20]:
        print(f"{b['rank']:>3} {b['name_zh']:<12} {b['team']:<6} "
              f"{b['pa']:>4} {b['ab']:>4} {b['h']:>4} "
              f"{b['hr']:>3} {b['bb']:>3} "
              f"{b['avg']:>5.3f} {b['obp']:>5.3f} {b['slg']:>5.3f} {b['ops']:>5.3f} "
              f"{b['woba']:>6.4f} {b['wrc_plus']:>6.1f}")
    print(f"{'='*80}")
    print(f"\nTotal qualifiers (>={MIN_PA} PA): {len(qualifiers)}")
    return output


if __name__ == '__main__':
    calc_wrc_plus()
