#!/usr/bin/env python3
"""L1 claim-level judging of pilot runs (测量框架 §4.2) by an LLM judge, to be validated against humans.

One judge call per task: the task material (text and page images, as the models saw it), the
reference card, and every model's answer for that task under shuffled anonymous labels, so the
judge cannot tell which model wrote which answer and applies one standard to all of them. The
label -> model key is kept beside the output. For each claim the judge returns the reference point
it matches, or a category for unmatched claims. Writes pilot/scores/l1_judge/<task_id>.json.
Usage: python3 scripts/judge_pilot_l1.py [--judge opus] [--tasks ...] [--jobs 4]
"""
import argparse
import json
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from run_pilot_models import message, parse_answer

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'pilot/runs'
CARDS = ROOT / 'evaluation/cards_pilot'
OUT = ROOT / 'pilot/scores/l1_judge'
MODELS = ('opus', 'sonnet', 'haiku')
SYSTEM = 'You are an expert adjudicator for a peer-review benchmark. Apply the rubric exactly. Reply with one JSON object and nothing else.'
RUBRIC = """You are given (1) the task material exactly as the models saw it, (2) the reference card for this task and (3) several anonymous answers.
Split each answer into claims: for T1 and T3 each entry of "issues" is one claim; for T2 each entry of "remaining_gaps" and of "addressed_requirements" is one claim.
For every claim decide, using the task material as the final authority:
- "match": the claim meets the match_criteria of a reference point (reference_points R..). Give its id. For T3 the claim's resolution judgement must also agree with the reference point. One claim may match only one point; pick the best one.
- "neutral": it corresponds to a neutral point (neutral_points N..). Give its id.
- "valid_new": not on the card, but a substantive problem that the material supports and the reasoning establishes.
- "valid_minor": correct but non-substantive (language, formatting, a trivial point).
- "invalid": factually wrong, misreads the material, or the reasoning does not hold.
- "unverifiable": cannot be decided from the material.
Judge content, not wording or length. Do not reward agreement with reviewers for its own sake; the material decides.
Return: {"answers": {"<label>": [{"claim_index": 0, "claim_field": "issues|remaining_gaps|addressed_requirements", "decision": "match|neutral|valid_new|valid_minor|invalid|unverifiable", "point_id": "R03 or N01 or null", "reason": "<=40 words"}]}}
Cover every claim of every answer."""


def card_for_judge(card):
    keep = ('id', 'judgment', 'issue_type', 'importance', 'status', 'match_criteria', 'acceptable_alternatives')
    return {'reference_points': [{k: p.get(k) for k in keep} for p in card['reference_points']],
            'neutral_points': [{k: p.get(k) for k in ('id', 'judgment', 'match_criteria')} for p in card['neutral_points']],
            'label_reference': card.get('label_reference')}


def judge(task_id, judge_model, seed):
    target = OUT / f'{task_id}.json'
    if target.is_file() and json.loads(target.read_text()).get('judgement') is not None:
        return task_id, 'cached'
    answers = {m: json.loads((RUNS / m / f'{task_id}.json').read_text())['answer'] for m in MODELS
               if (RUNS / m / f'{task_id}.json').is_file()}
    answers = {m: a for m, a in answers.items() if a is not None}
    labels = ['A', 'B', 'C'][:len(answers)]
    order = list(answers)
    random.Random(f'{seed}:{task_id}').shuffle(order)
    key = dict(zip(labels, order))
    card = json.loads((CARDS / f'{task_id}.json').read_text(encoding='utf-8'))
    msg = message(task_id)
    msg['message']['content'].append({'type': 'text', 'text': RUBRIC + '\n\nREFERENCE CARD:\n' +
                                      json.dumps(card_for_judge(card), ensure_ascii=False, indent=1) + '\n\nANSWERS:\n' +
                                      json.dumps({l: answers[m] for l, m in key.items()}, ensure_ascii=False, indent=1)})
    cmd = ['claude', '-p', '--model', judge_model, '--input-format', 'stream-json', '--output-format', 'stream-json',
           '--verbose', '--tools', '', '--system-prompt', SYSTEM, '--strict-mcp-config', '--setting-sources', '',
           '--no-session-persistence', '--max-turns', '1']
    for attempt in (1, 2):
        with tempfile.TemporaryDirectory() as empty:
            proc = subprocess.run(cmd, input=json.dumps(msg, ensure_ascii=False) + '\n', capture_output=True, text=True, cwd=empty, timeout=3600)
        events = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith('{')]
        result = next((e for e in events if e.get('type') == 'result'), {})
        served = sorted({e['message'].get('model') for e in events if e.get('type') == 'assistant' and e.get('message')})
        parsed, error = parse_answer(result.get('result', '') or '')
        OUT.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'task_id': task_id, 'judge': judge_model, 'judge_served': served, 'label_key': key,
                                      'judgement': parsed, 'parse_error': error, 'raw_text': result.get('result')},
                                     ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        if parsed is not None:
            return task_id, 'ok'
    return task_id, f'failed: {error}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--judge', default='opus')
    parser.add_argument('--tasks', nargs='*')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--seed', default='20261027')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'pilot/inputs/manifest.json').read_text())['items']
    tasks = args.tasks or [m['task_id'] for m in manifest]
    with ThreadPoolExecutor(args.jobs) as pool:
        for task_id, status in pool.map(lambda t: judge(t, args.judge, args.seed), tasks):
            print(task_id, status, flush=True)


if __name__ == '__main__':
    main()
