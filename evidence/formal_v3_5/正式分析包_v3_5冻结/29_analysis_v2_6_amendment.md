# 正式分析 v2.6：Claude 原生结构化输出

## 父版结果

v2.5 冻结包清单 SHA-256：
`6a9052592d2c0b0e7b634ad4432de78fb9f636ba3986f0eee3f3d1423e568ac5`。

v2.5 的六个合成校准槽位全部首试通过，校准清单 SHA-256：
`969f5adfcc1351b46067ede4086f3917ce8a39abf85b50a0d6c59822636da5dd`。

进入正式编码后，第一个调用单元 `ENCODE_V25_M1_S2_C01` 连续两次返回不可解析
JSON。两次 raw 均判无效，程序按“两次均失败即停止”规则终止。父版状态因此是：

- 总请求尝试 8 次：6 次合成校准 + 2 次正式运输失败；
- 首试失败单元 1 个；
- 有效正式编码 0 份；
- 无 `manifest_coding.json`，无 `effective/coding/*.json`；
- 两次失败 raw 原样保留，v2.6 不读取其正文来修改题目、菜单或判法。

## 接口探针

冻结 v2.6 前，用不含研究材料的虚拟任务 `{value: 7}` 检查 Claude Code CLI。
`claude-opus-4-6` low 在传入 `--json-schema` 后返回：

- 外层 `result`：可解析为 `{"value": 7}`；
- `structured_output`：对象 `{"value": 7}`；
- `num_turns=2`。

这证明原来的“只接受单轮普通文本 result”读取方式不适用于 Claude 原生结构化输出。
接口探针不计入正式分析请求预算，也没有接触正式回答。

## v2.6 改动

所有 Claude JSON 任务改为：

1. 将冻结 Schema 的规范 JSON 传给 CLI `--json-schema`；
2. 在 raw 的 `command_shape` 中记录 Schema SHA-256；
3. 要求 `structured_output` 为对象；
4. 要求外层 `result` 可解析，且解析值与 `structured_output` 完全相同；
5. 以 `structured_output` 的规范 JSON 作为有效正文和恢复依据；
6. 原生结构化输出允许 CLI 报告多于一轮，但仍禁止工具或权限请求，并核验指定模型。

Codex JSON 任务继续使用原生 `--output-schema`。两家 provider 现在都把 Schema 哈希
纳入有效 raw 匹配、断点恢复和阶段清单。

## 不变项与重跑纪律

题目、回答、盲化、菜单、合成金标准、模型、推理强度、每次两块、调用预算、证据
复核、统计规则全部不变。v2.6 不继承 v2.5 的任何校准票或失败正式票：

- 六槽合成校准从头各跑一次；
- 六槽必须全部首试通过；
- 通过后 48 个正式编码单元从头运行；
- 不根据父版失败正文选择性改材料或删样本。
