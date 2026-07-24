# 正式分析 v2.5：结构化输出 Schema 方言兼容

## 父版结果

v2.4 冻结包清单 SHA-256：
`76830724684050ca4b88354d5b698300f68f20a4bdb8948d1f236ee51d78d8f3`。

v2.4 的 M1/M2 首试通过；M3 在模型推理前被 Codex CLI 拒绝：

```text
Invalid schema for response_format 'codex_output_schema':
In context=('properties', 'decisive'), 'oneOf' is not permitted.
```

失败 raw SHA-256：
`514678dc4e30f1a7a7c168ede9acdeda4c6a0f277781fff26604ada51c103922`。
父版共 3 次纯合成请求，没有校准通过清单，没有正式编码请求。

## v2.5 唯一改动

`15_schema_transport.json` 中 `decisive` 原本是：

```json
{"oneOf": [{"$ref": "#/$defs/decisive_ref"}, {"type": "null"}]}
```

现改为引用同一 `decisive_ref`，并令该定义的类型为：

```json
{"type": ["object", "null"]}
```

对象字段、必填项和禁止额外字段均原样保留。两种写法接受的业务值相同：要么是含
`answer + local_id` 的完整对象，要么是 null。新增单测确认：

- Schema 文本不再含 `oneOf`；
- 规范对象可通过；
- null 可通过；
- 缺字段对象仍被拒绝。

提示、语义校验、金标准、模型、强度、预算与统计规则均不变。Codex 继续使用 v2.4
加入的原生 `--output-schema` 和 Schema 哈希证据链。
