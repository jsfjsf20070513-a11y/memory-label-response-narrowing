#!/bin/sh
# 校验已关账的 formal v3.5 证据包。
#
# 默认严格:任何一项不过都失败(退出码 1),包括逐字节重算未完成。
# 只有调用者显式加 --allow-version-drift,且失败确实是格式明确的纯 CLI 版本漂移,
# 才降级为 [PARTIAL] 并以 0 退出。降级由调用者主动选择,脚本不替他选。
#
# 检查项:
#   1. 仓库隐私边界
#   2. 运行前:git 状态干净(index+worktree+untracked)+ ignored 硬检查 +
#      记录 lstat 文件树清单基线 + **基线后 ignored 复查**(关竞态窗口)
#   3. 从冻结包逐字节重算
#   4. 已存结果哈希与登记字节一致
#   5. 运行后:git 状态、lstat 清单、**ignored 终检** 三重校验
#
# 设计要点(每条都来自被复现过的漏洞,不是假想):
#   - git 相关检查一律 fail closed:不在 git 工作树内、或 git 命令本身失败,
#     直接 [FAIL],绝不解释成"没有问题"。(归档副本没有 .git 时,旧版会把
#     ls-files 的失败静默当成"无污染"。)
#   - `git status --untracked-files=all` 看不见被 .gitignore 忽略的文件
#     (本仓忽略 *.tmp、__pycache__/、*.py[cod] 等),所以"无被忽略文件"必须
#     用 `git ls-files --others --ignored --exclude-standard` 单独硬检查;
#     且运行前后清单比对抓不住"运行前就已存在的污染",故该硬检查独立于清单比对。
#   - lstat 清单记录 类型/mode/symlink 目标/目录项,不只记内容哈希:
#     否则 aggregate 留下的未跟踪 symlink、或只改执行位的变化会漏判。
#   - git 状态与 lstat 清单在运行后**双重校验**,谁报异常都算失败。
#   - 清理 trap 在任何 mktemp 之前安装,任何提前退出路径都不泄漏临时文件。
#   - 重算失败不提前退出:先跑完检查 4、5 再统一退出,防止"失败 + 留下改动"
#     静默逃逸。
#   回归测试(隔离沙箱,不触碰真实冻结目录):scripts/test_verify_fault_injection.sh
#
# 关于第 4 项能证明什么:
#   它只确认"已存结果文件的字节没有漂移",不能证明当初的汇总逻辑或结果正确 ——
#   后者正是第 3 项重算要验证的内容。因此第 4 项通过不足以成为跳过第 3 项的理由。
#
# 为什么需要 --allow-version-drift:
#   冻结包内的 verify_run_authorization() 是为"防止未经授权调用模型"造的闸门,
#   但 aggregate 不调用任何模型,只是把已存编码重新汇总。日常授权升级 CLI 会让
#   纯离线重算停摆。冻结包不得回改,故在本层提供显式降级开关。
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
    -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; exit 0 ;;
    *) echo "未知参数:$arg(用法:sh scripts/verify_formal_v3_5.sh [--allow-version-drift])" >&2; exit 2 ;;
  esac
done

# ---- 前置:必须在 git 工作树内(fail closed) ----
if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[FAIL] $ROOT 不在 git 工作树内,无法校验冻结证据的干净状态(fail closed)。" >&2
  echo "       归档/解压副本请先还原为完整 git 仓库再运行本校验。" >&2
  exit 1
fi

# ---- 清理 trap:先安装,再创建任何临时文件 ----
BEFORE_MANIFEST=""
AFTER_MANIFEST=""
AGG_LOG=""
cleanup() {
  for f in "$BEFORE_MANIFEST" "$AFTER_MANIFEST" "$AGG_LOG"; do
    if [ -n "$f" ]; then rm -f "$f"; fi
  done
}
trap cleanup EXIT

