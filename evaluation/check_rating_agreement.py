#!/usr/bin/env python3
"""Summarize two independent raters' ordinal agreement; never generates ratings."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIMS = ("evidence_accuracy", "argument_validity", "conclusion_appropriateness")


def describe(pairs):
    matrix = [[0] * 5 for _ in range(5)]
    for a, b in pairs:
        if not isinstance(a, int) or not isinstance(b, int) or not 0 <= a <= 4 or not 0 <= b <= 4:
            raise ValueError("Scores must be integers from 0 to 4")
        matrix[a][b] += 1
    n = len(pairs)
    if not n:
        raise ValueError("No paired ratings")
    left = [sum(row) for row in matrix]
    right = [sum(matrix[i][j] for i in range(5)) for j in range(5)]
    observed_disagreement = sum(abs(a-b) / 4 for a, b in pairs) / n
    expected_disagreement = sum(abs(i-j) / 4 * left[i] * right[j] for i in range(5) for j in range(5)) / (n*n)
    return {
        "n_paired_answers": n,
        "confusion_matrix_rows_rater_a_columns_rater_b_0_to_4": matrix,
        "exact_agreement": sum(a == b for a, b in pairs) / n,
        "within_one_level": sum(abs(a-b) <= 1 for a, b in pairs) / n,
        "two_or_more_levels_apart": sum(abs(a-b) >= 2 for a, b in pairs) / n,
        "mean_absolute_level_difference": sum(abs(a-b) for a, b in pairs) / n,
        "linear_weighted_cohens_kappa": 1 - observed_disagreement / expected_disagreement if expected_disagreement else None,
        "kappa_undefined_reason": "Both raters use the same single category; chance correction is undefined" if not expected_disagreement else None,
        "rater_a_grade_counts": left, "rater_b_grade_counts": right,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ratings", type=Path)
    parser.add_argument("--rater-a", required=True)
    parser.add_argument("--rater-b", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rater_a == args.rater_b:
        raise ValueError("Choose two distinct raters")
    meta = {c["task_id"]: c for p in (ROOT / "cards").glob("*.json") for c in [json.loads(p.read_text())]}
    card_hashes = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "cards").glob("*.json")}
    rules_hash = hashlib.sha256((ROOT / "公共五级评分规则.json").read_bytes()).hexdigest()
    records, skipped = {}, Counter()
    with args.ratings.open(encoding="utf-8-sig", newline="") as f:
        for line, row in enumerate(csv.DictReader(f), 2):
            if row.get("rater_id") not in {args.rater_a, args.rater_b}:
                skipped["other_or_blank_rater"] += 1
                continue
            if row.get("rating_round") != "independent":
                skipped["not_independent_round"] += 1
                continue
            qid = row.get("task_id", "")
            if qid not in meta or not row.get("model_id", "").strip():
                raise ValueError(f"row {line}: unknown task or blank model")
            values = [row.get(d) for d in DIMS]
            if any(v not in {"0", "1", "2", "3", "4"} for v in values):
                raise ValueError(f"row {line}: independent completed scores must all be 0–4")
            if row.get("card_sha256") != card_hashes[qid] or row.get("scoring_rules_sha256") != rules_hash:
                raise ValueError(f"row {line}: missing or stale reference card/shared rules hash")
            response_path = Path(row.get("response_path", ""))
            if not response_path.is_absolute():
                response_path = args.ratings.resolve().parent / response_path
            if not response_path.is_file() or hashlib.sha256(response_path.read_bytes()).hexdigest() != row.get("response_sha256"):
                raise ValueError(f"row {line}: response file or hash mismatch")
            key = (row["model_id"], qid, row["rater_id"])
            if key in records:
                raise ValueError(f"row {line}: duplicate independent rating {key}")
            records[key] = row
    groups, unmatched = defaultdict(list), []
    objects = sorted({(model, qid) for model, qid, rater in records})
    for model, qid in objects:
        a = records.get((model, qid, args.rater_a))
        b = records.get((model, qid, args.rater_b))
        if a is None or b is None:
            unmatched.append({"model_id": model, "task_id": qid})
            continue
        if any(a[k] != b[k] for k in ("response_sha256", "card_sha256", "scoring_rules_sha256")):
            raise ValueError(f"{model}/{qid}: raters did not rate the same response and reference version")
        c = meta[qid]
        groups[(model, c["task"], c["split"], c["unit"])].append((c, a, b))
    output = []
    for group, rows in sorted(groups.items()):
        item = dict(zip(("model_id", "task", "split", "unit"), group))
        item["n_papers"] = len({c["paper_id"] for c, a, b in rows})
        item["dimensions"] = {d: describe([(int(a[d]), int(b[d])) for c, a, b in rows]) for d in DIMS}
        output.append(item)
    result = {"rater_a": args.rater_a, "rater_b": args.rater_b, "groups": output,
              "unmatched_answers": unmatched, "skipped": dict(skipped),
              "scope": "Question-level descriptive agreement, not validity, not a scientific gold standard.",
              "limitations": ["No significance test or confidence interval; shared-paper dependence remains.",
                              "Do not estimate reliability from post-discussion consensus ratings.",
                              "Five observed categories do not establish five discriminable ability levels.",
                              "Sparse or restricted grade ranges can make kappa unstable; report the confusion matrices."]}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"paired_groups": len(output), "unmatched_answers": len(unmatched)}))


if __name__ == "__main__":
    main()
