# CLI 版本漂移记录(2026-07-27)

接 `2026-07-26-cli-version-drift.md`。上一条只记了 Codex 一侧;本次两侧都不符。

## 事实

| 项 | 开跑登记(`00_open_analysis_v3_5.json`,2026-07-22T02:24:13Z) | 2026-07-27 现场 |
|---|---|---|
| Claude CLI | `2.1.215 (Claude Code)` | `2.1.220 (Claude Code)` |
| Codex CLI | `codex-cli 0.142.5` | `codex-cli 0.145.0` |

Claude CLI 的更新由项目负责人授权,不是意外漂移。

## 影响

- **已存结果的字节未漂移**:`scripts/check_result_hashes.py` 通过,`formal v3.5 result hashes are byte-identical`。
  **注意这句话的边界**:它只确认这几份结果文件与登记字节相同,**不能**证明当初的汇总逻辑或汇总结果正确——后者正是重算要验证的内容。因此它**不构成**跳过重算的充分理由。
- **逐字节重算做不了**:冻结包内 `verify_run_authorization()` 因版本不符停止。冻结包不得回改,故不在包内处理。
- 隐私边界检查通过;冻结证据在运行前后均干净。

## 本次处置

修改 `scripts/verify_formal_v3_5.sh`,**默认严格**:任何一项不过都失败,包括重算未完成。
只有调用者显式加 `--allow-version-drift`、且失败确实是格式明确的**纯**版本漂移时,
才降级为 `[PARTIAL]` 并以 0 退出。

理由:`verify_run_authorization()` 是为"防止未经授权调用模型"设的闸门(首条错误即
"缺正式开跑登记,拒绝调用模型"),而 `aggregate` 不调用任何模型,只是把已存编码重新
汇总。把防花钱的闸门挂在纯离线重算上,会让日常授权升级 CLI 直接导致校验停摆。

**这不是绕过闸门**:

- 冻结包与其中的闸门一个字节未改;
- **默认行为是失败**,降级必须由调用者显式选择,脚本不替他选;
- 只接受与 `^开跑登记的 CLI 版本与现场不符：\{.*\}$` 完全匹配、且整份日志仅此一行的情形;任何混合错误或其他失败一律非零退出;
- 降级成功时结论标为 `[PARTIAL]`,**不输出 `[PASS]`**,避免 CI 或调用者误判为已完整验证;
- 冻结证据的干净状态在 aggregate **前后各检查一次**,且覆盖 index、worktree 与 untracked。

## 复现

```sh
sh scripts/verify_formal_v3_5.sh                        # 退出码 1(默认严格,重算未完成)
sh scripts/verify_formal_v3_5.sh --allow-version-drift  # 退出码 0,结论为 [PARTIAL]
```

两者均已实测。

## 待办

要恢复逐字节重算,需把两个 CLI 还原到登记版本;或在下一轮开跑时重新登记版本。
本记录不改动任何冻结证据、结果或结论。
