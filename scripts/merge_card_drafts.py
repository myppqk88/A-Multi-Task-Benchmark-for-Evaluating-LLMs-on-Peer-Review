#!/usr/bin/env python3
"""Blind-merge drafter A and B card drafts into X/Y adjudication material (evaluation/参照卡起草规范_v0.2.md §5).

For each task the two drafts are randomly labelled X and Y with a secret seed. The X/Y -> A/B key
is written to pilot/blinding_key.json, which is git-ignored; only its SHA256 is printed so it can
be committed now and the key revealed after adjudication. Points are grouped by overlap of their
quoted evidence (human-report or manuscript quotes); a group may be one-to-one or link one
drafter's merged point to several finer points. Groups are suggestions the adjudicator confirms
or overrides. Drafter identity fields are removed from the merge output.
Usage: python3 scripts/merge_card_drafts.py [--seed-hex HEX]
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / 'pilot/cards_draft'
OUT = ROOT / 'pilot/merge'
SHEET = ROOT / 'pilot/adjudication'
KEY = ROOT / 'pilot/blinding_key.json'
PAIR_THRESHOLD = 0.5
COMPARED = ('issue_type', 'importance', 'status', 'origin')


def tokens(text):
    return set(re.findall(r'[a-z0-9]{3,}', text.lower()))


def evidence_tokens(point, field):
    if field == 'human':
        return tokens(' '.join(s.get('exact_quote', '') for s in point.get('human_sources', [])))
    return tokens(' '.join(e.get('exact_quote', '') or e.get('observation', '') for e in point.get('manuscript_evidence', [])))


def similarity(p, q):
    """Overlap coefficient of quoted evidence, so a short and a long quote of the same passage still match."""
    scores = []
    for field in ('human', 'manuscript'):
        a, b = evidence_tokens(p, field), evidence_tokens(q, field)
        if len(a) >= 3 and len(b) >= 3:
            scores.append(len(a & b) / min(len(a), len(b)))
    return max(scores) if scores else 0.0


def group_points(xs, ys):
    """Link every point to its best partner on the other side (if above threshold) and return connected
    groups, so one drafter's merged point can align with several of the other drafter's finer points."""
    links = set()
    for i, x in enumerate(xs):
        best = max(((similarity(x, y), j) for j, y in enumerate(ys)), default=(0, None))
        if best[0] >= PAIR_THRESHOLD:
            links.add((i, best[1]))
    for j, y in enumerate(ys):
        best = max(((similarity(x, y), i) for i, x in enumerate(xs)), default=(0, None))
        if best[0] >= PAIR_THRESHOLD:
            links.add((best[1], j))
    parent = {('x', i): ('x', i) for i in range(len(xs))} | {('y', j): ('y', j) for j in range(len(ys))}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for i, j in links:
        parent[find(('x', i))] = find(('y', j))
    groups = {}
    for node in parent:
        groups.setdefault(find(node), []).append(node)
    out = []
    for members in groups.values():
        gx = sorted(i for side, i in members if side == 'x')
        gy = sorted(j for side, j in members if side == 'y')
        score = max((similarity(xs[i], ys[j]) for i in gx for j in gy), default='')
        out.append((gx, gy, round(score, 2) if score != '' else ''))
    return sorted(out, key=lambda g: (not (g[0] and g[1]), g[0][:1] or [99], g[1][:1] or [99]))


def strip_identity(card):
    card = dict(card)
    card.pop('drafter', None)
    return card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed-hex', help='reuse a seed (only to reproduce an earlier merge)')
    args = parser.parse_args()
    seed = bytes.fromhex(args.seed_hex) if args.seed_hex else os.urandom(16)
    rng = random.Random(seed)
    tasks = sorted(d.name for d in DRAFTS.iterdir() if (d / 'A.json').is_file() and (d / 'B.json').is_file())
    missing = sorted(d.name for d in DRAFTS.iterdir() if d.is_dir() and d.name not in tasks)
    key = {'seed_hex': seed.hex(), 'tasks': {}}
    OUT.mkdir(parents=True, exist_ok=True)
    SHEET.mkdir(parents=True, exist_ok=True)
    summary = []
    for task in tasks:
        drafts = {d: json.loads((DRAFTS / task / f'{d}.json').read_text(encoding='utf-8')) for d in ('A', 'B')}
        order = ['A', 'B']
        rng.shuffle(order)
        key['tasks'][task] = {'X': order[0], 'Y': order[1]}
        x, y = strip_identity(drafts[order[0]]), strip_identity(drafts[order[1]])
        rows = []
        for gx, gy, score in group_points(x['reference_points'], y['reference_points']):
            px = [x['reference_points'][i] for i in gx]
            py = [y['reference_points'][j] for j in gy]
            if px and py:
                conflicts = [f for f in COMPARED if {p.get(f) for p in px} != {p.get(f) for p in py}]
                kind = ('one_to_one' if len(px) == len(py) == 1 else 'many_to_many') + ('_conflict' if conflicts else '_agreed')
            else:
                conflicts, kind = [], 'X_only' if px else 'Y_only'
            rows.append({'kind': kind, 'x': ';'.join(p['id'] for p in px), 'y': ';'.join(p['id'] for p in py),
                         'overlap': score, 'conflicts': conflicts})
        label_conflict = x.get('label_reference', {}).get('primary') != y.get('label_reference', {}).get('primary') \
            or set(x.get('label_reference', {}).get('acceptable_set', [])) != set(y.get('label_reference', {}).get('acceptable_set', []))
        merged = {'task_id': task, 'X': x, 'Y': y, 'suggested_alignment': rows, 'label_conflict': label_conflict,
                  'instructions': 'Groups are suggestions from evidence overlap; confirm or regroup before deciding.'}
        (OUT / f'{task}.json').write_text(json.dumps(merged, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        with (SHEET / f'{task}.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['task_id', 'row', 'kind', 'X_point', 'Y_point', 'overlap', 'conflicting_fields',
                        'decision(keep_X/keep_Y/merge/rewrite/delete/regroup)', 'final_issue_type', 'final_importance',
                        'final_status', 'final_judgment_if_rewritten', 'reason', 'adjudicator', 'date'])
            for n, r in enumerate(rows, 1):
                w.writerow([task, n, r['kind'], r['x'], r['y'], r['overlap'], ';'.join(r['conflicts'])] + [''] * 8)
            if x['task'] in ('T2', 'T3'):
                w.writerow([task, 'label', 'label_conflict' if label_conflict else 'label_agreed',
                            json.dumps(x['label_reference'], ensure_ascii=False), json.dumps(y['label_reference'], ensure_ascii=False),
                            '', ''] + [''] * 8)
        counts = {k: sum(r['kind'] == k for r in rows) for k in ('one_to_one_agreed', 'one_to_one_conflict', 'many_to_many_agreed', 'many_to_many_conflict', 'X_only', 'Y_only')}
        summary.append({'task_id': task, **counts, 'label_conflict': label_conflict})
    KEY.write_text(json.dumps(key, indent=1) + '\n')
    key_hash = hashlib.sha256(KEY.read_bytes()).hexdigest()
    (OUT / 'summary.json').write_text(json.dumps({'tasks_merged': len(tasks), 'tasks_missing_a_draft': missing,
                                                  'blinding_key_sha256': key_hash, 'per_task': summary},
                                                 ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'merged': len(tasks), 'missing': missing, 'blinding_key_sha256': key_hash}, indent=1))


if __name__ == '__main__':
    main()
