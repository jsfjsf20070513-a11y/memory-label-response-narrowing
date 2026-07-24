# 正式分析 v2.7：Claude Schema 元声明兼容

## 父版结果

v2.6 冻结包清单 SHA-256：
`f46f777bbf5d486351614e108c6668f623d304046a013319be472bc8a8f0b17a`。

v2.6 的首个合成校准单元 `CAL_V26_M1` 在模型推理前退出，Claude CLI stderr 为：

```text
Error: --json-schema is not a valid JSON Schema:
no schema with key or ref "https://json-schema.org/draft/2020-12/schema"
```

父版共 1 次失败请求，没有有效校准票，没有校准通过清单，也没有正式编码请求。

## 接口探针

用不含研究材料的小 Schema 检查 Claude CLI 2.1.207。去掉根节点 `$schema` 后，
同一接口成功接受：

- `$defs`；
- 本地 `$ref`；
- `type: ["object", "null"]`；
- `additionalProperties: false`。

探针返回 `{"decisive": null}`，`result` 与 `structured_output` 一致。该探针不计入
正式分析预算。

## v2.7 唯一改动

冻结 Schema 文件本身不改。只有传给 Claude CLI 原生 `--json-schema` 的规范副本
去掉根节点 `$schema`。其他键和值逐字继承。程序：

1. 对 Claude 计算并记录实际传入副本的 SHA-256；
2. 对 Codex 继续传完整冻结 Schema；
3. 提示中仍附完整冻结 Schema；
4. 本地 jsonschema 校验仍使用完整冻结 Schema；
5. 断点恢复按 provider 对应的实际原生 Schema 哈希匹配。

新增单测确认 Claude 副本只去掉根节点元声明，`$defs` 与引用不变，Codex 副本完全
不变。题目、回答、菜单、金标准、判法、模型、强度、预算和统计规则均不变。
