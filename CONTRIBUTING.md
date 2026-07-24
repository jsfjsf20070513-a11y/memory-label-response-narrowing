# 协作说明

## 第一次参与

1. 读 `README.md` 和 `HANDOFF_2026_07_24_项目协作_TO_LINGYUNLEO.md`。
2. 运行 `PYTHONDONTWRITEBYTECODE=1 sh scripts/verify_formal_v3_5.sh`。
3. 新建分支 `docs/first-read-<name>`。
4. 在 `paper/reading-notes/` 新建自己的阅读笔记，只写疑问、反例、可能的替代解释和写作建议。
5. 发第一个 PR，不要在首个 PR 直接改冻结证据或核心结论。

## PR 最小要求

- 标题说明是 `paper`、`analysis` 还是 `docs`。
- 正文写清“改了什么”、“为什么”、“用什么证据支撑”。
- 改动数字、图表或结论时，必须附复现命令。
- 提交前运行 `scripts/verify_formal_v3_5.sh` 和 `scripts/check_repo_privacy.py`。

## 写作约定

- 一段只承担一个主张。
- 数字紧跟证据文件路径，不靠记忆填写。
- 未验证的机制使用“可能”、“一种解释”，不写成事实。
- 反例和失败结果不得删掉：S8' 复现失败、AI-only 判读、样本窄和运输修补历史都是论文必写限制。
