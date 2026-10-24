#!/usr/bin/env python3
"""Apply team decisions to the master table and draw the 100-paper main analysis set.

Team decisions (2026-10-24): candidate-v0.1.0 papers whose discipline was
uncertain are dropped; Educational sciences is capped at 25% of the main set;
the main set has 100 papers and the rest of the core is an extension set.
Development-split papers were used while the original cards were written, so
they form the calibration pool and never enter the main set. Selection is a
seeded stratified random draw (discipline x v1 period). No models are called.
"""
import collections
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/master_table'
SEED = 20261024
MAIN_SIZE = 100
EDUCATION = '5.3 Educational sciences'
EDUCATION_CAP = 25
REVIEW_CAP = 15
POST = 'post_2025_06'


def largest_remainder(sizes, total):
    whole = sum(sizes.values())
    raw = {k: total * v / whole for k, v in sizes.items()}
    quota = {k: min(int(x), sizes[k]) for k, x in raw.items()}
    for k in sorted(raw, key=lambda k: (raw[k] - int(raw[k]), k), reverse=True):
        if sum(quota.values()) >= total:
            break
        if quota[k] < sizes[k]:
            quota[k] += 1
    return quota


def main():
    rows = list(csv.DictReader((OUT / 'master_table_v0.1.csv').open(encoding='utf-8')))
    for r in rows:
        r['period'] = POST if r['v1_post_2025_06'] == 'True' else 'pre_2025_06'
        if r['origin'] == 'candidate-v0.1.0' and r['discipline_scope'] == 'uncertain':
            r['core_proposal'], r['core_reason'] = 'exclude', 'team decision 2026-10-24: uncertain discipline dropped'
        r['set'] = ''
    core = [r for r in rows if r['core_proposal'] == 'core']
    for r in core:
        if r['split'] == 'development':
            r['set'] = 'calibration_pool'
    pool = [r for r in core if not r['set']]

    by_disc = collections.defaultdict(list)
    for r in pool:
        by_disc[r['discipline_oecd']].append(r)
    quota = {EDUCATION: min(EDUCATION_CAP, len(by_disc[EDUCATION]))}
    others = {k: len(v) for k, v in by_disc.items() if k != EDUCATION}
    quota.update(largest_remainder(others, MAIN_SIZE - quota[EDUCATION]))

    rng = random.Random(SEED)
    chosen = []
    for disc in sorted(by_disc):
        strata = collections.defaultdict(list)
        for r in sorted(by_disc[disc], key=lambda r: r['paper_id']):
            strata[r['period']].append(r)
        alloc = largest_remainder({k: len(v) for k, v in strata.items()}, quota[disc])
        for period in sorted(strata):
            members = strata[period][:]
            rng.shuffle(members)
            chosen += members[:alloc[period]]
            for r in members:
                r['_rank'] = members.index(r)

    reviews = [r for r in chosen if r['article_class'] == 'review']
    rng.shuffle(reviews)
    for r in reviews[REVIEW_CAP:]:
        swap = sorted((x for x in pool if x not in chosen and x['article_class'] != 'review'
                       and x['discipline_oecd'] == r['discipline_oecd']),
                      key=lambda x: (x['period'] != r['period'], x['_rank'], x['paper_id']))
        if swap:
            chosen[chosen.index(r)] = swap[0]
    for r in pool:
        r['set'] = 'main' if r in chosen else 'extension'

    fields = [k for k in rows[0] if not k.startswith('_')]
    with (OUT / 'master_table_v0.2.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    main_rows = [r for r in rows if r['set'] == 'main']
    count = lambda rs, key: dict(sorted(collections.Counter(key(r) for r in rs).items()))
    summary = dict(
        seed=SEED, decisions=['uncertain-discipline candidate-v0.1.0 papers excluded',
                              f'Educational sciences <= {EDUCATION_CAP} of {MAIN_SIZE}',
                              f'reviews <= {REVIEW_CAP} of {MAIN_SIZE}', 'development split -> calibration pool only'],
        sets=count(rows, lambda r: r['set'] or r['core_proposal']),
        main_by_discipline=count(main_rows, lambda r: r['discipline_oecd']),
        main_by_period=count(main_rows, lambda r: r['period']),
        main_by_article_class=count(main_rows, lambda r: r['article_class']),
        main_by_platform=count(main_rows, lambda r: r['paper_id'].split(':')[0]),
        main_by_origin=count(main_rows, lambda r: r['origin']),
        main_by_build_state=count(main_rows, lambda r: 'T1T2T3 built' if all(int(r[k] or 0) for k in ('n_T1', 'n_T2_single', 'n_T3'))
                                  else ('partly built' if any(int(r[k] or 0) for k in ('n_T1', 'n_T2_single', 'n_T3')) else 'not built')),
        calibration_pool_by_discipline=count([r for r in rows if r['set'] == 'calibration_pool'], lambda r: r['discipline_oecd']),
        models_called=False)
    (OUT / 'master_table_v0.2_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
