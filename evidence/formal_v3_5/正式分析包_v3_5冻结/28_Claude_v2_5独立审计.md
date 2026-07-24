# Claude Code 对 v2.5 的独立审计

- 时间：2026-07-16T11:00:32Z
- 模型：`claude-opus-4-6` low
- 会话：safe mode、无持久化、无工具
- 输入：v2.5 修订、运输 Schema、调用核心、分析入口与测试
- 未输入：正式回答、臂映射、实验运行输出
- 性质：冻结前设计审，不计入正式分析请求预算

审计结论：**无阻塞。**

Claude 确认，在 JSON Schema 2020-12 下：

- `required` 与 `additionalProperties` 只约束对象，值为 null 时不生效；
- nullable object 与原 `oneOf(object, null)` 的业务接受集合等价；
- null 与完整对象通过，残缺对象仍拒绝；
- 改写不触及判断、金标准或统计。
