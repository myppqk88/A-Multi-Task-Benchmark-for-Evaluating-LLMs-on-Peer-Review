#!/usr/bin/env python3
"""Aggregate L1 judge decisions into the 测量框架 §4.2 metrics per model and task type.

- Important-issue recall (T1, T3): distinct high-importance supported reference points matched,
  divided by min(5, number of such points). Tasks without high points are left out.
- Substantive precision: (match + valid_new) / (substantive claims - unverifiable), where valid_minor
  and neutral claims are not substantive.
- Invalid-critique rate: invalid / substantive claims.
Means are taken over papers (tasks of a paper averaged first); 95% intervals come from a paper-level
bootstrap (2,000 resamples, seed 20261029). Also lists novelty/contribution statements in T1 free
text for the exploratory coding of 测量框架 §3.2. Writes pilot/scores/l1_scores.json.
"""
import json
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / 'pilot/scores/l1_judge'
CARDS = ROOT / 'evaluation/cards_pilot'
RUNS = ROOT / 'pilot/runs'
NOVELTY = re.compile(r'[^.]*\b(novel\w*|originality|contribut\w*|innovative|first (study|to)|fills? (a|the) gap|timely|important addition|adds? to the literature)\b[^.]*\.', re.I)


def paper(task_id):
    return task_id.split('_')[1] if task_id.startswith('T3_') else task_id.split('_')[0]


def metrics(decisions, card, task):
    matched_high = set()
    counts = defaultdict(int)
    high = {p['id'] for p in card['reference_points'] if p['importance'] == 'high' and p['status'] == 'supported'}
    for d in decisions:
        counts[d['decision']] += 1
        if d['decision'] == 'match' and d.get('point_id') in high:
            matched_high.add(d['point_id'])
    substantive = counts['match'] + counts['valid_new'] + counts['invalid'] + counts['unverifiable']
    out = {'claims': sum(counts.values()), **{k: counts[k] for k in ('match', 'neutral', 'valid_new', 'valid_minor', 'invalid', 'unverifiable')}}
    denom = substantive - counts['unverifiable']
    out['precision'] = (counts['match'] + counts['valid_new']) / denom if denom else None
    out['invalid_rate'] = counts['invalid'] / substantive if substantive else None
    if task in ('T1', 'T3') and high:
        out['recall_high'] = len(matched_high) / min(5, len(high))
    return out


def bootstrap(values_by_paper, seed=20261029, n=2000):
    papers = sorted(values_by_paper)
    if not papers:
        return None, None, None
    mean = sum(values_by_paper[p] for p in papers) / len(papers)
    rng = random.Random(seed)
    stats = sorted(sum(values_by_paper[rng.choice(papers)] for _ in papers) / len(papers) for _ in range(n))
    return round(mean, 3), round(stats[int(0.025 * n)], 3), round(stats[int(0.975 * n) - 1], 3)


def main():
    per_task = []
    for path in sorted(JUDGE.glob('*.json')):
        j = json.loads(path.read_text(encoding='utf-8'))
        if not j.get('judgement'):
            continue
        card = json.loads((CARDS / path.name).read_text(encoding='utf-8'))
        for label, decisions in j['judgement'].get('answers', {}).items():
            model = j['label_key'].get(label)
            if model:
                per_task.append({'task_id': j['task_id'], 'task': card['task'], 'model': model, **metrics(decisions, card, card['task'])})
    summary = {}
    for model in sorted({r['model'] for r in per_task}):
        for task in ('T1', 'T2', 'T3', 'all'):
            rows = [r for r in per_task if r['model'] == model and (task == 'all' or r['task'] == task)]
            if not rows:
                continue
            entry = {'tasks': len(rows), 'claims': sum(r['claims'] for r in rows)}
            for k in ('match', 'neutral', 'valid_new', 'valid_minor', 'invalid', 'unverifiable'):
                entry[k] = sum(r[k] for r in rows)
            for metric in ('recall_high', 'precision', 'invalid_rate'):
                by_paper = defaultdict(list)
                for r in rows:
                    if r.get(metric) is not None:
                        by_paper[paper(r['task_id'])].append(r[metric])
                mean, lo, hi = bootstrap({p: sum(v) / len(v) for p, v in by_paper.items()})
                if mean is not None:
                    entry[metric] = {'mean': mean, 'ci95': [lo, hi], 'papers': len(by_paper)}
            summary[f'{model}|{task}'] = entry
    novelty = []
    for path in sorted(RUNS.glob('*/D*_T1_*.json')):
        run = json.loads(path.read_text())
        for field in ('summary', 'overall_assessment'):
            text = (run.get('answer') or {}).get(field, '') or ''
            for m in NOVELTY.finditer(text):
                novelty.append({'model': path.parent.name, 'task_id': run['task_id'], 'field': field, 'sentence': m.group(0).strip()})
    by_model = defaultdict(set)
    for n in novelty:
        by_model[n['model']].add(n['task_id'])
    out = {'summary': summary, 'per_task': per_task,
           'novelty_statements': {'t1_answers_with_statement': {m: len(v) for m, v in by_model.items()}, 'sentences': novelty}}
    (ROOT / 'pilot/scores/l1_scores.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for k, v in summary.items():
        print(k, {m: v[m] for m in v if m in ('tasks', 'claims', 'recall_high', 'precision', 'invalid_rate', 'invalid', 'valid_new')})
    print('T1 answers with a novelty/contribution statement (of 12):', out['novelty_statements']['t1_answers_with_statement'])


if __name__ == '__main__':
    main()
