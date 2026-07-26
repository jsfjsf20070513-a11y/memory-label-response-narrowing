# Repro Note: CLI 更新触发冻结版本闸门

## 发生了什么

2026-07-26，在完成关账后方法澄清时运行：

```bash
PYTHONDONTWRITEBYTECODE=1 sh scripts/verify_formal_v3_5.sh
```

隐私检查通过，但离线汇总入口在读取开跑登记后主动退出：

```text
开跑登记的 CLI 版本与现场不符：
claude_cli_version = 2.1.215 (Claude Code)
codex_cli_version = codex-cli 0.145.0
```

开跑登记保存的版本是：

```text
claude_cli_version = 2.1.215 (Claude Code)
codex_cli_version = codex-cli 0.142.5
```

用户已确认本机做过更新。因此差异来自 Codex CLI 正常升级，不是实验文件被改动。

## 为什么离线汇总也被挡住

冻结的 `analysis_v2.py aggregate` 在进入汇总前复用了正式开跑授权检查。该检查不仅验证
冻结包和授权原文，也要求当前 Claude/Codex CLI 版本与开跑时完全一致。

这个设计能防止正式模型调用在环境漂移后悄悄继续，却也把不需要模型调用的离线汇总绑
到了 CLI 版本。因此当前机器升级后，完整复现入口 fail-closed。

## 已完成的静态核验

以下检查在更新后的环境中通过：

```bash
python3 scripts/check_repo_privacy.py
python3 scripts/check_result_hashes.py
git diff --quiet -- evidence/formal_v3_5
```

结果：

- 仓库隐私边界通过；
- `summary.json`、`audit.json` 和 `manifest_results.json` 与关账哈希逐字节一致；
- `evidence/formal_v3_5/` 没有工作树改动。

## 当前判定

**冻结结果完整性通过；升级后的当前环境不能直接重跑完整汇总。**

这不推翻 2026-07-22 在版本匹配环境中完成的复现记录，但意味着 README 原先把一键复现
写成无条件可运行过于乐观。当前公开包应标为：

> 结果哈希可在当前环境核验；完整汇总可在记录的 CLI 环境中复现，当前升级环境被版本
> 闸门阻止。

## 不采取的做法

- 不修改冻结开跑登记里的旧版本号；
- 不把当前版本伪装成旧版本；
- 不降级用户已更新的 Codex CLI；
- 不删除或放宽正式运行的版本闸门；
- 不把静态哈希检查冒充完整重新汇总。

若未来要支持任意新 CLI 下的离线复现，应另建、互审并冻结一个只读离线汇总入口，明确
证明它不触发模型调用且与原汇总字节一致；这不是本轮文档澄清的范围。
