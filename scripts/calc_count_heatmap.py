"""
Generate league-wide count heatmap data by aggregating all player count JSONs.

Output: data/count_heatmap_{year}.json
        dashboard/static/api/analysis/count_heatmap_{year}.json

Usage:
    python3 scripts/calc_count_heatmap.py [--year 2025]
"""
import argparse
import json
import glob
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTS_ORDER = ['0-0', '0-1', '0-2', '1-0', '1-1', '1-2', '2-0', '2-1', '2-2', '3-0', '3-1', '3-2']


def aggregate_counts(year: int) -> dict:
    counts_dir = os.path.join(BASE_DIR, 'dashboard', 'static', 'api', 'analysis', 'counts', str(year))
    files = glob.glob(os.path.join(counts_dir, '*.json'))
    if not files:
        raise FileNotFoundError(f'No player JSON files found in {counts_dir}')

    agg: dict[str, dict] = {}
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        for item in data.get('by_count', []):
            c = item.get('count', '')
            if not c:
                continue
            if c not in agg:
                agg[c] = {'pa': 0, 'hits': 0, 'ks': 0, 'bbs': 0}
            agg[c]['pa'] += item.get('pa', 0)
            agg[c]['hits'] += item.get('result_hit', 0)
            agg[c]['ks'] += item.get('result_k', 0)
            agg[c]['bbs'] += item.get('result_bb', 0)

    counts = []
    for c in COUNTS_ORDER:
        if c not in agg:
            continue
        d = agg[c]
        pa = d['pa']
        counts.append({
            'count': c,
            'balls': int(c[0]),
            'strikes': int(c[2]),
            'pa': pa,
            'ba': round(d['hits'] / pa, 3) if pa > 0 else 0,
            'k_pct': round(d['ks'] / pa, 3) if pa > 0 else 0,
            'bb_pct': round(d['bbs'] / pa, 3) if pa > 0 else 0,
        })

    return {'year': year, 'total_players': len(files), 'counts': counts}


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate league count heatmap data')
    parser.add_argument('--year', type=int, default=2025)
    args = parser.parse_args()

    data = aggregate_counts(args.year)

    out_paths = [
        os.path.join(BASE_DIR, 'data', f'count_heatmap_{args.year}.json'),
        os.path.join(BASE_DIR, 'dashboard', 'static', 'api', 'analysis', f'count_heatmap_{args.year}.json'),
    ]
    for path in out_paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f'Written: {path}')

    print(f"Aggregated {data['total_players']} players, {len(data['counts'])} counts")


if __name__ == '__main__':
    main()
