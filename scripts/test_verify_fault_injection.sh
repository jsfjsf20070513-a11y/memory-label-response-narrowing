#!/bin/sh
# 回归测试:冻结目录被"被 .gitignore 忽略的文件"污染时,必须被发现。
#
# 由来:2026-07-28 lingyun 第三轮复核做故障注入 —— 在隔离副本的冻结目录里放一个
# .tmp 文件,当时的 verify_formal_v3_5.sh 仍输出"冻结证据未改变"并整体 [PASS]。
# 根因:`git status --untracked-files=all` 看不见被忽略的文件,而本仓忽略了
# *.tmp、__pycache__/、*.py[cod]。本项目在试跑期已被同类问题咬过一次(核验脚本
# 跳过 __pycache__),因此这里固化为永久测试。
#
# 本测试只在冻结目录里创建再删除一个临时文件,**不修改任何被跟踪的文件**,
# 也不调用模型、不跑 aggregate。
#
# 用法: sh scripts/test_verify_fault_injection.sh

set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EVIDENCE_PATH="evidence/formal_v3_5"
TARGET="$ROOT/$EVIDENCE_PATH"
CANARY="$TARGET/.fault_injection_canary.tmp"

FAILED=0
note() { echo "$1"; }
fail() { echo "[FAIL] $1" >&2; FAILED=1; }

# 与 verify_formal_v3_5.sh 中 evidence_manifest() 同构:不经过 git 的完整文件树哈希。
manifest() {
  python3 - "$TARGET" <<'PY'
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

git_status() {
  git -C "$ROOT" status --porcelain --untracked-files=all -- "$EVIDENCE_PATH"
}

if [ ! -d "$TARGET" ]; then
  echo "[SKIP] 找不到 $EVIDENCE_PATH,跳过" >&2
  exit 0
fi
if [ -e "$CANARY" ]; then
  fail "残留的 canary 文件已存在:$CANARY(请先手动删除)"
  exit 1
fi

BEFORE_MANIFEST=$(mktemp)
AFTER_MANIFEST=$(mktemp)
cleanup() { rm -f "$CANARY" "$BEFORE_MANIFEST" "$AFTER_MANIFEST"; }
trap cleanup EXIT

manifest >"$BEFORE_MANIFEST"
BEFORE_GIT=$(git_status)

# ---- 故障注入:放一个被 .gitignore 忽略的文件 ----
printf 'fault injection canary\n' >"$CANARY"

AFTER_GIT=$(git_status)
manifest >"$AFTER_MANIFEST"

# 断言 1:git 确实看不见它 —— 这正是原实现漏判的原因,必须成立,否则本测试失去意义。
if [ "$BEFORE_GIT" = "$AFTER_GIT" ]; then
  note "[OK] 断言 1:git status 看不见被忽略的 .tmp 文件(这就是纯 git 检查不够用的原因)"
else
  fail "断言 1 不成立:git status 竟然发现了 $CANARY。若 .gitignore 已改,请同步更新本测试。"
fi

# 断言 2:文件树哈希清单必须发现它。
if diff -q "$BEFORE_MANIFEST" "$AFTER_MANIFEST" >/dev/null 2>&1; then
  fail "断言 2 不成立:文件树哈希清单没有发现被忽略的新增文件 —— 检查 5 会漏判,这是阻断级缺陷。"
else
  note "[OK] 断言 2:文件树哈希清单发现了被忽略的新增文件"
fi

# 断言 3:git ls-files --others --ignored 能列出它(检查 2 的 [WARN] 依赖它)。
if git -C "$ROOT" ls-files --others --ignored --exclude-standard -- "$EVIDENCE_PATH" 2>/dev/null | grep -q 'fault_injection_canary'; then
  note "[OK] 断言 3:ls-files --others --ignored 能列出该文件"
else
  fail "断言 3 不成立:ls-files --others --ignored 没有列出 canary,检查 2 的污染告警会失效。"
fi

# 断言 4(端到端,最重要的一条):污染存在时,真脚本必须整体失败。
# 只靠"运行前后清单比对"抓不住这一类 —— 污染若在运行前就存在,前后一致,会照常 PASS。
# 因此这里连 --allow-version-drift 一起给,确保失败来自污染检查而不是版本闸门。
if sh "$ROOT/scripts/verify_formal_v3_5.sh" --allow-version-drift >/dev/null 2>&1; then
  fail "断言 4 不成立:冻结目录被污染时,verify_formal_v3_5.sh 竟然整体通过 —— 这是阻断级缺陷。"
else
  note "[OK] 断言 4:污染存在时 verify_formal_v3_5.sh 以非零退出"
fi

# ---- 清理并确认恢复原状 ----
rm -f "$CANARY"
manifest >"$AFTER_MANIFEST"
if diff -q "$BEFORE_MANIFEST" "$AFTER_MANIFEST" >/dev/null 2>&1; then
  note "[OK] 断言 5:清理后文件树哈希清单恢复原状,测试未留下痕迹"
else
  fail "断言 5 不成立:测试后目录未恢复原状,请人工核对 $EVIDENCE_PATH"
fi

# 断言 6:清理后,真脚本应恢复到"非污染"路径(此处仍会因版本漂移而受限,
# 故只断言它不再报污染)。
if sh "$ROOT/scripts/verify_formal_v3_5.sh" --allow-version-drift 2>&1 | grep -q '冻结证据已被污染'; then
  fail "断言 6 不成立:清理后仍报污染,说明检测逻辑或清理有问题。"
else
  note "[OK] 断言 6:清理后不再报污染"
fi

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "[FAIL] 故障注入回归测试未通过" >&2
  exit 1
fi

echo "[PASS] 故障注入回归测试通过(被 .gitignore 忽略的污染可被检出)"
