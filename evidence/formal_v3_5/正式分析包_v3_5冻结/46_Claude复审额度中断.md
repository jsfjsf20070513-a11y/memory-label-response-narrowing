# Claude Code / Opus 4.6 复审额度中断

- 复审请求：`45_Claude复审请求.md`；
- 模型/强度：Claude Code `claude-opus-4-6` low；
- 模式：无会话持久化、plan、只读工具；
- 结果：未形成审计意见；CLI 退出码 1；
- 原始提示：`You've hit your session limit · resets 7:40pm (Asia/Shanghai)`。

这不是正式研究调用，不计入 v3.2 的 48 次上限；没有模型输出，不能登记为 PASS 或
BLOCK。v3.2 候选包在复审成功前不得改名为冻结版，不得建立开跑授权文件，也不得执行
M3/O3 合成校准。额度重置后必须用同一份 `45_Claude复审请求.md` 重新发起独立复审。
