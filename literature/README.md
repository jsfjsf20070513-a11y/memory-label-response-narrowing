# 文献检索证据包

这是截至 2026-07-29 的文献检索快照。它把“最终综述”“完整去重语料”“检索方法”“筛选记录”“引用信息”“许可核验”和“可以合法再分发的原始 PDF”放在同一个目录中。本包不是正式实验数据，也不是 PRISMA 系统综述或对相关文献的穷尽性证明。

## 一眼看懂

- 去重后共登记 **51 篇**文献。
- 其中 **26 篇**进入最终综述正文，另外 **25 篇**作为背景、近邻或方法线索保留。
- **43 篇**有明确允许分享的 Creative Commons 许可，原始 PDF 已提交。
- **8 篇**虽然有官方公开阅读链接，但没有核实到允许本项目重新托管 PDF 的许可，因此只保留链接和元数据。
- 最终综述没有发现一篇论文同时满足本项目预先定义的五项条件，但这只是“在本轮登记范围内未检出”，不能写成“从来没人做过”。
- 43 份 PDF 共约 **124 MiB**；这是为了保留本轮许可版本快照而有意纳入的仓库体积。

## 从哪里开始

1. 想快速理解结论：读 [`review.md`](review.md)。
2. 想看检索是否可复核：读 [`search/search_protocol.md`](search/search_protocol.md) 和 [`search/query_log.md`](search/query_log.md)。
3. 想看全部 51 篇：打开 [`search/screening_inventory.csv`](search/screening_inventory.csv) 或 [`metadata/papers.json`](metadata/papers.json)。
4. 想导入文献管理软件：使用 [`metadata/references.bib`](metadata/references.bib)。
5. 想核对 PDF 是否能提交：看 [`metadata/download_manifest.json`](metadata/download_manifest.json) 和 [`papers/LICENSES.md`](papers/LICENSES.md)。

## 目录说明

| 路径 | 内容 |
|---|---|
| `review.md` | 交付给项目成员的中文综述；与桌面版逐字一致 |
| `search/search_protocol.md` | 问题、时间窗、来源、纳排标准、去重与停止规则 |
| `search/query_log.md` | 本轮使用的关键词逻辑与查询串 |
| `search/skill_selection.md` | 为什么使用学术检索 Skill，以及它在本轮做了什么 |
| `search/corpus_seed.json` | 51 条语料的来源标识、用途和筛选决策 |
| `search/screening_inventory.csv` | 便于人工查看和排序的筛选清单 |
| `search/evidence_notes.md` | 观察、解释和不能越过的推断边界 |
| `metadata/papers.json` | 结构化元数据、摘要、OA/许可状态、PDF 与代码链接 |
| `metadata/references.bib` | BibTeX 引用库 |
| `metadata/download_policy_input.json` | 送入许可感知下载器的冻结输入 |
| `metadata/download_manifest.json` | 每篇的下载/跳过原因、许可证据、文件大小与 SHA-256 |
| `papers/*.pdf` | 43 份许可明确、未经修改的第三方论文 PDF |
| `papers/LICENSES.md` | PDF 许可和署名说明 |

## 关键口径

本包把两件事分开：

- **观察**：在冻结的 Claude Opus 4.6、两道主检验题、单一通道、单一数学背景措辞下，数学背景条件更容易出现“更数学且非数学路径更少”的输出。
- **解释**：现有结果不能证明模型内部机制，不能推广到其他模型或任务，也不能说明“更数学”对用户一定更差。

同样，“公开可读”与“允许重新上传”不是一回事。8 篇 link-only 文献仍完整登记在元数据和引用库中，只是不把 PDF 本体放进仓库。`papers.json` 中的 `full_text_status: open_pdf` 表示网上存在公开阅读入口；下载策略或 manifest 中的 `license_not_redistributable` 表示没有确认本仓库可以重新托管，两者记录的是不同维度。

`metadata_verified` 只表示题名、作者、年份、标识符等书目信息经过核对，不表示论文中的每一项结论都完成了正文逐条核验。最终综述中的具体论断仍应以 [`search/evidence_notes.md`](search/evidence_notes.md) 记录的证据层级和限制为准。

## 校验

在仓库根目录运行：

```bash
python3 scripts/verify_literature_package.py --repo-root .
```

预期结果：

```text
OK: 51 records, 43 licensed PDFs, 8 link-only records
```

若需要从官方来源重抓元数据：

```bash
python3 scripts/build_literature_catalog.py
```

若本地 PDF 缺失，可用已冻结的 manifest 重新下载；大文件支持分段下载：

```bash
python3 scripts/download_literature_pdfs.py \
  --manifest literature/metadata/download_manifest.json \
  --out-dir literature/papers \
  --workers 2 \
  --segments 6

python3 scripts/finalize_literature_downloads.py \
  --papers literature/metadata/papers.json \
  --manifest literature/metadata/download_manifest.json \
  --papers-dir literature/papers \
  --repo-root .
```

元数据和许可可能随出版状态更新。若将来刷新，必须保留抓取日期，不得用新信息静默改写本轮结论。
