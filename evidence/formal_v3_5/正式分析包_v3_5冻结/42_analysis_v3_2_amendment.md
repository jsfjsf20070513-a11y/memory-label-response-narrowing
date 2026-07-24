# 正式分析 v3.2：Codex 严格 Schema 类型补丁

## 发生了什么

v3.1 完成冻结、独立审计和零调用复建后，第一次也是唯一一次 M3 长合成校准被
Codex 结构化输出接口以 HTTP 400 拒绝。raw 明示 `invalid_json_schema`：
`properties.method` 只有 `const`、没有显式 `type`。请求在推理前失败，stdout 中没有
模型消息，`effective_sha256` 为 null；v3.1 没有校准报告、正式编码清单或新票。

## 唯一测量改动

`15_schema_transport_codex_menu.json` 中七个带 `const` 或 `enum` 的字符串字段统一补
`type: string`：根层 `method/question/slot`、决定性证据的 `answer`、两类方向的
`tag`、判决的 `choice`。字段、允许值、提示词、合成材料、原回答、方向菜单、语义
校验、复核和统计全部不变。

Fable 初审随后发现 O3 同样由 Codex 执行，却仍使用缺显式类型的通用 Schema。为不
改变 Claude 槽的 Schema 字节，v3.2 新增 `17_schema_transport_codex_open.json`：它与
通用 Schema 的唯一区别是六个 `enum` 节点增加 `type: string`。程序只让 O3 使用它。

本地新增递归测试：M3/O3 实际使用的任一 Codex Schema 中有 `const`/`enum` 节点缺
`type` 都失败；另有测试证明 O3 严格副本剥去这些冗余类型后与通用 Schema 完全相同。
这不是用真实答案调参，而是让预先设计的分表能被提供方接口接收。

## 复用与调用边界

- 仍只复用 v3 已完整结束且可逐单元重建的 M1/M2 六个整槽；
- 不复用 v3 的孤立 M3 票，也不复用 v3.1 的任何东西（v3.1 本就没有模型输出）；
- v3.2 重新跑 M3 与 O3 各 1 次长合成校准，必须各自首试通过；
- 通过后才新跑 M3/O1/O2/O3 共 32 个盲化单元；
- 新目录尝试上限是 48，不把 v3.1 的推理前 400 混入新目录预算；总报告另行实报。

## 解释天花板

v3.2 仍是看到运输失败后的生成后分析修订，不是从头冻结的一次完成实验。即使最终
结果有形状，也必须连同 v3、v3.1 的失败史和票复用一起披露；确认性证据需要用冻结
后的工具处理全新回答。
