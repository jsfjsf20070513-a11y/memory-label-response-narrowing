# 正式分析 v3.5：额度重置后续跑说明

## 这一版解决什么

v3.4 已完成 M2、M3 的十个任务键固定复核批次；加上此前完整的 M1，六名复核者中
已有三名完成。开始 O1 第一批时，Claude Max 连续两次在推理前返回 429：两次记录的
输入、输出 token 都是 0，没有可复用的模型判断。

v3.5 不是换方法，也不重做已经成功的工作。它机械复验并整槽复用完整的 M1/M2/M3，
锁定两次 429 作为失败史；额度重置后只新跑 O1/O2/O3。回答、编码、复核任务、模型、
提示、Schema、判断标准和汇总规则全部不变。

## 固定父输入

- v3.4 冻结包清单：`5bfb89fb52e41a6f9a00583efbdf2d5d018f310bf76cd0606fd5a9825db9cad8`
- v3.4 运行状态：`9d52b2286876aa87bd8737b72159d9bba6901aa8408d185aa91e7c36913801a7`
- v3.4 M2 合并复核：`0bf9f5d5e82ac7dc7544a27cfbc96443d61da06fb3ad051744b067578e026b37`
- v3.4 M3 合并复核：`3d14f92262a45375190365d89fbdb3fea2378bb3a00c86f62b6c70bbae8925f7`
- M2/M3 的 prompts、raw、transport、merged 32 件联合哈希：
  `c1b5ff669037457d374e51d714c697885946c64b599b64a29da0a2463cb2693d`
- O1 两次推理前 429 raw：`bae4557a…b12c`、`8c0bbc97…379f8`

`prepare` 会重新核验 v3.2 的 18 份编码链、v3.3 的完整 M1 链、v3.4 的 M2/M3 链，
并确认 v3.4 只有十次有效复核和两次零 token 的 429，没有完整 review manifest 或
summary。任一处不符就关闭续跑。

## 复用与新调用

- 复用：M1、M2、M3 三个完整复核槽；
- 不复用：O1 的两份 429 raw，它们没有模型输出；
- 新跑：O1、O2、O3，每名五批，共 15 次任务键固定复核；
- 重试余量：8 次；v3.5 新目录硬上限 23 次；
- 先前实际请求：v3.2 36 次 + v3.3 7 次 + v3.4 12 次 = 55 次；
- 加上 v3.5 最坏 23 次，总计恰好 78 次，不超过用户批准的 78 次总规模。

额度重置前不得审计或开跑。审计和运行都使用 Claude Code / Opus 4.6；这不等于
Claude chat 或 Codex。正式运行的 O1/O2/O3 模型与原预注册槽位保持一致。

## 零调用核验与执行

```bash
cd 正式分析包_v3_5冻结
LC_ALL=C LANG=C PYTHONDONTWRITEBYTECODE=1 ./99_verify.sh
python3 analysis_v2.py prepare
python3 analysis_v2.py review
python3 analysis_v2.py aggregate
```

调用前必须登记 `../正式分析运行_v3_5/00_open_analysis_v3_5.json`，授权范围为
`formal_analysis_v3_5_quota_resume_up_to_23_calls`。CLI 只提供 `prepare`、`review`、
`aggregate`，没有回答生成、校准或编码入口。

## 报告时必须说明

M1 使用 v3.3 的数组运输；M2/M3 使用 v3.4、O1/O2/O3 使用 v3.5 的任务键固定运输。
六人的判断内容相同，但运输形式和实际请求轮次不对称。还必须列出 v3.2—v3.4 的完整
失败链、两次推理前额度拒绝，以及本分析是在编码后修补运输程序的探索性正式检验。
强确认仍需对全新回答复制。
