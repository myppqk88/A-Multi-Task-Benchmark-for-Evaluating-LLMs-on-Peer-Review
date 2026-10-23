# A Multi-Task Benchmark for Evaluating LLMs on Peer Review

本仓库用于同行评议三类任务的实验、评分标准核验与论文写作。我们评价的是模型能否根据材料作出**有证据、推理成立、结论适当的学术判断**，不是模型与真人评议的文字相似度，也不把真人意见自动视为正确答案。

**当前版本：候选题库与评分参照，尚未完成专家金标准和测量效度验证。本版没有模型实验结果。**

## 1. 任务与数据

共 **119 篇论文、282 道题**。所有分组以论文为单位，开发集与暂定正式集没有论文交叉。

| 场景 | 任务 | 开发集 | 暂定正式集 | 合计 |
|---|---|---:|---:|---:|
| T1 原稿评审 | 根据所给稿件指出至多五项重要问题并论证 | 14 | 49 | 63 |
| T2 作者回应评价：单关切 | 判断回应文字是否回答指定关切 | 22 | 80 | 102 |
| T2 作者回应评价：整份报告扩展 | 对完整报告及回应作对应评价 | 0 | 20 | 20 |
| T3 修订后综合判断 | 根据截止时点可用的评审、回应与稿件判断解决情况和遗留问题 | 10 | 87 | 97 |
| 合计 | 20 篇开发论文／99 篇暂定正式论文 | **46** | **236** | **282** |

`provisional_formal` 仍表示**暂定正式集**，不能直接写成已锁定测试集。T2 两种材料单位分别分析；整份报告扩展尚无开发集校准覆盖。三类任务共享科学性评价核心，但材料和允许推断的范围不同，具体以各题 `instruction`、`input` 和 `required_modalities` 为准。

## 2. 如何评价模型回答

1. 读取题目输入，让被测模型仅根据题内材料回答；保存完整输出和运行配置。
2. 评价者读取对应评分卡，核对真人关切、原文证据、允许的不同判断与分档边界。
3. 分别评 **证据准确性、论证成立性、结论适当性**，每维 **0–4 分，共五级**；同时记录理由和模型回答中的具体片段。
4. 同篇多题先在论文内汇总，再按论文等权；按任务、数据划分与 T2 材料单位分别报告三维结果。

评分入口是 [公共五级规则](evaluation/公共五级评分规则.json)、[逐题导航](evaluation/逐题导航.md)和[评分执行说明](evaluation/评分执行说明.txt)。不默认合成为单一总分或“智能分”。结论相同而理由错误、合理反驳真人、材料不足而保留判断，都有相应处理原则。

现有真人评议被整理为 **1,155 条候选参照点**，其中 **214 条待核实关切不可直接计分**，不能作为必答缺陷或扣分依据。所有卡片的 `expert_gold` 为空、`human_review_status` 为 `pending`。卡内 `supported` 是候选证据编码，**不是专家验收结论**；`publication_status` 保留原候选稿标记，公开上传不改变其核验状态。

评分者一致性用于检查评分过程的稳定性，**不等于评分有效**。有效性还需核对证据、测试评分边界、检查合理不同答案，以及少量有针对性的领域核验。具体见[方法依据与低成本验证计划](evaluation/方法依据与低成本验证计划.md)、[校准对照样例](evaluation/校准对照样例.md)与[最近邻研究核对](evaluation/最近邻研究核对.md)。

## 3. 仓库结构

```text
data/
  question_bank/       题面、input.json、材料文本及历史来源记录
  originals/           来源文件；二进制附件由 Release 恢复
  export_provenance.json  本地快照与迁移文件的哈希对应
  binary_assets.json   二进制附件清单与哈希
evaluation/
  cards/               282 份 JSON 评分卡及 Markdown 阅读版
  *.csv                空评分表、人工核验台账和争议清单
  *.py                 来源核验、评分汇总和一致性工具
experiments/           实验记录模板与运行约束；尚无本版模型输出
paper/                 写作入口与历史稿件（legacy）
scripts/               附件下载、仓库完整性检查
docs/                  数据来源、迁移与版本说明
```

题目目录里的 `private/` 是**评价侧与溯源材料**的历史目录名，不是 GitHub 访问控制。仓库与 Release 均公开；这些材料及 `evaluation/` **不得送入被测模型**。题目目录中的旧 `评分规则.txt`、`reference_draft.json` 只保留作历史溯源，现行评分统一使用 `evaluation/`。

