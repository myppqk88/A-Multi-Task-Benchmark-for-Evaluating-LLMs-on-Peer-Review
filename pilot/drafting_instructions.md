# 参照卡起草指令（起草者 A 与 B 共用，预实验 v0.2）

本文件是两名起草者的**唯一指令**，双方使用同一版本。完整规范见 `evaluation/参照卡起草规范_v0.2.md` 第 2–4 节；如有冲突，以该规范为准。

## 你的任务

为 `pilot/inputs/manifest.json` 中的每道题写一张参照卡草稿。先做 `pilot_role = calibration` 的 19 题，再做 `blind_check` 的 18 题。参照卡的作用是帮助人工评分者判断模型的回答。它**不是标准答案**，而是"经核实的重要问题清单 + 可接受的不同判断 + 典型错误"。

## 每道题读什么

| 任务 | 判断依据（模型可见，所有参照点必须锚定在这里） | 只供参考的线索（不能作为判定依据） |
|---|---|---|
| T1（`*_T1_Q01`） | `pilot/inputs/<task_id>/input.json` 中的 `input`，包括正文和页面图像 | 同一论文的 `pilot/inputs/T3_<样本号>_R1/input.json` 中 `materials.reviews`，即针对 v1 的真人报告 |
| T2（`*_T2_Q0n`） | 该题 `input`，即一条关切和对应回应 | 无 |
| T3（`T3_*_R1`） | 该题 `materials` 全部内容 | 无 |

**不得使用**：网络检索；论文的其他版本；`evaluation/cards/` 中的旧卡；`data/question_bank/**/private/`；另一位起草者的任何文件，包括 `pilot-drafts-A` 分支。

## 输出

每道题一个 JSON 文件：`pilot/cards_draft/<task_id>/<A 或 B>.json`。结构如下，所有字段都必须有，没有内容时用空数组。

```json
{
  "task_id": "", "paper_id": "", "task": "T1|T2|T3", "unit": "",
  "input_sha256": "manifest.json 中该题的 input_sha256",
  "card_version": "0.2", "drafter": "A|B",
  "reference_points": [
    {
      "id": "P1",
      "judgment": "一句话、可以检验的判断",
      "issue_type": "V1|V2|V3|V4|V5|V6|V7|V8|V9",
      "importance": "high|medium|low",
      "importance_reason": "",
      "origin": "human_review|card_author",
      "human_sources": [{"report_id": "R1", "exact_quote": "真人报告中的逐字原文"}],
      "manuscript_evidence": [
        {"input_field": "JSON 路径，如 input/manuscript_text 或 materials/manuscript_after/text", "exact_quote": "逐字原文"},
        {"input_field": "page_images 或 visual_pages", "page": 6, "observation": "目视记录"}
      ],
      "match_criteria": "模型的一条论点至少要说出什么，才算命中本点",
      "acceptable_alternatives": [],
      "status": "supported|partly_supported|disputed|unresolved"
    }
  ],
  "label_reference": {"primary": "", "acceptable_set": [], "rationale": ""},
  "known_invalid_patterns": [],
  "draft_notes": ""
}
```

- `label_reference`：T2 填 `adequacy_label`，T3 填 `overall_label`；T1 填空字符串和空数组。
- T3 的每个参照点，在 `judgment` 中写明该问题是 `resolved`、`partially_resolved`、`unresolved` 中的哪一种，以及判断依据。

## 规则（要点）

1. 先读完全部真人报告和回应，再读稿件。**一个真人关切对应一个参照点**；多位审稿人提出的同一问题，合并为一个参照点。
2. 每个参照点**必须**在判断依据中找到逐字引文或页码。真人提出、但在材料中找不到依据的关切，标为 `unresolved`，并在 `draft_notes` 中说明原因。
3. 如果真人关切的前提与稿件不符，`status` 标为 `disputed`，并在 `acceptable_alternatives` 中写明"指出这一要求不成立"也是合理的回答。
4. `origin: card_author`（起草者自己发现的问题）每张卡最多 2 个，并且只能是 high 或 medium 重要性。
5. 重要性：
   - `high`：如果成立，会削弱核心主张或主要结论；
   - `medium`：影响次要结论或结论的适用范围；
   - `low`：完善性建议。
6. `match_criteria` 必须具体到问题和位置；`acceptable_alternatives` 必须针对本参照点，不得在不同参照点之间复制同一句话。
7. 所有 `exact_quote` 必须能在对应字段中逐字找到。提交前用 `python3 scripts/check_card_drafts.py` 自检。
8. 不判断论文的整体质量好坏，也不打分；只建立参照。

## 提交

- 起草者 B：推送到分支 `pilot-drafts-B`，只包含 `pilot/cards_draft/*/B.json`。
- 起草者 A：推送到分支 `pilot-drafts-A`。同时在 `claude/upbeat-maxwell-lx1sxw` 上提交 `pilot/cards_draft/A_commitment.json`，内容是每份 A 草稿的 SHA256，用来证明这些草稿在 B 提交之前就已定稿。
- 两份草稿都提交后，再运行合并脚本，生成随机化的 X/Y 合并文件，交给裁决者。
