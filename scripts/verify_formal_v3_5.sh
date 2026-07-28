#!/bin/sh
# 校验已关账的 formal v3.5 证据包。
#
# 默认严格:任何一项不过都失败(退出码 1),包括逐字节重算未完成。
# 只有调用者显式加 --allow-version-drift,且失败确实是格式明确的纯 CLI 版本漂移,
# 才降级为 [PARTIAL] 并以 0 退出。降级由调用者主动选择,脚本不替他选。
#
# 检查项:
#   1. 仓库隐私边界
#   2. 冻结证据在运行前无未提交改动;并记录**完整文件树哈希清单**
#   3. 从冻结包逐字节重算
#   4. 已存结果哈希与登记字节一致
#   5. 运行后重算文件树哈希清单,与检查 2 的清单**逐字节比对**
#
# 检查 5 为什么不用 git:
#   `git status --untracked-files=all` **看不见被 .gitignore 忽略的文件**,而本仓忽略了
#   *.tmp、__pycache__/、*.py[cod] 等。故障注入验证过:往冻结目录放一个 .tmp 文件,
#   纯 git 版检查仍会输出"未改变"并整体 PASS。因此改用不经过 git 的完整文件树哈希,
#   新增、修改、删除(含被忽略的文件)一律会被发现。回归测试见
#   scripts/test_verify_fault_injection.sh。
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

# git 视角的状态:覆盖 index、worktree、untracked。
# **注意它看不见被 .gitignore 忽略的文件**(本仓忽略了 *.tmp、__pycache__/、*.py[cod] 等),
# 所以它只用于"运行前是否有未提交改动",不能用来证明目录未被改动。
evidence_status() {
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$ROOT" status --porcelain --untracked-files=all -- "$EVIDENCE_PATH"
  fi
}

# 完整文件树清单:遍历目录下每一个文件算 SHA-256,**完全不经过 git**,
# 因此被 .gitignore 忽略的文件也在内。新增、修改、删除都会改变这份清单。
# 这是判定"冻结证据是否被本次运行改动"的唯一依据。
evidence_manifest() {
  python3 - "$ROOT/$EVIDENCE_PATH" <<'PY'
import hashlib, os, sys
root = sys.argv[1]
rows = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames.sort()
    for name in sorted(filenames):
        path = os.path.join(dirpath, name)
        if os.path.islink(path) or not os.path.isfile(path):
            rows.append(f"{'nonfile':<64}  {os.path.relpath(path, root)}")
            continue
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        rows.append(f"{digest.hexdigest()}  {os.path.relpath(path, root)}")
rows.sort()
print("\n".join(rows))
PY
}

# ---- 检查 1:隐私边界 ----
python3 "$ROOT/scripts/check_repo_privacy.py"

# ---- 检查 2:运行前冻结证据必须干净 ----
BEFORE_STATUS=$(evidence_status)
if [ -n "$BEFORE_STATUS" ]; then
  echo "[FAIL] 运行前 $EVIDENCE_PATH 有未提交改动,无法证明本次运行是否改动了冻结证据" >&2
  echo "$BEFORE_STATUS" >&2
  exit 1
fi

# 记录运行前的完整文件树清单(含被忽略的文件),供检查 5 比对。
BEFORE_MANIFEST=$(mktemp)
AFTER_MANIFEST=$(mktemp)
evidence_manifest >"$BEFORE_MANIFEST"

# 冻结目录里**不得存在任何被 .gitignore 忽略的文件**。
# 这是硬失败,不是警告:冻结证据必须处于其登记状态,多一个 .tmp / .pyc / __pycache__
# 就说明目录已被污染,此时任何"未改变"的结论都不可信。
#
# 注意仅靠"运行前后清单比对"抓不住这一类:污染若在运行**之前**就存在,前后清单一致,
# 会照常给出 PASS —— 这正是 2026-07-28 故障注入复核命中的漏洞。
IGNORED_NOW=$(git -C "$ROOT" ls-files --others --ignored --exclude-standard -- "$EVIDENCE_PATH" 2>/dev/null || true)
if [ -n "$IGNORED_NOW" ]; then
  echo "[FAIL] 冻结目录中存在被 .gitignore 忽略的文件,冻结证据已被污染:" >&2
  echo "$IGNORED_NOW" | sed 's/^/         /' >&2
  echo "       git status 看不见这些文件。请人工确认来源后删除,再重跑本校验。" >&2
  exit 1
