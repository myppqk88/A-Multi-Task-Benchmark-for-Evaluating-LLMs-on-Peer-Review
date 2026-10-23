#!/usr/bin/env python3
"""Aggregate already completed ratings. Never calls or scores any model."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
DIMS = ("evidence_accuracy", "argument_validity", "conclusion_appropriateness")


def aggregate(rows, metadata):
    seen, accepted, pending = set(), [], 0
    for line, row in enumerate(rows, 2):
        if row.get("score_status") not in {"pending", "provisional", "excluded", "final"}:
            raise ValueError(f"row {line}: unknown score_status")
        if row.get("score_status") != "final":
            pending += 1
            continue
        qid = row.get("task_id", "")
        if qid not in metadata:
            raise ValueError(f"row {line}: unknown task_id {qid}")
        model = row.get("model_id", "").strip()
        if not model:
            raise ValueError(f"row {line}: final score needs model_id")
        key = (model, qid)
        if key in seen:
            raise ValueError(f"row {line}: duplicate final rating for {key}; adjudicate first")
        seen.add(key)
        scores = {}
        for dim in DIMS:
            value = row.get(dim, "")
            if value not in {"0", "1", "2", "3", "4"}:
                raise ValueError(f"row {line}: {dim} must be integer 0–4; missing is not zero")
            scores[dim] = int(value)
        accepted.append({**metadata[qid], "model_id": model, "scores": scores})
    groups = defaultdict(list)
    for record in accepted:
        groups[(record["model_id"], record["task"], record["split"], record["unit"])].append(record)
    output = []
    for key, records in sorted(groups.items()):
        papers = defaultdict(list)
        for record in records:
            papers[record["paper_id"]].append(record)
        item = dict(zip(("model_id", "task", "split", "unit"), key))
        item.update(n_questions=len(records), n_papers=len(papers), dimensions={})
        item["task_ids"] = sorted(r["task_id"] for r in records)
        for dim in DIMS:
            paper_means = {p: mean(r["scores"][dim] for r in rs) for p, rs in papers.items()}
            paper_weighted_distribution = [mean(sum(r["scores"][dim] == k for r in rs) / len(rs) for rs in papers.values()) for k in range(5)]
            item["dimensions"][dim] = {
                "paper_equal_mean": mean(paper_means.values()),
                "paper_means": paper_means,
                "question_grade_counts": [sum(r["scores"][dim] == k for r in records) for k in range(5)],
                "paper_equal_grade_proportions_0_to_4": paper_weighted_distribution,
            }
        output.append(item)
    return {"final_ratings": len(accepted), "pending_or_excluded_rows": pending,
            "groups": output,
            "limitations": ["Descriptive summaries only; ordinal grades are not interval-scale proof.",
                            "No across-task intelligence score. T2 material units remain separate.",
                            "Model comparisons require a common eligible paper/question subset; unequal coverage is not a fair ranking.",
                            "No reliability or validity estimates are produced by this script."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scores", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = {}
    card_hashes = {}
    rules_hash = hashlib.sha256((ROOT / "公共五级评分规则.json").read_bytes()).hexdigest()
    for p in (ROOT / "cards").glob("*.json"):
        d = json.loads(p.read_text())
        metadata[d["task_id"]] = {k: d[k] for k in ("task_id", "paper_id", "task", "split", "unit")}
        card_hashes[d["task_id"]] = hashlib.sha256(p.read_bytes()).hexdigest()
    with args.scores.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for line, row in enumerate(rows, 2):
        if row.get("score_status") != "final":
            continue
        qid = row.get("task_id")
        if row.get("scoring_rules_sha256") != rules_hash:
            raise ValueError(f"row {line}: missing or stale shared scoring rules hash")
        if row.get("card_sha256") != card_hashes.get(qid):
            raise ValueError(f"row {line}: missing or stale reference card hash")
        if not row.get("rater_id", "").strip():
            raise ValueError(f"row {line}: final rating needs rater_id")
        response_path = Path(row.get("response_path", ""))
        if not response_path.is_absolute():
            response_path = args.scores.resolve().parent / response_path
        if not response_path.is_file() or hashlib.sha256(response_path.read_bytes()).hexdigest() != row.get("response_sha256"):
            raise ValueError(f"row {line}: response file or hash mismatch")
        response = response_path.read_text(encoding="utf-8")
        for dim in DIMS:
            if not row.get(dim + "_reason", "").strip():
                raise ValueError(f"row {line}: {dim} needs a scoring reason")
            excerpt = row.get(dim + "_output_excerpt", "")
            valid_empty = not response.strip() and row.get(dim) == "0" and not excerpt.strip()
            if not valid_empty and (not excerpt.strip() or excerpt not in response):
                raise ValueError(f"row {line}: {dim} excerpt must quote the saved model response exactly")
    result = aggregate(rows, metadata)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"final_ratings": result["final_ratings"], "groups": len(result["groups"]),
                      "pending_or_excluded_rows": result["pending_or_excluded_rows"]}))


if __name__ == "__main__":
    main()
