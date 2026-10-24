#!/usr/bin/env python3
"""Build the merged candidate-paper table (candidate-v0.1.0 + intake batch-01).

Needs the candidate-v0.1.0 binary assets (scripts/download_assets.py) and the
intake/batch-01 branch fetched locally. Reads intake metadata from git, so no
intake checkout is required. No models are called; outputs are proposals that
the team must confirm.
"""
import argparse
import collections
import csv
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/master_table'
POST_CUTOFF = '2025-06-01'
CORE_TYPES = {'Research Article', 'Brief Report', 'Research Note', 'Case Study', 'Method Article', 'Study Protocol'}
REVIEW_TYPES = {'Review', 'Systematic Review', 'Scoping Review', 'Literature Review'}
REVIEW_CAP = 0.15
TYPE_PATTERN = (r'(RESEARCH ARTICLE|SYSTEMATIC REVIEW|SCOPING REVIEW|LITERATURE REVIEW|REVIEW|OPEN LETTER|ESSAY|'
                r'METHOD ARTICLE|DATA NOTE|STUDY PROTOCOL|CASE STUDY|OPINION ARTICLE|BRIEF REPORT|POLICY BRIEF|'
                r'RESEARCH NOTE|CORRESPONDENCE)')
MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def pdf_text(path, last_page=2):
    if not path or not (ROOT / path).is_file():
        return ''
    return subprocess.run(['pdftotext', '-l', str(last_page), str(ROOT / path), '-'], capture_output=True, text=True).stdout


def iso(day_month_year):
    d, m, y = day_month_year.split()
    return f'{y}-{MONTHS[m[:3]]:02d}-{int(d):02d}'


def old_dates(ledger):
    """v1 and v2 public dates of a candidate-v0.1.0 paper, with their source."""
    p1, p2 = ledger.get('前稿原件', ''), ledger.get('修改稿原件', '')
    if ledger['论文ID'].startswith('PeerJ:'):
        get = lambda p: (re.findall(r'_(\d{4}-\d{2}-\d{2})_', p) or [''])[0]
        return get(p1), get(p2), 'PeerJ file-name submission date'
    first = re.search(r'First published:\s*(\d{1,2} \w{3} \d{4})', pdf_text(p1))
    latest = re.search(r'Latest published:\s*(\d{1,2} \w{3} \d{4})', pdf_text(p2))
    return (iso(first.group(1)) if first else '', iso(latest.group(1)) if latest else '',
            'publisher PDF cover (First/Latest published)')


def old_type(pid, ledger):
    if pid.startswith('PeerJ:'):
        kind = 'Systematic Review' if 'systematic review' in ledger['题名'].lower() else 'Research Article'
        return kind, 'PeerJ: not printed on manuscript; inferred from title'
    text = pdf_text(ledger.get('前稿原件', ''))
    m = re.search(r'^\s*' + TYPE_PATTERN + r'\s*$', text, re.M) or re.search(TYPE_PATTERN, text[:3000])
    return (m.group(1).title() if m else ''), 'publisher PDF first pages'


def count_reports(text):
    m = re.search(r'已定位(\d+)份独立当轮报告', text)
    return int(m.group(1)) if m else 0