## 4. 在新电脑或 GitHub Codespaces 中使用

要求 Python 3.10 或更新版本，评分与校验工具仅用标准库。以下操作不调用任何模型。

```bash
git clone https://github.com/myppqk88/A-Multi-Task-Benchmark-for-Evaluating-LLMs-on-Peer-Review.git
cd A-Multi-Task-Benchmark-for-Evaluating-LLMs-on-Peer-Review
python3 scripts/validate_repository.py
python3 scripts/download_assets.py
python3 scripts/validate_repository.py --full
```

普通 Git 克隆包含题目、文本、评分卡与代码。图片、原始 PDF 和 Word 等二进制文件放在同仓库 [候选版本 Release](https://github.com/myppqk88/A-Multi-Task-Benchmark-for-Evaluating-LLMs-on-Peer-Review/releases/tag/candidate-v0.1.0) 中，下载脚本校验 SHA256 并恢复原目录。**未下载附件时不能运行完整的图文任务，也不能声称复现了完整题库。** 需要网络与约 4 GB 额外可用磁盘空间；成功后可删除 `.asset-cache/` 释放缓存。

在 Codespaces 中打开仓库后，从下载和校验步骤继续。GitHub 网页本身不运行模型；后续应在 Codespaces、本地或计算服务器上配置实验。模型调用程序和付费运行不在本次交付范围内，参见 [实验说明](experiments/README.md)。GitHub Actions 只做无模型的文件和工具检查。

## 5. 填表、汇总与一致性

复制 [评分表模板](evaluation/评分表模板.csv) 另存到 `experiments/ratings/`，不要直接覆盖空模板。记录 `model_id`、`rater_id`、完整回答路径和 SHA256、评分卡及规则哈希、三维分数、理由和回答片段。`pending` 或空白不等于零分。

从仓库根目录执行：

```bash
python3 evaluation/summarize_scores.py experiments/ratings/final.csv --output experiments/results/summary.json
python3 evaluation/check_rating_agreement.py experiments/ratings/independent.csv --rater-a A --rater-b B --output experiments/results/agreement.json
```

以上 CSV 路径是**待填写文件示例**，不是已经存在的实验结果。两名评分者的独立原始记录标记 `rating_round=independent`；协商后的记录另存，不能混入独立一致性计算。工具提供分布、档位差及线性加权 Cohen κ；不生成评分、不提供效度证明，也不自动估计论文聚类置信区间。比较不同模型时使用相同合格题目和论文覆盖。

## 6. 当前核验结果与待办

- 迁移后 282 题机械核验通过：零缺题、零错误；2,074 条文字证据和 70 条图像证据完成定位检查。
- 保留 106 条来源可见性警告；均对应已明确不可直接计分的待核关切。
- 本地原始输入 JSON 字节保持一致；迁移只转换路径元数据并更新相应哈希。详见 [迁移说明](docs/PORTABILITY.md)。
- 27 项争议已按 18 篇论文合并，先由研究团队用已有材料核对，确有专业分歧再请领域专家；还需代表性抽查与评分校准。
- 尚未完成：人工金标准、评分信效度与增量验证、当前版本模型实验、正式结果与论文更新。

这些检查证明文件对应与引文定位，不证明全部学术判断正确。公开评分参照也意味着后续评测必须记录版本、模型日期、访问约束与潜在训练污染，不能把本仓库称为隐藏测试集。

## 7. 论文、来源与许可

[论文写作入口](paper/README.md) 包含可编辑的历史 LaTeX/Word 稿件及必要图件。它们属于旧研究版本，**历史结果未按当前 282 题和三维五级方法重新核验，不能直接作为本版结果**。本次未改写论文论证，也未填入新的实验数据。

原始论文、公开评审与回应保留作者及来源信息。第三方内容的权利仍归原权利人；本仓库不对全部材料统一授予新许可。逐项再分发许可登记尚待完成，不能把公开可访问或平台名称当作全部材料的许可结论。详见 [数据来源与权利说明](docs/DATA_SOURCES.md)。

当前是研究工作版本，尚无可引用的正式论文 DOI。引用本数据版本时请记录仓库地址、Release 标签和具体 commit，不生成虚构论文引用。
