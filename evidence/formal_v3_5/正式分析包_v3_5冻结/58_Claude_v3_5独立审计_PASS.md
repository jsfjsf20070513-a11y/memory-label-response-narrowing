# v3.5 独立只读审计:PASS(附审计模型变更披露)

- 审计日期:2026-07-20
- 审计方:Claude Code。**实际模型为 Claude Fable 5(claude-fable-5),不是 57 号请求所写的 Opus 4.6**;原因是当前会话运行在 Fable 5 上。审计性质不变:只读、独立于组装方(Codex/Sol)、未运行任何正式模型调用。此变更在此如实登记,最终报告须一并披露。
- 被审对象:`正式分析包_v3_5候选/`(96 件登记文件,清单自身 SHA-256 `bf2f2aacb0e4212ebd44f062a4f9f5e0406c06949cbfbe35e9f6eb63f2d55c7e`,含 56/57 号、不含本文件),对照 `正式分析包_v3_4冻结/` 与 `正式分析运行_v3_4/`。
- 方法:逐字 diff v3.4 冻结包与 v3.5 候选包;直接读取 v3.4 运行现场原始件并独立复算哈希;在 scratchpad 干净临时副本中运行 `99_verify.sh` 与 `32_tests.py`,未触碰被审目录。

## 按 57 号六项核对

**1. v3.4 的 M2/M3 与 M1 来源 —— 符合。**
M2/M3 各五批 raw 均只有 attempt1 且 `valid:true`;合并文件哈希实测
M1 `26a86fe9…46b41`、M2 `0bf9f5d5…026b37`、M3 `3d14f922…8925f7`,与 13 号记录及 config 登记逐字一致。M1 来自 v3.3 完整槽,`source_v33_attestation.json` 登记链完整。v3.4 运行目录确无 `manifest_review.json`、`summary.json`。候选包 `verify_v34_completed_reviews_and_quota_failure()` 对每批做 prompt/effective 哈希回链、任务键复验、逐字节重建合并文件(`canonical_json(reconstructed) == merged bytes`)并跑原 `validate_review()` 全集校验,任一不符 SystemExit。

**2. O1 两次失败 —— 确为推理前额度拒绝。**
两份 raw 实测哈希 `bae4557a…b12c`、`8c0bbc97…379f8` 与 config 登记一致;内容均为
`api_error_status:429`、"You've hit your session limit"、`input_tokens:0`、`output_tokens:0`、`valid:false`、`effective_sha256:null`。无任何模型判断可复用;候选包代码显式校验以上每个字段,并要求 v3.4 raw 总数 12、有效数 10。

**3. 只复用完整槽 —— 符合。**
`prepare_quota_resume_inputs()` 仅整槽复制 M1/M2/M3 合并文件与 18 份编码,复制前先走 v3.2/v3.3/v3.4 三层复验;O1 raw 仅作失败史锁定(哈希登记),无从失败输出取值的代码路径。回答、校准、编码均为 `copy_exact`(哈希核对复制),无重跑入口。

**4. O1/O2/O3 执行方式 —— 与 v3.4 冻结一致,无暗门。**
`02_prepare.py`、`pipeline.py`、六份 Schema、两份复核提示词、`review_schemas/`、`51_build_review_schemas.py` 与 v3.4 冻结包逐字节相同(diff 为空);`99_verify.sh` 复核 25 份任务键 Schema 可逐字重建。`run_review_v35()` 只按 config `new_review_slots=["O1","O2","O3"]` 发出 5+5+5=15 批,总数硬校验;分批仍用原 `review_chunks`(每批≤30),槽位模型未变(O1/O2 Claude Opus 4.6 low、O3 Codex gpt-5.4 low)。合并后仍跑原 `validate_review()` 全集校验。`aggregate` 走原 `run_aggregate()`:六槽 `effective/review/*.json` 缺一即 SystemExit,review 阶段清单只在 15 批全部成功后落盘,汇总前无人工揭盲路径。选择性复用、重新分批、暗门:未发现。

**5. 预算与口径 —— 准确。**
CLI 分发改为 `prepare→prepare_quota_resume_inputs / review→run_review_v35 / aggregate→run_aggregate_v33`;新增 `inherited_review` 阶段清单并纳入 review 前置校验。`max_requests_for_completed_run=23`(15 主调用+8 重试)由 `enforce_request_limits()` 在每次新请求前后强制。实测三个父运行 raw 计数 36+7+12=55(额度失败与无效尝试均计入,与口径一致),最坏累计 55+23=78。核心程序改动仅三处常量(RUN_DIR/AUTH_FILENAME/AUTH_SCOPE)加 v3.5 函数;`analysis_v3_5` config 节内五个父哈希全部经独立复算吻合(含 32 件 M2/M3 证据束联合哈希 `c1b5ff66…2693d`,按包内 canonical_json 格式复算一致)。

**6. 运输不对称 —— 可接受,须披露。**
M1 数组运输、M2/M3 v3.4 键运输、O1/O2/O3 v3.5 键运输,三种实现分属三次运行;但六槽最终都收敛到同一 `validate_review()` 全集语义校验与同一合并格式,判断标准未变,可接受。最终报告必须披露:(a) 三种运输实现与三个时间点的不对称;(b) 编码(v3.2)与复核(v3.3/v3.4/v3.5)跨运行复用链;(c) 两次 429 额度中断史;(d) 订阅通道执行的既有限制(采样参数登记不可控,见 35 号);(e) 本次审计模型为 Fable 5 而非预注册文本所写 Opus 4.6。

## 现场核验

- 干净临时副本 `99_verify.sh` 退出码 0:清单 96 件全对、菜单节选与随机表可重建、25 份任务键 Schema 逐字重建、依赖冻结、72 项测试 OK、JSON Schema 全过、调用闸门关闭。
- 附带确认核验器仍拒绝 `__pycache__` 残留(先跑测试产生字节码后,核验器如设计退出码 1)。
- `正式分析运行_v3_5/` 不存在,`00_open_analysis_v3_5.json` 未登记,闸门关闭。

## 结论

**PASS。**允许冻结为 `正式分析包_v3_5冻结/`。开跑仍须:登记用户本轮原文 `go` 后,严格按 `prepare → review → aggregate` 执行;六槽全集通过前不得汇总、不得揭盲。
