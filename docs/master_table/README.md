# 候选论文总表 v0.1

`master_table_v0.1.csv` 合并了 candidate-v0.1.0 的 119 篇论文与 intake batch-01 的 88 篇，共 207 篇。表中的学科、文章类型和核心集划分都只是**建议**，须由团队确认后再锁定。生成过程中没有调用模型。

重新生成：先运行 `python3 scripts/download_assets.py`，再执行 `git fetch origin intake/batch-01`，最后运行 `python3 scripts/build_master_table.py`。

## 字段来源

| 字段 | 来源 | 可靠程度 |
|---|---|---|
| `discipline_oecd`（原有 119 篇） | `discipline_proposals_v0.1.csv`，**仅依据题名**给出的 OECD 学科建议 | 待团队确认；`uncertain` 共 16 篇 |
| `discipline_oecd`（新增 88 篇） | intake 元数据 | 待团队确认 |
| `article_type` | ORE/F1000：出版社 PDF 首页或平台 HTML 标注。PeerJ：稿件上没有印类型，按题名推断 | PeerJ 的推断需要核对 |
| `v1_date` / `v2_date` | ORE/F1000：PDF 封面上的 First/Latest published 日期，或 intake 元数据。PeerJ：文件名中的**投稿日期** | PeerJ 的日期是投稿日期，不是公开日期 |
| `t1_page_images` / `t3_visual_pages` / `image_evidence_items` | 现有 `input.json` 和评分卡 | 新增 88 篇尚未成题，暂为空 |

## 核心集规则（按顺序判定）

1. `discipline_scope = out`：判为 `exclude`，即不属于 OECD 第 5 大类"社会科学"。
2. 材料链不完整：判为 `non_core`。包括后稿未确认、回应缺失，以及仍处暂缓状态的 T3。
3. Essay、Open Letter、Opinion Article、Data Note、Policy Brief、Correspondence：判为 `stratum_non_empirical`，作为单独分层，不计入核心集。
4. 学科待确认：判为 `pending_discipline`，团队确认后再决定是否进入核心集。
5. 其余论文进入 `core`。其中综述类在核心集中的占比上限为 15%：原有论文优先，其次按 v1 报告多的优先，超出上限的综述判为 `reserve_review_cap`。
6. Research Note 归入"实证/方法"类，视同 Brief Report。

## 模态元数据

题目 `input.json` 的字节和哈希是冻结的约定，因此本表**不改写**已有输入文件，而是在表中统一登记模态信息。新题成题时，统一使用 `required_modalities` 字段。