def article_class(kind):
    if kind in CORE_TYPES:
        return 'empirical_or_method'
    if kind in REVIEW_TYPES:
        return 'review'
    return 'non_empirical' if kind else 'unknown'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake-ref', default='origin/intake/batch-01')
    args = parser.parse_args()

    catalog = json.loads((ROOT / 'evaluation/source_catalog.json').read_text())
    disc = {r['paper_id']: r for r in csv.DictReader((OUT / 'discipline_proposals_v0.1.csv').open())}
    cards = collections.defaultdict(list)
    for f in (ROOT / 'evaluation/cards').glob('*.json'):
        cards[json.loads(f.read_text())['paper_id']].append(json.loads(f.read_text()))

    intake_files = git('ls-tree', '-r', '--name-only', args.intake_ref, 'intake/batch-01').split()
    intake_meta = {}
    for path in intake_files:
        if path.endswith('/metadata.json') and path.count('/') == 3:
            m = json.loads(git('show', f'{args.intake_ref}:{path}'))
            intake_meta[path.split('/')[2]] = m

    rows = []
    for pid, entry in catalog.items():
        ledger = entry['ledger']
        own = cards.get(pid, [])
        tasks = collections.Counter((c['task'], c['unit']) for c in own)
        t3 = [c for c in own if c['task'] == 'T3']
        deferred = [c['task_id'] for c in t3 if (ROOT / Path(c['input_path']).parent / '暂缓原因.txt').is_file()]
        fill = intake_meta.get('fill_' + pid.replace(':', '_'))
        v1_reports = count_reports(ledger['当轮评审'])
        with_response = v1_reports if ledger['作者回复'].startswith('每份报告') else None
        if fill and fill.get('reviews'):
            v1_reports = len([r for r in fill['reviews'] if r['on_version'] == 'v1'])
            answered = {a for r in fill['responses'] for a in ([r['answers']] if isinstance(r['answers'], str) else r['answers'])}
            with_response = len([r for r in fill['reviews'] if r['on_version'] == 'v1' and r['id'] in answered])
        if t3 and not deferred:
            chain = 'complete_T3_built'
        elif t3:
            chain = 'complete_T3_deferred_supplements_filled' if fill else 'T3_deferred'
        elif ledger['主要缺环类型'].startswith('回复缺失'):
            chain = 'partial_responses_missing'
        elif fill and v1_reports and ledger['本地修改稿'].startswith('已定位至少两份'):
            chain = 'complete_after_fill_T3_not_built'
        else:
            chain = 'incomplete'
        kind, kind_src = old_type(pid, ledger)
        v1d, v2d, date_src = old_dates(ledger)
        t1_pages = t3_pages = 0
        for c in own:
            data = json.loads((ROOT / c['input_path']).read_text())
            if c['task'] == 'T1':
                t1_pages += len(data['input'].get('page_images') or [])
            if c['task'] == 'T3':
                t3_pages += json.dumps(data, ensure_ascii=False).count('"path": "assets/')
        image_ev = sum(1 for c in own for e in c['evidence'] if e.get('evidence_type') == 'image' or 'image_path' in e['locator'])
        d = disc[pid]
        rows.append(dict(
            paper_id=pid, origin='candidate-v0.1.0', title=ledger['题名'],
            discipline_oecd=d['discipline_oecd'], discipline_scope=d['scope'],
            discipline_source='proposal from title only; team to confirm', discipline_note=d['basis_note'],
            article_type=kind, article_type_source=kind_src, article_class=article_class(kind),
            v1_date=v1d, v2_date=v2d, date_source=date_src, v1_post_2025_06=bool(v1d and v1d >= POST_CUTOFF),
            split=ledger['当前划分'], n_T1=tasks[('T1', 'original_manuscript')],
            n_T2_single=tasks[('T2', 'single_concern')], n_T2_report=tasks[('T2', 'complete_report')],
            n_T3=len(t3), t3_deferred=';'.join(deferred), v1_reports=v1_reports,
            v1_reports_with_response='' if with_response is None else with_response, chain_status=chain,
            t1_page_images=t1_pages, t3_visual_pages=t3_pages, image_evidence_items=image_ev))

    for key, m in sorted(intake_meta.items()):
        if key.startswith('fill_'):
            continue
        pid = f"{m['platform']}:{m['article_id']}"
        vs = {v['label']: v for v in m['versions']}
        v1 = [r for r in m['reviews'] if r['on_version'] == 'v1']
        kind = m.get('article_type', '')
        rows.append(dict(
            paper_id=pid, origin='intake-batch-01', title=m['title'],
            discipline_oecd=m['discipline_oecd'], discipline_scope='uncertain' if m['discipline_uncertain'] else 'in',
            discipline_source='intake metadata; team to confirm', discipline_note='',
            article_type=kind, article_type_source='platform HTML label', article_class=article_class(kind),
            v1_date=vs['v1']['public_date'], v2_date=vs['v2']['public_date'], date_source='intake metadata',
            v1_post_2025_06=vs['v1']['public_date'] >= POST_CUTOFF, split='unassigned',
            n_T1=0, n_T2_single=0, n_T2_report=0, n_T3=0, t3_deferred='',
            v1_reports=len(v1), v1_reports_with_response=len([r for r in v1 if r.get('has_response', True)]),
            chain_status='complete_not_built', t1_page_images='', t3_visual_pages='', image_evidence_items=''))

    for r in rows:
        if r['discipline_scope'] == 'out':
            r['core_proposal'], r['core_reason'] = 'exclude', 'outside OECD 5 Social sciences'
        elif r['chain_status'] in ('incomplete', 'partial_responses_missing', 'T3_deferred'):
            r['core_proposal'], r['core_reason'] = 'non_core', 'review-response-revision chain incomplete'
        elif r['article_class'] == 'non_empirical':
            r['core_proposal'], r['core_reason'] = 'stratum_non_empirical', f"article type {r['article_type']}"
        elif r['article_class'] == 'unknown':
            r['core_proposal'], r['core_reason'] = 'pending', 'article type unknown'
        elif r['discipline_scope'] == 'uncertain':
            r['core_proposal'], r['core_reason'] = 'pending_discipline', 'discipline to be confirmed by team'
        else:
            r['core_proposal'], r['core_reason'] = 'core', ''
    eligible = [r for r in rows if r['core_proposal'] == 'core']
    reviews = sorted((r for r in eligible if r['article_class'] == 'review'),
                     key=lambda r: (r['origin'] != 'candidate-v0.1.0', -r['v1_reports'], r['paper_id']))
    cap = int(REVIEW_CAP * len([r for r in eligible if r['article_class'] != 'review']) / (1 - REVIEW_CAP))
    for r in reviews[cap:]:
        r['core_proposal'], r['core_reason'] = 'reserve_review_cap', f'review share capped at {REVIEW_CAP:.0%} of core'

    rows.sort(key=lambda r: (r['origin'], r['paper_id']))
    with (OUT / 'master_table_v0.1.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    core = [r for r in rows if r['core_proposal'] == 'core']
    summary = dict(
        papers=len(rows), by_origin=collections.Counter(r['origin'] for r in rows),
        core_proposal=collections.Counter(r['core_proposal'] for r in rows),
        core_by_discipline=collections.Counter(r['discipline_oecd'] for r in core),
        core_by_article_class=collections.Counter(r['article_class'] for r in core),
        core_by_platform=collections.Counter(r['paper_id'].split(':')[0] for r in core),
        core_v1_post_2025_06=sum(r['v1_post_2025_06'] for r in core),
        core_missing_v1_date=sum(not r['v1_date'] for r in core),
        core_by_chain=collections.Counter(r['chain_status'] for r in core),
        models_called=False)
    (OUT / 'master_table_v0.1_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