# git 视角的状态:覆盖 index、worktree、untracked。看不见被忽略的文件。
git_evidence_status() {
  git -C "$ROOT" status --porcelain --untracked-files=all -- "$EVIDENCE_PATH"
}

# lstat 文件树清单:不经过 git,逐项记录 类型/mode/内容哈希(常规文件)/
# symlink 目标/目录项。新增、修改、删除、类型变化、mode 变化都会改变这份清单。
evidence_manifest() {
  python3 - "$ROOT/$EVIDENCE_PATH" <<'PY'
import hashlib, os, stat, sys
root = sys.argv[1]
rows = []
def record(path):
    st = os.lstat(path)
    rel = os.path.relpath(path, root)
    mode = oct(stat.S_IMODE(st.st_mode))
    if stat.S_ISLNK(st.st_mode):
        rows.append(f"l {mode} {rel} -> {os.readlink(path)}")
    elif stat.S_ISDIR(st.st_mode):
        rows.append(f"d {mode} {rel}")
    elif stat.S_ISREG(st.st_mode):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        rows.append(f"f {mode} {digest.hexdigest()} {rel}")
    else:
        rows.append(f"? {mode} {rel}")
for dirpath, dirnames, filenames in os.walk(root):
    record(dirpath)
    dirnames.sort()
    for name in sorted(filenames):
        record(os.path.join(dirpath, name))
    # symlink 指向目录时会出现在 dirnames 里且不被下钻,单独记录
    for name in sorted(dirnames):
        p = os.path.join(dirpath, name)
        if os.path.islink(p):
            record(p)
rows.sort()
print("\n".join(rows))
PY
}

# ---- 检查 1:隐私边界 ----
python3 "$ROOT/scripts/check_repo_privacy.py"

# ---- 检查 2a:运行前 git 状态必须干净(fail closed) ----
if ! BEFORE_STATUS=$(git_evidence_status); then
  echo "[FAIL] 运行前 git status 执行失败,无法判定冻结证据状态(fail closed)。" >&2
  exit 1
fi
if [ -n "$BEFORE_STATUS" ]; then
  echo "[FAIL] 运行前 $EVIDENCE_PATH 有未提交改动,无法证明本次运行是否改动了冻结证据" >&2
  echo "$BEFORE_STATUS" >&2
  exit 1
fi

# ignored 检查(fail closed),供运行前、基线后、运行后三处复用。
# 三处缺一不可:单次检查与基线建立之间存在竞态窗口——污染若恰在 ls-files 返回空之后、
# 基线清单生成之前出现,它会被纳入基线,前后清单一致、git status 又看不见,四道全漏。
# 该竞态已被第六轮复核用 git wrapper 实际复现(退出码 0 放行)。
# 关闭方式:基线建立后立即复查一次;运行结束后再终检一次——凡持续存在到任一检查点的
# 污染必被其后最近的检查抓到。(出现后又自行消失的瞬态污染超出终态检查的能力范围。)
list_ignored_or_die() {  # $1 = 阶段描述
  if ! _IG=$(git -C "$ROOT" ls-files --others --ignored --exclude-standard -- "$EVIDENCE_PATH"); then
    echo "[FAIL] git ls-files 执行失败($1),无法判定是否存在被忽略的污染文件(fail closed)。" >&2
    exit 1
  fi
  printf '%s' "$_IG"
}

# ---- 检查 2b:运行前不得存在任何被 .gitignore 忽略的文件(硬失败) ----
IGNORED_NOW=$(list_ignored_or_die "运行前")
if [ -n "$IGNORED_NOW" ]; then
  echo "[FAIL] 冻结目录中存在被 .gitignore 忽略的文件,冻结证据已被污染:" >&2
  echo "$IGNORED_NOW" | sed 's/^/         /' >&2
  echo "       git status 看不见这些文件。请人工确认来源后删除,再重跑本校验。" >&2
  exit 1
fi

