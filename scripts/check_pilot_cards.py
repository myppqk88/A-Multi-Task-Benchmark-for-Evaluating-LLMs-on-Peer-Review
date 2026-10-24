#!/usr/bin/env python3
"""Check that every quote in evaluation/cards_pilot/ still occurs in the current pilot input and that the
card's input_sha256 matches the manifest. Run after any change to pilot inputs.
Usage: python3 scripts/check_pilot_cards.py [task_id ...]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_card_drafts import norm, resolve, strings, strip_line_numbers  # noqa: E402


def found(quote, raw):
    q = norm(quote)
    return q in norm(raw) or q in norm(strip_line_numbers(raw))


def main():
    manifest = {m['task_id']: m for m in json.loads((ROOT / 'pilot/inputs/manifest.json').read_text())['items']}
    ids = sys.argv[1:] or sorted(manifest)
    bad = 0
    for task in ids:
        card = json.loads((ROOT / 'evaluation/cards_pilot' / f'{task}.json').read_text(encoding='utf-8'))
        inp = json.loads((ROOT / manifest[task]['input_path']).read_text(encoding='utf-8'))
        everything = ' '.join(strings(inp))
        reviews = everything
        if card['task'] == 'T1':  # T1 cards cite the reports, which only the paper's T3 input carries
            t3 = ROOT / 'pilot/inputs' / f"T3_{task.split('_')[0]}_R1" / 'input.json'
            reviews = ' '.join(strings(json.loads(t3.read_text(encoding='utf-8'))['materials']['reviews'])) if t3.is_file() else ''
        problems = [] if card['input_sha256'] == manifest[task]['input_sha256'] else ['input_sha256 mismatch']
        for p in card['reference_points'] + card['neutral_points']:
            for src in p.get('human_sources', []):
                if not found(src.get('exact_quote', ''), reviews):
                    problems.append(f"{p['id']} human quote: {src['exact_quote'][:50]!r}")
            for ev in p.get('manuscript_evidence', []):
                if 'exact_quote' in ev:
                    try:
                        raw = ' '.join(strings(resolve(inp, ev['input_field'])))
                    except (KeyError, IndexError, ValueError, TypeError):
                        raw = everything
                    if not found(ev['exact_quote'], raw):
                        problems.append(f"{p['id']} evidence quote: {ev['exact_quote'][:50]!r}")
        print(task, 'ok' if not problems else problems)
        bad += bool(problems)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