fi

echo "[PASS] frozen evidence clean before run（无未提交改动、无被忽略文件;完整清单已记录）"

# ---- 检查 3:逐字节重算 ----
RECOMPUTED=0
DRIFT_LINE=""
AGG_STATUS=0
AGG_REASON=""
AGG_LOG=$(mktemp)
trap 'rm -f "$AGG_LOG" "$BEFORE_MANIFEST" "$AFTER_MANIFEST"' EXIT

if (cd "$PACKAGE" && python3 analysis_v2.py aggregate) >"$AGG_LOG" 2>&1; then
  RECOMPUTED=1
  echo "[PASS] aggregate recomputation reproduced"
else
  # 只有整份日志恰好一行、且完全匹配版本漂移格式时,才认定为纯漂移。
  NONEMPTY=$(grep -c '[^[:space:]]' "$AGG_LOG" || true)
  if [ "$ALLOW_DRIFT" -eq 1 ] && [ "$NONEMPTY" -eq 1 ] && grep -qE "$DRIFT_RE" "$AGG_LOG"; then
    DRIFT_LINE=$(grep -E "$DRIFT_RE" "$AGG_LOG" | head -1)
  elif [ "$ALLOW_DRIFT" -eq 1 ]; then
    AGG_STATUS=1
    AGG_REASON="重算失败,但不是格式明确的纯 CLI 版本漂移,不予降级"
  else
    AGG_STATUS=1
    AGG_REASON="重算未完成(默认严格模式)。确属已知版本漂移时,可显式加 --allow-version-drift。"
  fi
fi

# 注意:重算失败时**不在此处退出**。aggregate 可能在失败前已经写了一部分文件,
# 必须先跑完检查 5(运行后冻结证据)才能知道冻结证据有没有被改脏。提前 exit
# 会跳过那一步,让"失败 + 留下改动"这种最危险的情况静默逃逸。

# ---- 检查 4:已存结果哈希(重算失败也执行,信息更全) ----
HASH_STATUS=0
if ! python3 "$ROOT/scripts/check_result_hashes.py"; then
  HASH_STATUS=1
fi

# ---- 检查 5:运行后冻结证据仍然干净(无论前面成败,必须执行) ----
# 以完整文件树清单为准,不以 git 为准 —— git 看不见被忽略的文件。
POST_STATUS=0
evidence_manifest >"$AFTER_MANIFEST"
if ! diff -q "$BEFORE_MANIFEST" "$AFTER_MANIFEST" >/dev/null 2>&1; then
  POST_STATUS=1
  echo "[FAIL] 本次运行改动了冻结证据 $EVIDENCE_PATH(文件树哈希清单不一致)" >&2
  diff "$BEFORE_MANIFEST" "$AFTER_MANIFEST" | sed 's/^/       /' >&2
  if [ "$AGG_STATUS" -ne 0 ]; then
    echo "       ⚠ 重算是失败的,却仍留下了改动 —— 冻结包可能被写脏,请人工核对后再继续。" >&2
  fi
else
  echo "[PASS] frozen evidence unchanged by this run（按完整文件树哈希,含被忽略文件）"
fi

# ---- 统一退出:任何一项不过都失败 ----
if [ "$AGG_STATUS" -ne 0 ] || [ "$HASH_STATUS" -ne 0 ] || [ "$POST_STATUS" -ne 0 ]; then
  echo "" >&2
  echo "[FAIL] 校验未通过:" >&2
  if [ "$AGG_STATUS" -ne 0 ]; then
    echo "  - 检查 3 重算:$AGG_REASON" >&2
    sed 's/^/      /' "$AGG_LOG" >&2
  fi
  if [ "$HASH_STATUS" -ne 0 ]; then
    echo "  - 检查 4 已存结果哈希:不一致" >&2
  fi
  if [ "$POST_STATUS" -ne 0 ]; then
    echo "  - 检查 5 运行后冻结证据:已被改动" >&2
  fi
  exit 1
fi

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
