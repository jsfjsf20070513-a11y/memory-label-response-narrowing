# 正式分析 v2.4：Codex 原生结构化输出

## 父版结果

v2.3 冻结包清单 SHA-256：
`0c1f6932b797e7f380b44ccf912f6436cf603033d183dee046f18b6d5135c629`。

v2.3 的 M1/M2/M3/O1/O2 五槽首试通过，最后的 O3 在 JSON 解析前失败：
`Expecting property name enclosed in double quotes`。失败 raw SHA-256：
`1967157f549463597fdaea107ab73e56aaeaa7d01e77894161eb97ac05c7e397`。

父版六次请求全部是纯合成校准，没有校准通过清单，没有正式编码请求。

## 失败性质

O3 没有进入 Schema、语义、证据或金标准判断；失败只是模型最终文本含坏 JSON。
这说明把 Schema 原文附在提示末尾仍不足以保证 Codex 的运输层。

现场 Codex CLI 0.142.5 的 `codex exec --help` 提供：

```text
--output-schema <FILE>
    Path to a JSON Schema file describing the model's final response shape
```

## v2.4 唯一实现改动

- 所有 Codex JSON 调用在原有提示内嵌 Schema 之外，再向 CLI 传
  `--output-schema <冻结 Schema 绝对路径>`；
- Claude 调用方式不变；
- raw 的 `command_shape` 新增 `output_schema_sha256`；
- 有效 raw 的恢复与复验同时核对该 Schema 哈希；
- 在真正请求登记时，pending raw 也记录 Schema 哈希；
- 新增单测机械确认命令含 `--output-schema` 且 raw 记录的哈希正确。

这只约束返回结构，不改变提示、菜单、方向粒度、判断、模型、强度、金标准、预算或统计
规则。v2.4 仍使用六张全新的首试校准票，不复用 v2.3 的五张通过票。
