#!/usr/bin/env python3
"""Draw the 12 pilot papers from the calibration pool: 6 for rule calibration, 6 for the blind check.

Seeded and stratified by discipline so both halves cover the same fields as far
as the pool allows. Reads docs/master_table/master_table_v0.2.csv; no models are called.
"""
import collections
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'docs/master_table/master_table_v0.2.csv'
OUT = ROOT / 'docs/master_table/pilot_v0.1.csv'
SEED = 20261025
PER_HALF = 6


def main():
    pool = [r for r in csv.DictReader(TABLE.open(encoding='utf-8')) if r['set'] == 'calibration_pool']
    rng = random.Random(SEED)
    by_disc = collections.defaultdict(list)
    for r in sorted(pool, key=lambda r: r['paper_id']):
        by_disc[r['discipline_oecd']].append(r)
    # Discipline quotas by largest remainder, then alternate halves within each discipline,
    # starting from whichever half is currently smaller, so both halves share the same fields.
    sizes = {d: len(v) for d, v in by_disc.items()}
    raw = {d: 2 * PER_HALF * n / len(pool) for d, n in sizes.items()}
    quota = {d: int(x) for d, x in raw.items()}
    for d in sorted(raw, key=lambda d: (raw[d] - int(raw[d]), d), reverse=True)[:2 * PER_HALF - sum(quota.values())]:
        quota[d] += 1
    halves = {'calibration': [], 'blind_check': []}
    for disc in sorted(by_disc, key=lambda d: (-quota[d], d)):
        members = by_disc[disc][:]
        rng.shuffle(members)
        for r in members[:quota[disc]]:
            name = min(halves, key=lambda h: (len(halves[h]), h))
            halves[name].append(r)
    chosen = {r['paper_id']: name for name, rs in halves.items() for r in rs}
    fields = ['paper_id', 'pilot_role', 'discipline_oecd', 'article_type', 'v1_date', 'n_T1', 'n_T2_single', 'n_T3', 'chain_status', 'title']
    with OUT.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in sorted(pool, key=lambda r: (chosen.get(r['paper_id'], 'zz_unused'), r['paper_id'])):
            w.writerow({**r, 'pilot_role': chosen.get(r['paper_id'], 'unused')})
    print(json.dumps({name: [(r['paper_id'], r['discipline_oecd']) for r in rs] for name, rs in halves.items()},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