# ---- 检查 2c:记录运行前 lstat 清单作基线 ----
# 专属前缀:让调用方(含回归测试)能精确识别本脚本的临时文件,不与 OS 噪声混淆
BEFORE_MANIFEST=$(mktemp "${TMPDIR:-/tmp}/verify_fv35.XXXXXX")
AFTER_MANIFEST=$(mktemp "${TMPDIR:-/tmp}/verify_fv35.XXXXXX")
evidence_manifest >"$BEFORE_MANIFEST"

# ---- 检查 2d:基线建立后立即复查 ignored(关闭"检查完→建基线"竞态窗口) ----
IGNORED_NOW=$(list_ignored_or_die "基线复查")
if [ -n "$IGNORED_NOW" ]; then
  echo "[FAIL] 基线建立后复查发现被 .gitignore 忽略的污染文件(出现在检查与基线的间隙):" >&2
  echo "$IGNORED_NOW" | sed 's/^/         /' >&2
  exit 1
fi

echo "[PASS] frozen evidence clean before run（git 状态干净、ignored 双查通过、lstat 基线已记录）"

# ---- 检查 3:逐字节重算 ----
RECOMPUTED=0
DRIFT_LINE=""
AGG_STATUS=0
AGG_REASON=""
AGG_LOG=$(mktemp "${TMPDIR:-/tmp}/verify_fv35.XXXXXX")

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

# 注意:重算失败时不在此处退出。aggregate 可能在失败前已写了一部分文件,
# 必须先跑完检查 4、5 才能知道冻结证据有没有被改脏。

# ---- 检查 4:已存结果哈希(重算失败也执行) ----
HASH_STATUS=0
if ! python3 "$ROOT/scripts/check_result_hashes.py"; then
  HASH_STATUS=1
fi

# ---- 检查 5:运行后 git 状态 与 lstat 清单 双重校验(无论前面成败,必须执行) ----
POST_STATUS=0
if ! AFTER_STATUS=$(git_evidence_status); then
  POST_STATUS=1
  echo "[FAIL] 运行后 git status 执行失败,无法判定冻结证据状态(fail closed)。" >&2
else
  if [ -n "$AFTER_STATUS" ]; then
    POST_STATUS=1
    echo "[FAIL] 本次运行改动了冻结证据 $EVIDENCE_PATH(git 状态):" >&2
    echo "$AFTER_STATUS" | sed 's/^/       /' >&2
  fi
fi
evidence_manifest >"$AFTER_MANIFEST"
if ! diff -q "$BEFORE_MANIFEST" "$AFTER_MANIFEST" >/dev/null 2>&1; then
  POST_STATUS=1
  echo "[FAIL] 本次运行改动了冻结证据 $EVIDENCE_PATH(lstat 文件树清单不一致):" >&2
  diff "$BEFORE_MANIFEST" "$AFTER_MANIFEST" | sed 's/^/       /' >&2
fi
# ignored 终检:清单比对只能发现"基线之后出现"的污染;若污染在竞态窗口混入基线,
# 前后清单一致——只有对终态直接再查 ignored 才能抓到。
IGNORED_END=$(list_ignored_or_die "运行后")
if [ -n "$IGNORED_END" ]; then
  POST_STATUS=1
  echo "[FAIL] 运行后冻结目录中存在被 .gitignore 忽略的文件(无论何时混入,终态即污染):" >&2
  echo "$IGNORED_END" | sed 's/^/       /' >&2
fi
if [ "$POST_STATUS" -ne 0 ] && [ "$AGG_STATUS" -ne 0 ]; then
  echo "       ⚠ 重算是失败的,却仍留下了改动 —— 冻结包可能被写脏,请人工核对后再继续。" >&2
fi
if [ "$POST_STATUS" -eq 0 ]; then
  echo "[PASS] frozen evidence unchanged by this run（git 状态与 lstat 清单双重校验）"
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
    echo "  - 检查 5 运行后冻结证据:已被改动或无法判定" >&2
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
