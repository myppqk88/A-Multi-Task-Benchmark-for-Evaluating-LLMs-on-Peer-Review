#!/usr/bin/env python3
"""Check portable candidate data; --full also checks downloaded source evidence."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    binaries=json.loads((ROOT/'data/binary_assets.json').read_text())
    binary_paths={x['path']:x['sha256'] for x in binaries['files']}
    tracked=0
    for record in json.loads((ROOT/'data/export_provenance.json').read_text())['files']:
        p=ROOT/record['path']
        if record['path'] in binary_paths:
            assert record['export_sha256']==binary_paths[record['path']]
            if not args.full: continue
        assert p.is_file(), f'Missing {record["path"]}; download Release assets for --full'
        assert sha(p)==record['export_sha256'],f'Checksum mismatch: {record["path"]}'
        tracked+=1
        if p.name=='input.json': assert record['local_snapshot_sha256']==record['export_sha256']
    cards=[json.loads(p.read_text()) for p in sorted((ROOT/'evaluation/cards').glob('*.json'))]
    assert len(cards)==282 and len({c['task_id'] for c in cards})==282
    assert Counter(c['task'] for c in cards)=={'T1':63,'T2':122,'T3':97}
    papers=defaultdict(set)
    for c in cards:
        papers[c['split']].add(c['paper_id'])
        assert c['expert_gold'] is None and c['human_review_status']=='pending'
        assert sha(ROOT/c['input_path'])==c['input_sha256']
        assert set(c['dimension_bindings'])=={'evidence_accuracy','argument_validity','conclusion_appropriateness'}
        assert not c['input_path'].startswith('/')
        if c['task']=='T2': assert all(e['source_path']==c['input_path'] for e in c['evidence'])
    assert len(papers['development'])==20 and len(papers['provisional_formal'])==99
    assert not papers['development']&papers['provisional_formal']
    assert sum(p.get('scoring_use')=='pending_concern_only_not_required_defect' for c in cards for p in c['reference_points'])==214
    manifest=json.loads((ROOT/'evaluation/package_manifest.json').read_text())
    assert not manifest['models_evaluated'] and manifest['human_gold_count']==0
    for p,h in manifest['cards_sha256'].items(): assert sha(ROOT/'evaluation'/p)==h
    rule_hash=sha(ROOT/'evaluation/公共五级评分规则.json')
    assert rule_hash==manifest['scoring_rules_sha256']
    with (ROOT/'evaluation/评分表模板.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==282
    for row in rows:
        assert row['card_sha256']==sha(ROOT/'evaluation/cards'/f"{row['task_id']}.json")
        assert row['scoring_rules_sha256']==rule_hash
    print(json.dumps({'cards':len(cards),'papers':sum(map(len,papers.values())),'checked_data_files':tracked,'binary_files':len(binary_paths),'full':args.full,'models_evaluated':False}),flush=True)
    if args.full:
        subprocess.run([sys.executable,str(ROOT/'evaluation/validate_package.py'),'--output','validation_report.json'],cwd=ROOT,check=True)
    else: print('Text/metadata checks passed. Binary source and exact-evidence checks require --full.')
if __name__=='__main__': main()
