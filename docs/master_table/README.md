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

## v0.2：团队决定与主分析集（2026-10-24）

`master_table_v0.2.csv` 新增 `set` 字段，由 `python3 scripts/select_main_set.py` 生成，随机种子 20261024，结果可以复现。

团队决定：
- 原有论文中学科不确定的 16 篇不再收录，判为 `exclude`。文件保留在仓库中以便溯源。
- 主分析集 100 篇，其中教育学不超过 25 篇，综述不超过 15 篇。
- 主分析集以外的核心论文作为扩展集（`extension`，39 篇），后续再做。

抽样规则：
- `development` 划分的论文曾用于编写原有评分卡，因此只能进入校准池（`calibration_pool`，16 篇），不进入主分析集。
- 在学科层内，再按 v1 公开时间（以 2025-06-01 为界）分层随机抽取。学科配额用最大余数法分配，各时间层按比例分配。
- 综述超出上限时，用同学科、同时间层的非综述论文替换。

结果（详见 `master_table_v0.2_summary.json`）：
- 主分析集 100 篇：2025-06 之后公开的 30 篇；ORE 51 篇、F1000 45 篇、PeerJ 4 篇。
- 已建好三个环节题目的 20 篇，部分建好的 32 篇，尚未成题的 48 篇。
- 新增论文中的 ORE:1-28 学科仍待确认，暂不纳入。

### 修订记录：2026-10-25

修正 `build_master_table.py` 的一处判定错误：补件后仍缺作者回应的论文（ORE:4-67、F1000:156744 等），原先被误判为"补件后材料链完整"，现改判为 `partial_responses_missing`。

这一修正使核心集规模和综述名额发生变化，用同一随机种子重新抽样后，主分析集有 6 篇论文发生替换：
- 移出：F1000:132112、F1000:163166、ORE:1-34、ORE:4-169；
- 移入：ORE:1-40、ORE:1-90、F1000:163068、ORE:1-42。

主分析集在此之前尚未用于任何成题或评分。v0.1 和 v0.2 两张表都已用修正后的脚本重新生成。
