#!/usr/bin/env python3
"""Automatic (L0) scoring of pilot model runs, plus conclusion-label accuracy for T2/T3.

L0 (测量框架 §4.1): schema validity; every exact_quote must occur, after whitespace and quote-mark
normalisation, in the input field it names (or with line-number lines removed); page evidence must
name a page that was supplied; T2 must keep revision_verification = not_assessed.
Label accuracy (§4.2): the model's label is correct when it is in the card's acceptable set.
A quote found elsewhere in the input but not in the named field counts as a field error, not a
fabrication. Writes pilot/scores/auto_scores.json and prints a per-model summary.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_card_drafts import norm, pages_of, resolve, strings, strip_line_numbers  # noqa: E402

RUNS = ROOT / 'pilot/runs'
CARDS = ROOT / 'evaluation/cards_pilot'


def field_text(inp, field):
    """Text of the named field; dotted paths (materials.manuscript_after.text) are read as JSON pointers."""
    field = field.replace('.', '/').lstrip('/')
    for base in ('', 'input/', 'materials/'):
        try:
            return ' '.join(strings(resolve(inp, base + field)))
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return None


def contains(raw, quote):
    q = norm(quote)
    return bool(q) and (q in norm(raw) or q in norm(strip_line_numbers(raw)))


def evidence_items(answer, task):
    if task == 'T2':
        yield from answer.get('evidence_refs', [])
    else:
        for issue in answer.get('issues', []):
            yield from issue.get('evidence', [])
        yield from answer.get('contribution_assessment', {}).get('evidence', [])


def score(run, inp, card):
    task = card['task']
    answer = run['answer']
    schema = inp.get('output_schema') or inp.get('output_format')
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(answer), key=str)
    everything = ' '.join(strings(inp))
    pages = pages_of(inp)
    quotes = found = elsewhere = page_refs = page_ok = 0
    fabricated = []
    for ev in evidence_items(answer, task):
        if 'exact_quote' in ev:
            quotes += 1
            raw = field_text(inp, ev.get('input_field', ''))
            if raw is not None and contains(raw, ev['exact_quote']):
                found += 1
            elif contains(everything, ev['exact_quote']):
                elsewhere += 1
            else:
                fabricated.append(ev['exact_quote'][:120])
        elif 'page' in ev:
            page_refs += 1
            page_ok += int(ev['page']) in pages
    out = {'schema_valid': not errors, 'schema_errors': [e.message[:160] for e in errors[:3]],
           'quotes': quotes, 'quotes_in_named_field': found, 'quotes_in_other_field': elsewhere,
           'quotes_not_found': len(fabricated), 'not_found_examples': fabricated[:3],
           'page_refs': page_refs, 'page_refs_valid': page_ok,
           'n_issues': len(answer.get('issues', [])) if task != 'T2' else len(answer.get('remaining_gaps', []))}
    if task == 'T2':
        out['overreach'] = answer.get('revision_verification') != 'not_assessed'
    if task in ('T2', 'T3'):
        label = answer.get('adequacy_label' if task == 'T2' else 'overall_label')
        ref = card['label_reference']
        out.update({'label': label, 'label_in_acceptable_set': label in ref['acceptable_set'],
                    'label_is_primary': label == ref['primary']})
    return out


def main():
    manifest = {m['task_id']: m for m in json.loads((ROOT / 'pilot/inputs/manifest.json').read_text())['items']}
    rows = []
    for path in sorted(RUNS.glob('*/*.json')):
        run = json.loads(path.read_text(encoding='utf-8'))
        task_id, model = run['task_id'], path.parent.name
        card = json.loads((CARDS / f'{task_id}.json').read_text(encoding='utf-8'))
        inp = json.loads((ROOT / manifest[task_id]['input_path']).read_text(encoding='utf-8'))
        row = {'model': model, 'model_served': run.get('models_served'), 'task_id': task_id, 'task': card['task'],
               'parsed': run['answer'] is not None}
        if run['answer'] is not None:
            row.update(score(run, inp, card))
        rows.append(row)
    summary = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for key in (r['model'], f"{r['model']}|{r['task']}"):
            s = summary[key]
            s['runs'] += 1
            s['parsed'] += r['parsed']
            if not r['parsed']:
                continue
            s['schema_valid'] += r['schema_valid']
            for k in ('quotes', 'quotes_in_named_field', 'quotes_in_other_field', 'quotes_not_found', 'page_refs', 'page_refs_valid', 'n_issues'):
                s[k] += r[k]
            if 'label' in r:
                s['labelled'] += 1
                s['label_ok'] += r['label_in_acceptable_set']
                s['label_primary'] += r['label_is_primary']
    table = {}
    for key, s in sorted(summary.items()):
        table[key] = {'runs': int(s['runs']), 'parsed': int(s['parsed']), 'schema_valid': int(s['schema_valid']),
                      'quotes': int(s['quotes']),
                      'fabricated_quote_rate': round(s['quotes_not_found'] / s['quotes'], 3) if s['quotes'] else None,
                      'wrong_field_rate': round(s['quotes_in_other_field'] / s['quotes'], 3) if s['quotes'] else None,
                      'page_refs': int(s['page_refs']), 'page_refs_valid': int(s['page_refs_valid']),
                      'mean_items': round(s['n_issues'] / s['parsed'], 2) if s['parsed'] else None}
        if s['labelled']:
            table[key].update({'label_accuracy': f"{int(s['label_ok'])}/{int(s['labelled'])}",
                               'label_primary_match': f"{int(s['label_primary'])}/{int(s['labelled'])}"})
    out = ROOT / 'pilot/scores'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'auto_scores.json').write_text(json.dumps({'summary': table, 'runs': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for key, v in table.items():
        print(key, v)


if __name__ == '__main__':
    main()
