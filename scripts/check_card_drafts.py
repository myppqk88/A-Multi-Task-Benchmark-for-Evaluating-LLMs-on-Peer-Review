#!/usr/bin/env python3
"""Mechanical checks for pilot card drafts (pilot/drafting_instructions.md).

Checks structure, enum values, input hash, that every exact_quote occurs verbatim
(after whitespace normalisation) in the field it names, that human-source quotes
occur in the reports the drafter was allowed to read, that cited pages exist, and
the card_author / alternatives rules. It does not judge scientific content.
Usage: python3 scripts/check_card_drafts.py [--drafter A|B] [task_id ...]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'pilot/inputs'
DRAFTS = ROOT / 'pilot/cards_draft'
ISSUE = {f'V{i}' for i in range(1, 10)}
IMPORTANCE = {'high', 'medium', 'low'}
STATUS = {'supported', 'partly_supported', 'disputed', 'unresolved'}
LABELS = {'T2': {'sufficient', 'partially_sufficient', 'insufficient', 'insufficient_evidence'},
          'T3': {'acceptable_under_rubric', 'needs_substantive_revision', 'insufficient_evidence'}}


LINE_NUMBER_LINE = re.compile(r'\n[ \t]*\d{1,4}[ \t]*(?=\n)')


def strip_line_numbers(text):
    """Remove manuscript line-number lines (PeerJ review PDFs print one between every text line)."""
    return LINE_NUMBER_LINE.sub('\n', text)


def norm(text):
    text = text.replace('­', '').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return re.sub(r'\s+', ' ', text).strip()


def resolve(obj, pointer):
    for part in [p for p in pointer.strip('/').split('/') if p]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def pages_of(inp):
    labels = set()
    blob = json.dumps(inp, ensure_ascii=False)
    for m in re.finditer(r'"page_label": "p(\d+)"|"source_page": (\d+)|"source_attachment_page": (\d+)', blob):
        labels.add(int(next(g for g in m.groups() if g)))
    return labels


def check(task_id, drafter, manifest):
    errors = []
    path = DRAFTS / task_id / f'{drafter}.json'
    if not path.is_file():
        return [f'missing {path.relative_to(ROOT)}']
    try:
        card = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        return [f'invalid JSON: {exc}']
    item = manifest[task_id]
    inp = json.loads((ROOT / item['input_path']).read_text(encoding='utf-8'))
    task = item['task']
    for key in ('task_id', 'paper_id', 'task', 'unit', 'input_sha256', 'card_version', 'drafter',
                'reference_points', 'label_reference', 'known_invalid_patterns', 'draft_notes'):
        if key not in card:
            errors.append(f'missing field {key}')
    if card.get('input_sha256') != item['input_sha256']:
        errors.append('input_sha256 does not match manifest')
    if card.get('drafter') != drafter or card.get('task') != task or card.get('task_id') != task_id:
        errors.append('drafter/task/task_id mismatch')
    if task == 'T1':
        reports = json.loads((INPUTS / f"T3_{task_id.split('_')[0]}_R1" / 'input.json').read_text())['materials']['reviews'] \
            if (INPUTS / f"T3_{task_id.split('_')[0]}_R1").is_dir() else {}
    elif task == 'T2':
        reports = {'comment': inp['input']['comment_text']}
    else:
        reports = inp['materials']['reviews']
    report_text = {k: norm(v) for k, v in reports.items()}
    pages = pages_of(inp)
    points = card.get('reference_points', [])
    if not points:
        errors.append('no reference_points')
    authored = 0
    seen_alternatives = {}
    for p in points:
        pid = p.get('id', '?')
        for key, allowed in (('issue_type', ISSUE), ('importance', IMPORTANCE), ('status', STATUS)):
            if p.get(key) not in allowed:
                errors.append(f'{pid}: bad {key} {p.get(key)!r}')
        if p.get('origin') not in ('human_review', 'card_author'):
            errors.append(f'{pid}: bad origin')
        if p.get('origin') == 'card_author':
            authored += 1
            if p.get('importance') == 'low':
                errors.append(f'{pid}: card_author point must be high or medium')
        elif not p.get('human_sources'):
            errors.append(f'{pid}: human_review point without human_sources')
        for src in p.get('human_sources', []):
            quote = norm(src.get('exact_quote', ''))
            rid = src.get('report_id')
            pool = [report_text[rid]] if rid in report_text else list(report_text.values())
            if not quote or not any(quote in t for t in pool):
                errors.append(f'{pid}: human quote not found in {rid}: {quote[:60]!r}')
        if not p.get('manuscript_evidence') and p.get('status') != 'unresolved':
            errors.append(f'{pid}: no manuscript_evidence')
        for ev in p.get('manuscript_evidence', []):
            if 'exact_quote' in ev:
                try:
                    field = resolve(inp, ev['input_field'])
                except (KeyError, IndexError, ValueError, TypeError):
                    errors.append(f"{pid}: unknown input_field {ev['input_field']!r}")
                    continue
                raw = ' '.join(strings(field))
                quote = norm(ev['exact_quote'])
                if quote not in norm(raw) and quote not in norm(strip_line_numbers(raw)):
                    errors.append(f"{pid}: quote not found in {ev['input_field']}: {ev['exact_quote'][:60]!r}")
            elif 'page' in ev:
                if int(ev['page']) not in pages:
                    errors.append(f"{pid}: page {ev['page']} not supplied to the model")
                if not ev.get('observation'):
                    errors.append(f'{pid}: page evidence without observation')
            else:
                errors.append(f'{pid}: evidence needs exact_quote or page')
        if not p.get('match_criteria'):
            errors.append(f'{pid}: empty match_criteria')
        for alt in p.get('acceptable_alternatives', []):
            if alt in seen_alternatives:
                errors.append(f'{pid}: alternative copied from {seen_alternatives[alt]}')
            seen_alternatives[alt] = pid
    if authored > 2:
        errors.append(f'{authored} card_author points (max 2)')
    label = card.get('label_reference', {})
    if task in LABELS:
        if label.get('primary') not in LABELS[task] or not set(label.get('acceptable_set', [])) <= LABELS[task] \
                or label.get('primary') not in label.get('acceptable_set', []):
            errors.append('label_reference invalid for task')
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--drafter', default='A', choices=['A', 'B'])
    parser.add_argument('task_ids', nargs='*')
    args = parser.parse_args()
    manifest = {m['task_id']: m for m in json.loads((INPUTS / 'manifest.json').read_text())['items']}
    ids = args.task_ids or sorted(manifest)
    failed = 0
    for task_id in ids:
        errors = check(task_id, args.drafter, manifest)
        status = 'ok' if not errors else f'{len(errors)} problem(s)'
        print(f'{task_id}: {status}')
        for e in errors:
            print('   -', e)
        failed += bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
