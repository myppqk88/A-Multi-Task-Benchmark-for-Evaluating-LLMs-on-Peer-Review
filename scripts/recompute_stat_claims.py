#!/usr/bin/env python3
"""Recompute the statistical claims in pilot reference cards from the numbers the manuscripts report.

Each check names the card point it verifies (task_id and provenance 'from'), the reported numbers,
quotes that must occur in the model-visible input, and the recomputation. A claim counts as
verified when the recomputed value contradicts the reported one by the stated rule. Checks that
need a figure read off a page image are listed as requiring a human look. The human adjudicator
then only decides how much the error matters, not whether the arithmetic is right.
Writes evaluation/cards_pilot/stat_recompute.json.
"""
import json
import math
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_card_drafts import norm, strip_line_numbers, strings  # noqa: E402


def visible_text(task_id):
    data = json.loads((ROOT / 'pilot/inputs' / task_id / 'input.json').read_text(encoding='utf-8'))
    raw = ' '.join(strings(data))
    return norm(raw), norm(strip_line_numbers(raw))


def chi2_min_p(x):
    """Smallest p-value the statistic could have under any df from 1 to 10 (df is not reported)."""
    return min(stats.chi2.sf(x, df) for df in range(1, 11))


def t_two_sided(t, df):
    return 2 * stats.t.sf(abs(t), df)


def check_d01_chi2():
    x, reported = 2.632, 0.004
    p = chi2_min_p(x)
    return {'reported': f'χ2={x}, P={reported}', 'recomputed': f'over df 1–10 the smallest p is {p:.3f}',
            'contradicts': p > reported * 5, 'note': 'df not reported; no df in 1–10 makes χ2=2.632 give p≈.004'}


def check_d01_health():
    students, workers = 46.50, 70.51
    return {'reported': 'text: students hope more for health; Table 3 health: students 46.50%, workers 70.51%',
            'recomputed': f'workers − students = {workers - students:.2f} percentage points',
            'contradicts': workers > students, 'note': 'direction in text is opposite to Table 3'}


def check_d15_t():
    p_main = t_two_sided(1.560, 200)
    p_df2 = t_two_sided(0.005, 2)
    return {'reported': 'Table 4 t=1.560, Sig.(2-tailed)=.120; text reports a significant difference using .028 (Levene); text t(2)=0.005, p=0.05',
            'recomputed': f't=1.560 gives p≈{p_main:.3f} for large df (consistent with .120, i.e. not significant); t(2)=0.005 gives p={p_df2:.3f}',
            'contradicts': p_main > 0.05 and p_df2 > 0.5,
            'note': '.028 is the Levene test for equal variances, not the test of the mean difference'}


def check_d16():
    n1, m1, s1, n2, m2, s2 = 93, 4.38, 0.18, 86, 3.87, 0.13
    sp = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    t_pooled = (m1 - m2) / (sp * math.sqrt(1 / n1 + 1 / n2))
    t_welch = (m1 - m2) / math.sqrt(s1 ** 2 / n1 + s2 ** 2 / n2)
    f = 1.06 / 0.128
    return {'reported': 'Table 2: t=2.05, p=.042 (N 93/86, M 4.38/3.87, SD .18/.13); Table 3: MS 1.06/.128, df 2/261, F=3.78; 179 students',
            'recomputed': f'pooled t={t_pooled:.1f}, Welch t={t_welch:.1f}; F=MS_between/MS_within={f:.2f}; '
                          f'SS check 2.12/2={2.12 / 2:.2f}, 33.34/261={33.34 / 261:.3f}; total df 263 implies N=264, not 179',
            'contradicts': t_pooled > 10 and abs(f - 3.78) > 1,
            'note': 'reported statistics cannot be produced from the table values'}


def check_d09():
    threshold = 6.08 + 3.29 * 42.50
    return {'reported': 'outlier rule: 3.29 SD above mean ($6.08, SD $42.50) → $133.58; groups 250 + 197 + 697 = 1144 vs abstract 447 + 619',
            'recomputed': f'6.08 + 3.29 × 42.50 = {threshold:.2f}; 250 + 197 + 697 = {250 + 197 + 697}; 447 + 619 = {447 + 619}',
            'contradicts': abs(threshold - 133.58) > 1 and 447 + 619 != 1144,
            'note': 'the non-isolating group is 697 in the procedure and 619 in the abstract'}


CHECKS = [
    {'tasks': ['D01_T1_Q01', 'T3_D01_R1'], 'quotes': ['χ2=2.632, P=0.004'], 'fn': check_d01_chi2},
    {'tasks': ['D01_T1_Q01'], 'quotes': ['46.50', '70.51', 'with students hoping more for health'], 'fn': check_d01_health},
    {'tasks': ['D15_T1_Q01', 'T3_D15_R1'], 'quotes': ['1.560', '.120', '4.899', '.028'], 'fn': check_d15_t},
    {'tasks': ['D16_T1_Q01', 'T3_D16_R1'], 'quotes': ['4.38 0.18 2.05 0.042', '3.87 0.13', '33.34 261 0.128', '1.06 3.78 0.026'], 'fn': check_d16},
    {'tasks': ['T3_D09_R1'], 'quotes': ['6.08 USD, SD = $42.50 USD', 'neither (n = 697)', 'or not (n = 619)', '133.58'], 'fn': check_d09},
]
NEEDS_IMAGE = [{'task': 'D20_T1_Q01', 'claim': 'A03 item scores do not add up to the Total column',
                'why': 'scores are only in the attachment page image; a person must read page 4 of A03'}]


def main():
    out = []
    for c in CHECKS:
        result = c['fn']()
        found = {}
        for task in c['tasks']:
            texts = visible_text(task)
            found[task] = {q: any(norm(q) in t for t in texts) for q in c['quotes']}
        result['quotes_found_in_input'] = found
        result['contradicts'] = bool(result['contradicts'])
        result['verified'] = result['contradicts'] and all(all(v.values()) for v in found.values())
        result['tasks'] = c['tasks']
        out.append(result)
    report = {'checks': out, 'needs_human_image_check': NEEDS_IMAGE}
    (ROOT / 'evaluation/cards_pilot/stat_recompute.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for r in out:
        missing = [f'{t}:{q}' for t, qs in r['quotes_found_in_input'].items() for q, ok in qs.items() if not ok]
        print(r['tasks'], 'verified' if r['verified'] else 'NOT verified', '|', r['recomputed'], '| missing quotes:', missing)


if __name__ == '__main__':
    main()
