#!/bin/sh
# 校验已关账的 formal v3.5 证据包。
#
# 默认严格:任何一项不过都失败(退出码 1),包括逐字节重算未完成。
# 只有调用者显式加 --allow-version-drift,且失败确实是格式明确的纯 CLI 版本漂移,
# 才降级为 [PARTIAL] 并以 0 退出。降级由调用者主动选择,脚本不替他选。
#
# 检查项:
#   1. 仓库隐私边界
#   2. 冻结证据在运行前是干净的(index + worktree + untracked)
#   3. 从冻结包逐字节重算
#   4. 已存结果哈希与登记字节一致
#   5. 冻结证据在运行后仍然干净(与 2 对照,证明本次运行未改动)
#
# 关于第 4 项能证明什么:
#   它只确认"已存结果文件的字节没有漂移",**不能**证明当初的汇总逻辑或汇总
#   结果正确 —— 后者正是第 3 项重算要验证的内容。因此第 4 项通过不足以成为
#   跳过第 3 项的理由;跳过只能靠调用者显式授权。
#
# 为什么需要 --allow-version-drift:
#   冻结包内的 verify_run_authorization() 是为"防止未经授权调用模型"造的闸门
#   (首条错误即"缺正式开跑登记,拒绝调用模型"),但 aggregate 不调用任何模型,
#   只是把已存编码重新汇总。于是日常授权升级 CLI 也会让纯离线重算停摆。
#   冻结包不得回改,故在本层提供显式降级开关,而不改动包内闸门。
#
# 用法: sh scripts/verify_formal_v3_5.sh [--allow-version-drift]

set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PACKAGE="$ROOT/evidence/formal_v3_5/正式分析包_v3_5冻结"
AUTH="$ROOT/evidence/formal_v3_5/正式分析运行_v3_5/00_open_analysis_v3_5.json"
EVIDENCE_PATH="evidence/formal_v3_5"
# 版本漂移错误的精确格式;只接受这一种形态,混合错误不得降级。
DRIFT_RE='^开跑登记的 CLI 版本与现场不符：\{.*\}$'

ALLOW_DRIFT=0
for arg in "$@"; do
  case "$arg" in
    --allow-version-drift) ALLOW_DRIFT=1 ;;
    -h|--help) sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数:$arg(用法:sh scripts/verify_formal_v3_5.sh [--allow-version-drift])" >&2; exit 2 ;;
  esac
done

# 完整工作区状态:同时覆盖 index、worktree 与 untracked。
evidence_status() {
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$ROOT" status --porcelain --untracked-files=all -- "$EVIDENCE_PATH"
  fi
}

# ---- 检查 1:隐私边界 ----
python3 "$ROOT/scripts/check_repo_privacy.py"

# ---- 检查 2:运行前冻结证据必须干净 ----
BEFORE=$(evidence_status)
if [ -n "$BEFORE" ]; then
  echo "[FAIL] 运行前 $EVIDENCE_PATH 就不干净,无法证明本次运行是否改动了冻结证据" >&2
  echo "$BEFORE" >&2
  exit 1
fi
echo "[PASS] frozen evidence clean before run"

# ---- 检查 3:逐字节重算 ----
RECOMPUTED=0
DRIFT_LINE=""
AGG_LOG=$(mktemp)
trap 'rm -f "$AGG_LOG"' EXIT

if (cd "$PACKAGE" && python3 analysis_v2.py aggregate) >"$AGG_LOG" 2>&1; then
  RECOMPUTED=1
  echo "[PASS] aggregate recomputation reproduced"
else
  # 只有整份日志恰好一行、且完全匹配版本漂移格式时,才认定为纯漂移。
  NONEMPTY=$(grep -c '[^[:space:]]' "$AGG_LOG" || true)
  if [ "$ALLOW_DRIFT" -eq 1 ] && [ "$NONEMPTY" -eq 1 ] && grep -qE "$DRIFT_RE" "$AGG_LOG"; then
    DRIFT_LINE=$(grep -E "$DRIFT_RE" "$AGG_LOG" | head -1)
  elif [ "$ALLOW_DRIFT" -eq 1 ]; then
    echo "[FAIL] 重算失败,但不是格式明确的纯 CLI 版本漂移,不予降级" >&2
    cat "$AGG_LOG" >&2
    exit 1
  else
    echo "[FAIL] 重算未完成(默认严格模式)。确属已知版本漂移时,可显式加 --allow-version-drift。" >&2
    cat "$AGG_LOG" >&2
    exit 1
  fi
fi

# ---- 检查 4:已存结果哈希 ----
python3 "$ROOT/scripts/check_result_hashes.py"

# ---- 检查 5:运行后冻结证据仍然干净 ----
AFTER=$(evidence_status)
if [ -n "$AFTER" ]; then
  echo "[FAIL] 本次运行改动了冻结证据 $EVIDENCE_PATH" >&2
  echo "$AFTER" >&2
  exit 1
fi
echo "[PASS] frozen evidence unchanged by this run"

# ---- 报告 ----
if [ "$RECOMPUTED" -eq 1 ]; then
  echo "[PASS] formal v3.5 collaboration snapshot fully verified"
  exit 0
fi

REGISTERED=$(python3 - "$AUTH" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(f"claude {d.get('claude_cli_version','?')} / codex {d.get('codex_cli_version','?')}")
except Exception as exc:
    print(f"(无法读取登记文件:{exc})")
PY
)

echo "[WARN] aggregate recomputation NOT performed —— 调用者以 --allow-version-drift 显式降级"
echo "       登记版本:$REGISTERED"
echo "       现场:${DRIFT_LINE#*：}"
echo "       检查 4 只确认已存结果字节未漂移,不能证明当初的汇总逻辑或结果正确。"
echo "       要完整复验:还原上述登记版本后不带参数重跑。"
echo "       若本次漂移尚未登记,请在 docs/repro/ 追加一条记录。"
echo "[PARTIAL] formal v3.5 snapshot partially verified (recomputation skipped)"
exit 0
