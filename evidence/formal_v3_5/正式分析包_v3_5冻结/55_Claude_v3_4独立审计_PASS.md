# Claude Code / Opus 4.6 对 v3.4 的独立审计：PASS

- 模型：Claude Code `claude-opus-4-6`，low；
- 模式：无会话持久化、plan、只读工具；
- 请求：`54_Claude_v3_4审计请求.md`；
- 结论：**PASS，可冻结执行。**

## 核对结果

1. v3.3 M1 的五批为 30+30+30+30+24=144 条，全部首试有效，可逐字重建 merged
   并通过原语义校验；M2 两次无效，v3.3 没有 review manifest/summary。
2. v3.4 只复用完整 M1；M2 无效 raw 只核哈希，不复制、不进入结果；不重跑编码。
3. 25 份 Schema 的 `additionalProperties:false` 与完整 `required` 从结构上禁止缺键、
   多键和改键；所有 `const`/`enum` 有显式类型，未见 Claude/Codex 明显拒绝风险。
4. 键固定输出按冻结任务顺序转回旧列表后，仍走原 `validate_review()` 和原汇总；没有
   批间重复/遗漏或选择性复用暗门。
5. v3.4 为 25 主调用+8 重试=33；累计最坏 36+7+33=76≤78，有测试断言。
6. M1 数组运输与 M2—O3 键固定运输的不对称可接受，但必须披露。

报告还必须明确：M1 完整性来自五批实际全部通过和全集复验，不是键固定 Schema 的结构
保证；M1 五次请求计入 v3.3，不计入 v3.4。
