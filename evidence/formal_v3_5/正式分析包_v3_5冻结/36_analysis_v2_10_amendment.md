# 正式分析 v2.10：Codex 额度中断后同算法续跑

## 父版结果

v2.9 冻结包清单 SHA-256：
`bf4812b1111a2ad1ff4a24065eda92a509e2f578b2d8a40e8c68a358231f199b`。

v2.9 的 M1/M2 合成校准首试通过。M3 由 Codex CLI 在推理前拒绝：

```text
You've hit your usage limit ... try again at Jul 23rd, 2026 4:28 PM.
```

父版共 3 次请求，无 `manifest_calibration.json`，无正式编码请求。M1/M2 校准票不复用。

## v2.10 改动范围

v2.10 不改任何业务代码、提示、Schema、材料、模型、强度、预算、判法或统计。它只：

- 将父运行证据链更新为 v2.9 的 Codex 额度失败 raw 与状态；
- 使用新的运行目录、授权文件名和 `V210` 单元前缀；
- 待 Codex 额度恢复后，六槽合成校准从头各跑一次。

v2.9 菜单去重提示已经过 55 项测试和 Claude Opus 4.6 独立审计。v2.10 无业务实现
变化，因此继承该审计，不为形式版本号另外消耗模型额度。
