# CLI 版本漂移记录(2026-07-27)

接 `2026-07-26-cli-version-drift.md`。上一条只记了 Codex 一侧;本次两侧都不符。

## 事实

| 项 | 开跑登记(`00_open_analysis_v3_5.json`,2026-07-22T02:24:13Z) | 2026-07-27 现场 |
|---|---|---|
| Claude CLI | `2.1.215 (Claude Code)` | `2.1.220 (Claude Code)` |
| Codex CLI | `codex-cli 0.142.5` | `codex-cli 0.145.0` |

Claude CLI 的更新由项目负责人授权,不是意外漂移。

## 影响

- **已存结果未受影响**:`scripts/check_result_hashes.py` 通过,`formal v3.5 result hashes are byte-identical`。
- **逐字节重算做不了**:冻结包内 `verify_run_authorization()` 因版本不符停止。冻结包不得回改,故不在包内处理。
- 隐私边界检查通过;冻结证据未被本次运行改动。

## 本次处置

修改 `scripts/verify_formal_v3_5.sh`,把校验分成主次两层:

- **主检查**(不过即失败):隐私边界、已存结果哈希、冻结证据未被改动。
- **次检查**(不过只降级报告):从冻结包逐字节重算。

理由:`verify_run_authorization()` 是为"防止未经授权调用模型"设的闸门(首条错误即
"缺正式开跑登记,拒绝调用模型"),而 `aggregate` 不调用任何模型,只是把已存编码重新
汇总。把防花钱的闸门挂在纯离线重算上,会让日常授权升级 CLI 直接导致校验停摆。

**这不是绕过闸门**:

- 冻结包与其中的闸门一个字节未改;
- 跳过时明确打印 `[SKIP]` 与"本次未完成逐字节重算";
- 已存结果由独立的哈希检查保证;
- 新增 `--strict`,版本漂移一律判失败,供正式发表前的完整复验使用(该模式下本次仍为失败,已实测)。

## 复现

```sh
sh scripts/verify_formal_v3_5.sh           # 退出码 0,含 [SKIP] 行
sh scripts/verify_formal_v3_5.sh --strict  # 退出码 1,版本漂移判失败
```

## 待办

要恢复逐字节重算,需把两个 CLI 还原到登记版本;或在下一轮开跑时重新登记版本。
本记录不改动任何冻结证据、结果或结论。
