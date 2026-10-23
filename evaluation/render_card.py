#!/usr/bin/env python3
"""Render authoritative reference JSON. Does not change scientific judgments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def display(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join("- " + display(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{k}**：{display(v)}" for k, v in value.items())
    return str(value)


def render(card):
    rules = json.loads((ROOT / "公共五级评分规则.json").read_text())
    lines = [f"# {card['task_id']} 评分参照卡", "", f"论文：{card['paper_id']} ｜ 场景：{card['task']} ｜ 划分：{card['split']} ｜ 单位：{card['unit']}", "",
             "**状态：Astra整理的候选参照，待团队与必要专家核验；不是人工金标准。**", "",
             f"[题目输入](../../{card['input_path']}) ｜ [本卡完整JSON]({card['task_id']}.json)", "",
             "## 关键判断与允许的不同答案", ""]
    for point in card["reference_points"]:
        usage_label = " · 待核实，不可直接计分" if point.get("scoring_use") == "pending_concern_only_not_required_defect" else " · 候选参照"
        lines.extend([f"### {point['id']} · {point['status']}{usage_label}", "", point["judgment"], "",
                      f"证据：{', '.join(point['evidence_ids'])}。重要性：{point['importance']}。{point['importance_reason']}", "",
                      "允许的不同判断：", "", display(point["acceptable_alternatives"]), ""])
        if point.get("scoring_use") == "pending_concern_only_not_required_defect":
            lines.extend(["**使用限制：仅记录待核实关切，不能作为必答缺陷或扣分依据。模型未重复或合理反驳此意见，不因此扣分。**", ""])
        elif point.get("scoring_use") == "candidate_anchor_subject_to_human_review":
            lines.extend(["**用途：候选评分参照，仍须团队核验；不要求模型与此措辞或结论一致。**", ""])
        if point.get("verification_requirement"):
            lines.extend(["核验要求：" + display(point["verification_requirement"]), ""])
    if card.get("concern_coverage"):
        lines.extend(["## 真人关切覆盖与处置", "", display(card["concern_coverage"]), ""])
    if card.get("human_reference_use"):
        lines.extend(["## 修订后真人评议的参照用途", "", display(card["human_reference_use"]), ""])
    lines.extend(["## 三维五级评分", "", "依据完整回答评分；参照点不是命中清单。以下公共档位与逐题边界共同使用。", ""])
    lines.extend([rules.get("task_budget_policy", ""), ""])
    for dim, binding in card["dimension_bindings"].items():
        definition = rules["dimensions"][dim]
        lines.extend([f"### {definition['label']}", "", binding["focus"], "", "| 分值 | 公共档位含义 |", "|---|---|"])
        for level, meaning in definition["anchors"].items():
            lines.append(f"| {level} | {meaning.replace('|', '／')} |")
        lines.extend(["", "**本题2→3分边界：** " + binding["boundary_2_3"], "",
                      "**本题3→4分边界：** " + binding["boundary_3_4"], "",
                      "高分条件：", "", display(binding["high_score_conditions"]), "",
                      "低分风险：", "", display(binding["low_score_risks"]), ""])
        if binding.get("levels"):
            lines.extend(["本题档位示例（与公共规则共同解释）：", "", display(binding["levels"]), ""])
    lines.extend(["## 严重错误与开放答案边界", "", display(card["severe_error_checks"]), ""])
    if card.get("coverage_limit"):
        lines.extend([display(card["coverage_limit"]), ""])
    lines.extend(["## 核验范围", "", display(card["read_scope"]), "", "## 专家待裁决事项", "",
                  display(card["expert_queue"]) if card["expert_queue"] else "目前未列必须外聘裁决事项；仍须团队核验及代表性抽查。", "", "## 来源证据", ""])
    for e in card["evidence"]:
        lines.extend([f"### {e['id']} · {e.get('role', '')}", "",
                      f"[来源文件](../../{e['source_path']}) ｜ 模型可见：{e.get('model_visible')} ｜ 仅参照：{e.get('reference_only')}", ""])
        if e.get("evidence_type") == "image":
            lines.extend(["目视记录：" + e["observation"], ""])
        else:
            quote = e["quote"]
            lines.extend(["> " + quote[:1200].replace("\n", "\n> "), ""])
            if len(quote) > 1200:
                lines.extend(["（此处截断展示，完整逐字引文与定位保存在本卡JSON。）", ""])
            lines.extend(["定位：`" + json.dumps(e["locator"], ensure_ascii=False) + "`", ""])
        lines.extend(["SHA256：`" + e["source_sha256"] + "`", ""])
    lines.extend(["## 使用说明", "", "按题内证据和完整推理评分，不以真人同意或候选标签一致替代科学判断。评分参照只供评价侧使用，不能加入被测模型的题目输入。", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    for path in sorted((ROOT / "cards").glob("*.json")):
        path.with_suffix(".md").write_text(render(json.loads(path.read_text())), encoding="utf-8")
