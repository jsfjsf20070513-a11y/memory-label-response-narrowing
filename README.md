# 用户背景标签与模型回答范围

**User Background Labels and Response Breadth in Language Models**

这是一个小型、预注册、可复核的研究项目。我们问的不是“AI 记忆是好是坏”，而是一个更小的问题：

> 面对同一个本可从多个角度回答的问题，当模型提前知道“用户是数学系本科生”时，回答是否更偏数学，同时减少其他方向？

## 当前结论

在冻结的 Claude Opus 4.6、固定题目和最小背景注入下，12 个主检验块中有 8 个同时出现“更数学 + 非数学方向更少”，反向为 0，单侧精确 `p=0.00390625`。

这只支持一个有边界的结论：**问题在当前冻结场景中存在。**它不证明所有模型、所有记忆系统或所有话题都会如此，也没有证明内部机制。

完整人话报告：[`docs/results/16_正式实验v3_5结果_人话版_2026-07-22.md`](docs/results/16_%E6%AD%A3%E5%BC%8F%E5%AE%9E%E9%AA%8Cv3_5%E7%BB%93%E6%9E%9C_%E4%BA%BA%E8%AF%9D%E7%89%88_2026-07-22.md)

## 现在到哪了

- 正式 v3.5 分析已关账，结果可在本仓库重建。
- 人类尺子校验正在进行：预计 3 名不知情判官，当前已私下回收 2 份。
- 第三份回收前，中途答案、管理员映射和任何揭盲结果都不进仓库。
- `paper/` 是当前两位研究者共同写作的唯一入口。

## 先读什么

1. 本页；
2. [`docs/results/16_正式实验v3_5结果_人话版_2026-07-22.md`](docs/results/16_%E6%AD%A3%E5%BC%8F%E5%AE%9E%E9%AA%8Cv3_5%E7%BB%93%E6%9E%9C_%E4%BA%BA%E8%AF%9D%E7%89%88_2026-07-22.md)；
3. [`docs/method/05_预注册修订稿_v0_2.md`](docs/method/05_%E9%A2%84%E6%B3%A8%E5%86%8C%E4%BF%AE%E8%AE%A2%E7%A8%BF_v0_2.md)；
4. [`HANDOFF_2026_07_24_项目协作_TO_LINGYUNLEO.md`](HANDOFF_2026_07_24_%E9%A1%B9%E7%9B%AE%E5%8D%8F%E4%BD%9C_TO_LINGYUNLEO.md)；
5. `paper/manuscript.md`。

## 复现正式结果

Python 需满足 `evidence/formal_v3_5/正式分析包_v3_5冻结/requirements.lock.txt`。在仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 sh scripts/verify_formal_v3_5.sh
```

通过标准：重新汇总后 `summary.json`、`audit.json` 和 `manifest_results.json` 的 SHA-256 与关账记录完全一致。

## 协作方式

- 从 `main` 新建短分支，一个 PR 只改一件可独立审查的事。
- 论文里永远把“观察到什么”与“我们如何解释”分开写。
- `evidence/` 是冻结证据，默认只读；新分析放入新目录，不覆盖旧文件。
- 任何人都不得提交原始聊天导出、PII、密钥、管理员盲化映射或未关账的人类判官答案。

细则见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和 [`DATA_BOUNDARIES.md`](DATA_BOUNDARIES.md)。
