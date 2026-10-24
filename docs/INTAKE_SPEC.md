# 新增素材收录规范（intake batch-01）

本规范供本地整理工具（含本地 AI 助手）向仓库提交**原始素材**使用。只收原始材料，不生成任何评审、评分卡、标签或摘要。收到后由仓库维护方统一核验、成题和制卡。

## 1. 收录目标

本批有两项任务：

- **A. 补缺**：补齐现有题库中材料链不完整的论文（第 5 节）。
- **B. 扩充**：新增 **80–120 篇**社会科学"全链条"候选论文。预计核验后保留约 50–60 篇，使核心分析集达到约 100 篇。

## 2. 纳入标准（B 类每篇须全部满足）

1. **学科**：属于 OECD Fields of Science 第 5 大类"社会科学"，即心理学、经济与商业、教育、社会学、法学、政治学、社会与经济地理、媒体与传播、其他社会科学。哲学、语言学、艺术、纯工程、临床医学不收。跨学科论文须以社会科学研究问题为主，有疑问时标 `discipline_uncertain: true`。
2. **全链条材料**，四项缺一不可：
   - 前稿 v1 全文（PDF，原始字节）；
   - 针对 v1 的**独立、完整的审稿报告原文**，至少 1 份，建议 2 份或以上。编辑决定信，或作者回信中引述的审稿意见，**不算**；
   - 作者针对这些报告的**逐条回应**；
   - 修订稿 v2 全文（PDF）。
3. **时间可核**：每份文件都有可核的公开日期，并能确定"报告针对哪一版、回应答复哪份报告、修订稿是哪一版"。
4. **来源**：优先 Open Research Europe、F1000Research 及其他公开完整评审和回应的平台。PeerJ 只收公开了完整 review history 的论文。
5. **年份**：尽量覆盖不同年份。**2025 年 6 月及以后公开的论文请尽可能多收**，用于后续的污染对照。
6. **排除**：已在本仓库的论文不收。已有论文 ID 见 `evaluation/source_catalog.json` 的键名，例如 `ORE:5-107`、`F1000:134799`、`PeerJ:1604`。
7. **有多模态内容的论文优先**：正文中有实质性的表格、统计输出、模型图或量表图。

## 3. 每篇论文的目录结构

```text
intake/batch-01/<platform>_<article_id>/
  metadata.json
  versions/v1.pdf
  versions/v2.pdf
  versions/v3.pdf               （如有）
  reviews/R1_v1.pdf|html|txt     原始格式保存；另附同名 .txt 纯文本
  reviews/R2_v1.*
  responses/R1_v1_response.*     对应 R1_v1 的作者回应，原始格式 + .txt
  responses/R2_v1_response.*
  supplements/                   论文正式附件（如有），原始文件名
  source_pages/                  评审页、版本页的 HTML 或 PDF 存档（如有）
```

`metadata.json` 字段（不确定的填 `null`，不要猜）：

```json
{
  "platform": "ORE | F1000 | PeerJ | 其他平台名",
  "article_id": "平台内编号",
  "doi": "...",
  "title": "...",
  "discipline_oecd": "5.x 名称",
  "discipline_uncertain": false,
  "license": "如 CC BY 4.0；未知填 null",
  "versions": [
    {"label": "v1", "file": "versions/v1.pdf", "public_date": "YYYY-MM-DD", "url": "..."}
  ],
  "reviews": [
    {"id": "R1_v1", "on_version": "v1", "reviewer": "署名或 anonymous",
     "recommendation": "原文中的推荐（如 Approved with reservations）",
     "date": "YYYY-MM-DD", "file": "reviews/R1_v1.pdf", "url": "..."}
  ],
  "responses": [
    {"id": "R1_v1_response", "answers": "R1_v1", "date": "YYYY-MM-DD",
     "file": "responses/R1_v1_response.txt", "url": "..."}
  ],
  "notes": "任何缺口或疑点"
}
```

## 4. 上传方式

1. 新建分支 `intake/batch-01`，不要直接改 `main`，也不要修改仓库中已有的文件。
2. 只把 `metadata.json`、`.txt` 纯文本和 `intake/batch-01/manifest.csv` 提交进 Git。
3. PDF、HTML 存档、图片、Word 等二进制文件按论文目录打包成若干 `tar.gz` 分卷，每卷不超过 1.9 GB。分卷上传到新 Release，标签为 `intake-batch-01`，指向该分支的提交。
4. `manifest.csv` 每个文件一行，列为：`paper_dir,relative_path,bytes,sha256,in_git(yes/no),archive_name`。
5. 不得上传与论文无关的文件、个人名单、账号信息或任何 API 密钥。

## 5. 现有题库的补缺清单（A 类）

文件仍按第 3 节结构放在 `intake/batch-01/fill_<原ID，冒号改下划线>/`，例如 `fill_PeerJ_1604/`，只放缺失的部分。

| 论文 | 缺什么 |
|---|---|
| PeerJ 1604, 125, 10705, 3082, 19382, 16184, 5414, 1050, 19554, 1690, 2011, 12078, 20600, 737, 2506, 2087, 22, 883 | 第一轮的独立完整审稿报告原文（PeerJ review history 页面），以及对应的作者逐条回应 |
| ORE:4-67, ORE:5-64, ORE:2-80, F1000:156744 | 与审稿报告时间对应的作者回应，并注明回应日期和所答复的报告 |
| ORE:1-150（T3_D02_R1） | GRRIP_RPO_survey_data_documentation.pdf、GRRIP_researcher_survey_data_documentation.pdf、GRRIP_stakeholder_survey_data_documentation.pdf、GRRIP_researcher_survey_structure.csv、GRRIP_stakeholder_survey_structure.csv |
| T3_D04_R1、T3_D20_R1 | 见各题目录 `data/question_bank/T3_轮次综合判断/<题号>/暂缓原因.txt` 中列出的文件 |

PeerJ 3082（盲人振动导航）学科可能不属社会科学，可以不补。

## 6. 禁止事项

- 不得用模型生成、改写、翻译或总结任何评审、回应或稿件内容。
- 找不到原文时如实记为缺失，不得用摘要或转述代替。
- 不判断论文质量，不写评分或标签。
