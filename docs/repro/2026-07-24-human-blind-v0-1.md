# Repro Pack: human-blind-v0.1

## Claim

本证据包支撑的唯一主张是：在冻结的 12 对回答上，三名人类判官按预注册规则合成后，
满足 `calibration_supported` 的全部门槛。

## Code State

- 项目：`记忆注入与模型行为/第一步_回答是否变窄/人类盲判校验`
- 汇总器：`02_aggregate_human.py`
- 测试：`03_tests.py`
- 盲化映射：`管理员私有_v0_1/01_盲化映射.json`
- AI 冻结对照：`正式实验_问题是否存在/正式分析运行_v3_5/audit.json`
- 旧 v3.5 结果没有被改写。

## Environment

- Python：`3.14.0`
- 依赖：仅 Python 标准库
- 日期：2026-07-24，Asia/Shanghai

## Inputs

| 输入 | 私有路径 | SHA-256 | 公开性 |
|---|---|---|---|
| HJ1 | `管理员私有_v0_1/回收结果_2026-07-24/03_记录表_HJ1.csv` | `20e58947a8832c10b0cafa992db52da55375b56f3c5152a31a42e94e514b2615` | 本地私有 |
| HJ2 | `管理员私有_v0_1/回收结果_2026-07-24/03_记录表_HJ2.csv` | `9f1d3d2c6e398fcdf1826413a1e95c28e8741549052d2194643394db6c3f2293` | 本地私有 |
| HJ3 | `管理员私有_v0_1/回收结果_2026-07-24/03_记录表_HJ3.csv` | `82941e12b3238a234fbeb2e7a7f612318a3e4e687bf2a279ca71c5b0bd1996ea` | 本地私有 |

三份输入均为 12 行，判官编号各自唯一，pair_id 集合完整，无空判、非法选项、重复块或
方向性判断缺理由。原始自由文本理由和逐判官票不进入 GitHub。

## Commands

在 `人类盲判校验/` 目录运行：

```bash
python3 03_tests.py
python3 02_aggregate_human.py \
  --responses 管理员私有_v0_1/回收结果_2026-07-24 \
  --output 管理员私有_v0_1/回收结果_2026-07-24/04_完整汇总_私有.json
```

## Outputs

| 输出 | SHA-256 / 摘要 | 用途 |
|---|---|---|
| `04_完整汇总_私有.json` | `6a69f74bda98cb5f03672fbd3770d68a7481b58576115f5b987655bfdf6aab60` | 完整审计，仅本地 |
| `结果_v0_1/aggregate_public.json` | `e8b06103413ae3bc9a65d6095e1d5143172483fab48cac4a33287faec0e761ae`；不含个人票和理由 | 协作与写作 |
| `docs/human-validation/10_人类校验关账报告_2026-07-24.md` | 结果解释和限制 | 研究入口 |

汇总摘要：

```json
{
  "ai_exact_agreement": 10,
  "calibration_pass": true,
  "human_negative": 0,
  "human_positive": 10,
  "human_sign_p": 0.0009765625,
  "human_zero": 2,
  "quality_fail_blocks": 0,
  "status": "calibration_supported"
}
```

## Pass Criteria

以 `00_预注册_v0_1.md` 为准：人类正向至少 6、非零块单侧精确 `p <= 0.05`、与 AI
逐块一致至少 9、反向不超过 1、质量失败块不超过 4。五项实际值分别为
`10`、`0.0009765625`、`10`、`0`、`0`，全部通过。

## Reproduction Log

- 2026-07-24：7 项原测试全部通过。
- 2026-07-24：三份真实输入通过冻结汇总器，状态为 `calibration_supported`。
- 2026-07-24：桌面原件与私有归档副本逐字节同哈希。

## Known Limits

- 公开协作者拿不到原始自由文本理由和管理员映射，因此公开包只能验证已脱敏汇总，
  完整重跑依赖项目负责人本地私有输入。
- HJ2 的部分理由虽符合冻结的“非空”结构规则，但对“非数学方向更多”的解释较弱。
- 这是测量校验而非独立复制，不能增加旧实验的样本量或改写其原 p 值。
