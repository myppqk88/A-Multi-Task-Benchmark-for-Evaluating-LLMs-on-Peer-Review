#!/usr/bin/env python3
"""Local deterministic checks only. No model/API calls; no scientific acceptance."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DIMENSIONS = {"evidence_accuracy", "argument_validity", "conclusion_appropriateness"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(value, path):
    if not path:
        return value
    if not path.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def string_leaves(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from string_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_leaves(child)


def compact_whitespace(value):
    return re.sub(r"\s+", "", value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true", help="Still lists missing cards; does not fail on those alone")
    parser.add_argument("--output", default="validation_report.json")
    args = parser.parse_args()
    expected = {}
    for assignment in sorted(ROOT.glob("assignment_*.json")):
        for paper in json.loads(assignment.read_text()):
            for q in paper["questions"]:
                expected[q["题号"]] = q
    required = json.loads((ROOT / "card_schema.json").read_text())["required"]
    errors, warnings, checked, evidence_counts = [], [], [], Counter()
    hash_cache, text_cache, json_cache = {}, {}, {}

    def problem(qid, code, detail, warning=False):
        (warnings if warning else errors).append({"task_id": qid, "code": code, "detail": detail})

    def file_hash(path):
        if path not in hash_cache:
            hash_cache[path] = sha(path)
        return hash_cache[path]

    cards = {p.stem: p for p in (ROOT / "cards").glob("*.json")}
    missing = sorted(set(expected) - set(cards))
    for qid in sorted(set(cards) - set(expected)):
        problem(qid, "unexpected_card", str(cards[qid]))
    for qid, path in sorted(cards.items()):
        if qid not in expected:
            continue
        q = expected[qid]
        try:
            card = json.loads(path.read_text())
        except Exception as exc:
            problem(qid, "invalid_json", str(exc))
            continue
        checked.append(qid)
        for key in required:
            if key not in card:
                problem(qid, "required_field", key)
        for key, value in [("task_id", qid), ("paper_id", q["论文ID"]), ("task", q["任务"]),
                           ("split", q["用途"]), ("input_path", q["input_path"]),
                           ("input_sha256", q["input_sha256"]), ("expert_gold", None),
                           ("human_review_status", "pending"), ("publication_status", "仅研究团队核验稿")]:
            if card.get(key) != value:
                problem(qid, "field_mismatch", {"field": key, "actual": card.get(key), "expected": value})
        if not path.with_suffix(".md").is_file():
            problem(qid, "missing_readable_card", str(path.with_suffix(".md")))
        inp = REPO / q["input_path"]
        if not inp.is_file() or file_hash(inp) != q["input_sha256"]:
            problem(qid, "changed_original_input", str(inp))
        input_data = json.loads(inp.read_text())
        material = input_data.get("materials", input_data.get("input", {}))
        material_strings = list(string_leaves(material))
        material_compact = [compact_whitespace(s) for s in material_strings]
        declared_images = []
        for value in material_strings:
            if Path(value).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and len(value) < 4096:
                image_path = Path(value)
                if not image_path.is_absolute():
                    image_path = inp.parent / image_path
                if image_path.is_file():
                    declared_images.append(image_path)
        evidences = card.get("evidence", [])
        if not evidences:
            problem(qid, "no_evidence", "Every card must have source evidence or an explicit source-gap card")
        ids = [e.get("id") for e in evidences]
        if any(not isinstance(eid, str) or not eid.strip() for eid in ids):
            problem(qid, "empty_evidence_id", ids)
        if len(ids) != len(set(ids)):
            problem(qid, "duplicate_evidence_id", ids)
        visible_ids = set()
        for e in evidences:
            eid = e.get("id")
            try:
                source = Path(e["source_path"])
                if not source.is_absolute():
                    source = REPO / source
                if not source.is_file():
                    raise ValueError("source file missing: " + str(source))
                if file_hash(source) != e["source_sha256"]:
                    raise ValueError("source SHA256 mismatch")
                if e.get("model_visible") and e.get("reference_only"):
                    raise ValueError("model_visible and reference_only both true")
                if e.get("model_visible"):
                    visible_ids.add(eid)
                if q["任务"] == "T2" and source.resolve() != inp.resolve():
                    problem(qid, "t2_external_evidence", eid)
                if e.get("evidence_type") == "image":
                    if not e.get("observation"):
                        raise ValueError("image observation missing")
                    if e.get("model_visible") and not any(file_hash(p) == file_hash(source) for p in declared_images):
                        raise ValueError("visible image not declared in current task input")
                    evidence_counts["image"] += 1
                    continue
                if source not in text_cache:
                    text_cache[source] = source.read_text(encoding="utf-8")
                text = text_cache[source]
                loc = e["locator"]
                if "json_pointer" in loc:
                    if source not in json_cache:
                        json_cache[source] = json.loads(text)
                    text = pointer(json_cache[source], loc["json_pointer"])
                if not isinstance(text, str):
                    raise ValueError("locator must resolve to string")
                if "text_span" in loc:
                    start, end = loc["text_span"]
                    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end <= len(text):
                        raise ValueError("invalid character span")
                    text = text[start:end]
                if text != e["quote"]:
                    raise ValueError("quote does not equal source locator")
                if not text.strip():
                    raise ValueError("empty quote")
                if e.get("model_visible") and not any(compact_whitespace(text) in s for s in material_compact):
                    raise ValueError("visible quote absent from current task materials (including whitespace-normalized comparison)")
                evidence_counts["text"] += 1
            except Exception as exc:
                problem(qid, "evidence_error", {"evidence_id": eid, "error": str(exc)})
        refs = card.get("reference_points", [])
        if not refs:
            problem(qid, "no_reference_points", "No substantive reference point")
        if not any(p.get("scoring_use") != "pending_concern_only_not_required_defect" and set(p.get("evidence_ids", [])).intersection(visible_ids) for p in refs):
            problem(qid, "no_visible_candidate_anchor", "Pending human concerns alone cannot constitute a task scoring reference")
        for point in refs:
            for key in ("id", "judgment", "evidence_ids", "importance", "importance_reason", "status", "acceptable_alternatives"):
                if key not in point:
                    problem(qid, "reference_point_field", {"id": point.get("id"), "field": key})
            referenced = set(point.get("evidence_ids", []))
            if not referenced <= set(ids):
                problem(qid, "unknown_evidence_id", {"point": point.get("id"), "ids": sorted(referenced-set(ids))})
            if not referenced:
                problem(qid, "unanchored_reference_point", point.get("id"))
            if point.get("status") not in {"supported", "partly_supported", "disputed", "unresolved"}:
                problem(qid, "invalid_point_status", point.get("id"))
            if point.get("scoring_use") not in {None, "candidate_anchor_subject_to_human_review", "pending_concern_only_not_required_defect"}:
                problem(qid, "invalid_scoring_use", point.get("id"))
            if point.get("scoring_use") == "pending_concern_only_not_required_defect" and not point.get("verification_requirement"):
                problem(qid, "pending_point_verification_missing", point.get("id"))
            if q["任务"] in {"T1", "T3"} and not referenced.intersection(visible_ids):
                problem(qid, "reference_without_visible_support", point.get("id"), warning=True)
        if q["任务"] in {"T1", "T3"} and not card.get("concern_coverage"):
            problem(qid, "missing_concern_coverage", "List substantive concerns and dispositions; source gaps must be explicit")
        point_ids = {p.get("id") for p in refs}
        if len(point_ids) != len(refs) or any(not isinstance(pid, str) or not pid.strip() for pid in point_ids):
            problem(qid, "invalid_reference_point_ids", [p.get("id") for p in refs])
        for concern in card.get("concern_coverage", []):
            if not isinstance(concern, dict):
                problem(qid, "coverage_format", "Coverage entries must be objects")
                continue
            cids = concern.get("reference_point_ids", [])
            if concern.get("point_id"):
                cids = [concern["point_id"]]
            if not set(cids) <= point_ids:
                problem(qid, "coverage_unknown_point", cids)
        if q["任务"] == "T3" and not card.get("human_reference_use"):
            problem(qid, "missing_human_reference_use", "Record target-version human review use or explicit unavailable/exclusion reason")
        human_use = card.get("human_reference_use", {})
        if isinstance(human_use, dict) and human_use.get("original_pdf"):
            human_pdf = REPO / human_use["original_pdf"]
            if not human_pdf.is_file() or file_hash(human_pdf) != human_use.get("original_pdf_sha256"):
                problem(qid, "human_reference_pdf_hash", str(human_pdf))
        bindings = card.get("dimension_bindings", {})
        if set(bindings) != DIMENSIONS:
            problem(qid, "dimensions", sorted(bindings))
        for name, value in bindings.items():
            for key in ("rule_ref", "focus", "high_score_conditions", "low_score_risks", "boundary_2_3", "boundary_3_4"):
                if not value.get(key):
                    problem(qid, "dimension_binding_field", {"dimension": name, "field": key})
        explicit_levels = [v.get("levels") for v in bindings.values()]
        if len(explicit_levels) == 3 and all(explicit_levels) and all(x == explicit_levels[0] for x in explicit_levels[1:]):
            problem(qid, "identical_dimension_levels", "Three dimensions have identical task-specific level definitions")
        scope = card.get("read_scope", {})
        for key in ("read", "not_read", "verification_limits"):
            if key not in scope:
                problem(qid, "read_scope_field", key)
        for item in card.get("expert_queue", []):
            if not item.get("question") or not item.get("why_needed"):
                problem(qid, "expert_queue_unspecific", item)
    frozen = json.loads((ROOT / "source_freeze_manifest.json").read_text())
    rules = json.loads((ROOT / "公共五级评分规则.json").read_text())
    if set(rules.get("dimensions", {})) != DIMENSIONS:
        problem("SHARED_RULES", "dimensions", list(rules.get("dimensions", {})))
    for dim, definition in rules.get("dimensions", {}).items():
        if set(definition.get("anchors", {})) != {"0", "1", "2", "3", "4"}:
            problem("SHARED_RULES", "five_levels", dim)
    frozen_checked = 0
    for name, digest in frozen["files"].items():
        path = REPO / name
        if not path.is_file() or file_hash(path) != digest:
            problem("SOURCE_FREEZE", "changed_frozen_file", name)
        frozen_checked += 1
    originals = {}
    catalog = json.loads((ROOT / "source_catalog.json").read_text())
    for paper in catalog.values():
        for source in paper["manuscripts"] + paper["process_sources"]:
            name, digest = source["original_path"], source["original_sha256"]
            if name in originals and originals[name] != digest:
                problem("SOURCE_CATALOG", "conflicting_source_hash", name)
            originals[name] = digest
    for name, digest in originals.items():
        path = REPO / name
        if not path.is_file() or file_hash(path) != digest:
            problem("SOURCE_CATALOG", "original_source_hash_mismatch", name)
    report = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Deterministic coverage, source identity, exact quotations and schema checks only; not scientific or expert acceptance.",
        "expected_cards": len(expected), "checked_cards": len(checked), "missing_cards": missing,
        "checked_evidence": dict(evidence_counts), "frozen_files_checked": frozen_checked,
        "original_source_files_checked": len(originals),
        "errors": errors, "warnings": warnings,
        "structural_pass": not errors and not missing,
        "expert_validated": False, "models_evaluated": False,
    }
    (ROOT / args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("expected_cards", "checked_cards", "checked_evidence", "frozen_files_checked", "structural_pass")}, ensure_ascii=False))
    print(json.dumps({"missing": len(missing), "errors": len(errors), "warnings": len(warnings)}, ensure_ascii=False))
    raise SystemExit(1 if errors or (missing and not args.partial) else 0)


if __name__ == "__main__":
    main()
