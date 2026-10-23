#!/usr/bin/env python3
"""Deterministic synthetic fixtures only. Does not call or evaluate a model."""
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    summary, agreement = load('summarize_scores'), load('check_rating_agreement')
    meta = {f'q{i}': {'task_id': f'q{i}', 'paper_id': 'p1' if i < 3 else 'p2', 'task': 'T2', 'split': 'development', 'unit': 'single_concern'} for i in range(4)}
    rows = [{'task_id': f'q{i}', 'model_id': 'synthetic', 'score_status': 'final', **{d: '4' if i < 3 else '0' for d in summary.DIMS}} for i in range(4)]
    assert summary.aggregate(rows, meta)['groups'][0]['dimensions'][summary.DIMS[0]]['paper_equal_mean'] == 2
    assert agreement.describe([(0, 0), (4, 4)])['linear_weighted_cohens_kappa'] == 1
    assert agreement.describe([(0, 4), (4, 0)])['linear_weighted_cohens_kappa'] == -1
    assert agreement.describe([(4, 4), (4, 4)])['linear_weighted_cohens_kappa'] is None
    for bad in [rows + [rows[0]], [{**rows[0], 'evidence_accuracy': ''}], [{**rows[0], 'evidence_accuracy': '5'}], [{**rows[0], 'score_status': 'typo'}]]:
        try:
            summary.aggregate(bad, meta)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid score record accepted')
    cardpath = sorted((ROOT / 'cards').glob('*.json'))[0]
    card = json.loads(cardpath.read_text())
    results = []
    with tempfile.TemporaryDirectory(prefix='benchmark_utility_check_') as tmp:
        directory = Path(tmp)
        response = directory / 'synthetic.txt'
        response.write_text('SYNTHETIC FIXTURE ONLY')
        base = {'task_id': card['task_id'], 'model_id': 'synthetic_fixture_only', 'score_status': 'final', 'rating_round': 'independent', 'rater_id': 'synthetic_A', 'response_path': str(response), 'response_sha256': digest(response), 'card_sha256': digest(cardpath), 'scoring_rules_sha256': digest(ROOT / '公共五级评分规则.json')}
        for dim in summary.DIMS:
            base.update({dim: '3', dim + '_reason': 'Synthetic parser check only', dim + '_output_excerpt': 'SYNTHETIC FIXTURE ONLY'})
        def run(script, records, extra, accepted):
            fixture = directory / 'fixture.csv'
            with fixture.open('w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=list(base))
                writer.writeheader()
                writer.writerows(records)
            process = subprocess.run([sys.executable, str(ROOT / script), str(fixture), '--output', str(directory / 'result.json'), *extra], capture_output=True, text=True)
            assert (process.returncode == 0) == accepted, (script, process.stderr)
            results.append({'script': script, 'expected_acceptance': accepted, 'passed': True})
        run('summarize_scores.py', [base], [], True)
        run('summarize_scores.py', [{**base, 'scoring_rules_sha256': 'wrong'}], [], False)
        run('summarize_scores.py', [{**base, 'argument_validity_output_excerpt': 'absent'}], [], False)
        run('check_rating_agreement.py', [base, {**base, 'rater_id': 'synthetic_B'}], ['--rater-a', 'synthetic_A', '--rater-b', 'synthetic_B'], True)
        run('check_rating_agreement.py', [base, {**base, 'rater_id': 'synthetic_B', 'response_sha256': 'wrong'}], ['--rater-a', 'synthetic_A', '--rater-b', 'synthetic_B'], False)
    result = {'scope': 'Synthetic software fixtures only; no model outputs, benchmark grades, or human reliability estimates', 'aggregation_paper_weighting_passed': True, 'kappa_edge_cases_passed': True, 'invalid_score_rejection_passed': True, 'cli_checks': results, 'temporary_fixtures_deleted': True, 'models_evaluated': False}
    (ROOT / 'utility_validation_report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result))

if __name__ == '__main__':
    main()
