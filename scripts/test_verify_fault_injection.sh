#!/bin/sh
# verify_formal_v3_5.sh 的故障注入回归测试(隔离沙箱版)。
#
# 由来:2026-07-28 lingyun 复核先后命中的一组漏洞——
#   R3:被 .gitignore 忽略的 .tmp 放进冻结目录,校验仍整体 PASS;
#   R4:①回归测试直接写真实冻结目录;②只断言非零退出,无关错误也算"检测成功";
#      ③git 失败被静默解释成"无污染"(fail open);④manifest 只记内容哈希,
#      漏判 symlink 与 mode 变化;⑤污染路径泄漏临时文件。
# 本测试对每一条都固化一个断言,并遵守两条纪律:
#   1. **一切注入都发生在 mktemp -d 沙箱里的仓库副本上,真实冻结目录零接触**
#      (对真实仓库只做只读的 git status,首尾各一次,证明未被本测试改动)。
#   2. **每个断言都匹配精确的失败信息,不认"随便什么非零退出"。**
# 沙箱里的 aggregate 被替换为受控桩(FI_AGG_MODE 环境变量切换行为),因此本测试
# 不调用任何模型、不运行任何真实 aggregate,耗时与 CLI 版本无关。
#
# 用法: sh scripts/test_verify_fault_injection.sh

set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PKG_REL="evidence/formal_v3_5/正式分析包_v3_5冻结"
POLLUTION_MSG="冻结目录中存在被 .gitignore 忽略的文件"
CHANGED_MSG="本次运行改动了冻结证据"
NOGIT_MSG="不在 git 工作树内"

FAILED=0
ok()  { echo "[OK] $1"; }
bad() { echo "[NG] $1" >&2; FAILED=1; }

SANDBOX=$(mktemp -d)
cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

# 真实仓库只读基线(证明本测试没碰真实证据;放在一切动作之前)
REAL_BEFORE=$(git -C "$ROOT" status --porcelain --untracked-files=all -- evidence)

# ---- 搭沙箱:复制仓库(不含 .git),独立 git 初始化,替换 aggregate 为受控桩 ----
REPO="$SANDBOX/repo"
mkdir -p "$REPO"
cp -R "$ROOT/." "$REPO/"
rm -rf "$REPO/.git"
# 清掉可能随 Finder 混进副本的 OS 噪声,保证沙箱基线干净
find "$REPO/evidence" -name .DS_Store -exec rm -f {} + 2>/dev/null || true

cat > "$REPO/$PKG_REL/analysis_v2.py" <<'PYEOF'
#!/usr/bin/env python3
# 故障注入桩:替代冻结包 aggregate,行为由 FI_AGG_MODE 控制。
#   drift(默认) 只打印一行纯版本漂移错误后退出 1;
#   symlink     先在冻结包内留下一个未跟踪 symlink,再按 drift 退出;
#   modechange  先给 core.py 加执行位,再按 drift 退出。
# 后两种模拟"aggregate 中途失败并弄脏冻结目录",校验脚本必须抓到。
import os, stat, sys
mode = os.environ.get("FI_AGG_MODE", "drift")
here = os.path.dirname(os.path.abspath(__file__))
if mode == "symlink":
    os.symlink("fi-target-does-not-exist", os.path.join(here, "fi_canary_link"))
elif mode == "modechange":
    p = os.path.join(here, "core.py")
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print("开跑登记的 CLI 版本与现场不符：{'claude_cli_version': 'fi-stub', 'codex_cli_version': 'fi-stub'}", file=sys.stderr)
sys.exit(1)
PYEOF

git -C "$REPO" init -q
git -C "$REPO" config user.email "fi@test.invalid"
git -C "$REPO" config user.name "fault-injection-test"
git -C "$REPO" add -A
git -C "$REPO" commit -q -m "sandbox baseline"

# 沙箱基线自检:冻结目录不得有被忽略文件,否则后续断言全部失真
if [ -n "$(git -C "$REPO" ls-files --others --ignored --exclude-standard -- evidence/formal_v3_5)" ]; then
  bad "沙箱基线不干净:冻结目录里有被忽略文件,无法开展测试"
  exit 1
fi

CANARY="$REPO/$PKG_REL/fi_polluted.tmp"

# 统一执行器:在沙箱仓库里跑真校验脚本,捕获输出与退出码
run_verifier() {  # $@ = 传给校验脚本的参数;读全局 AGG_MODE / RUN_TMPDIR
  if OUT=$(cd "$REPO" && TMPDIR="${RUN_TMPDIR:-${TMPDIR:-/tmp}}" FI_AGG_MODE="${AGG_MODE:-drift}" \
      sh scripts/verify_formal_v3_5.sh "$@" 2>&1); then
    RC=0
  else
    RC=$?
  fi
}

# ---- 断言 1:被忽略的污染文件必须被检出,且失败原因必须精确 ----
printf 'fault injection canary\n' >"$CANARY"
AGG_MODE=drift
run_verifier --allow-version-drift
if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -q "$POLLUTION_MSG"; then
  ok "断言 1:ignored 污染 → 非零退出,且给出精确的污染错误信息"
else
  bad "断言 1:ignored 污染未被以正确原因拒绝(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi
rm -f "$CANARY"

# ---- 断言 2(无关错误对照,复核者的原攻击):非污染原因的失败不得被记成"检测成功" ----
mv "$REPO/scripts/check_repo_privacy.py" "$REPO/scripts/check_repo_privacy.py.bak"
printf 'fault injection canary\n' >"$CANARY"
run_verifier --allow-version-drift
if [ "$RC" -ne 0 ] && ! printf '%s' "$OUT" | grep -q "$POLLUTION_MSG"; then
  ok "断言 2:无关错误(隐私脚本缺失)→ 失败但不含污染信息,与污染检出可区分"
else
  bad "断言 2:无关错误未被区分(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi
mv "$REPO/scripts/check_repo_privacy.py.bak" "$REPO/scripts/check_repo_privacy.py"
rm -f "$CANARY"

# ---- 断言 3(阴性对照 + 临时文件泄漏):干净沙箱 → PARTIAL 退出 0,且不泄漏临时文件 ----
TMPISO="$SANDBOX/tmpiso"
mkdir -p "$TMPISO"
RUN_TMPDIR="$TMPISO"
run_verifier --allow-version-drift
RUN_TMPDIR=""
if [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -q '\[PARTIAL\]' && ! printf '%s' "$OUT" | grep -q "$POLLUTION_MSG"; then
  ok "断言 3:干净状态 → [PARTIAL] 退出 0,无污染误报"
else
  bad "断言 3:干净状态行为异常(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi
if [ -z "$(ls -A "$TMPISO")" ]; then
  ok "断言 3b:隔离 TMPDIR 运行后为空,无临时文件泄漏"
else
  bad "断言 3b:泄漏了临时文件:$(ls -A "$TMPISO" | tr '\n' ' ')"
fi

# ---- 断言 4:aggregate 运行中留下未跟踪 symlink → 运行后检查必须抓到 ----
AGG_MODE=symlink
run_verifier --allow-version-drift
if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -q "$CHANGED_MSG"; then
  ok "断言 4:运行中注入 symlink → 以\"改动了冻结证据\"失败"
else
  bad "断言 4:运行中注入的 symlink 未被抓到(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi
rm -f "$REPO/$PKG_REL/fi_canary_link"

# ---- 断言 5:aggregate 运行中只改 mode(加执行位)→ 运行后检查必须抓到 ----
AGG_MODE=modechange
run_verifier --allow-version-drift
if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -q "$CHANGED_MSG"; then
  ok "断言 5:运行中只改执行位 → 以\"改动了冻结证据\"失败"
else
  bad "断言 5:运行中的 mode 变化未被抓到(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi
chmod 644 "$REPO/$PKG_REL/core.py"
AGG_MODE=drift

# ---- 断言 6:无 .git 的归档副本必须 fail closed,不得宣称"干净" ----
NOGIT="$SANDBOX/nogit"
mkdir -p "$NOGIT"
cp -R "$REPO/." "$NOGIT/"
rm -rf "$NOGIT/.git"
printf 'fault injection canary\n' >"$NOGIT/$PKG_REL/fi_polluted.tmp"
if OUT=$(cd "$NOGIT" && sh scripts/verify_formal_v3_5.sh --allow-version-drift 2>&1); then RC=0; else RC=$?; fi
if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -q "$NOGIT_MSG"; then
  ok "断言 6:无 .git 副本 → fail closed,明确报\"不在 git 工作树内\""
else
  bad "断言 6:无 .git 副本未 fail closed(rc=$RC)"
  printf '%s\n' "$OUT" | sed 's/^/    /' >&2
fi

# ---- 断言 7:真实仓库冻结证据全程未被本测试触碰 ----
REAL_AFTER=$(git -C "$ROOT" status --porcelain --untracked-files=all -- evidence)
if [ "$REAL_BEFORE" = "$REAL_AFTER" ]; then
  ok "断言 7:真实 evidence/ 的 git 状态首尾一致,本测试零接触"
else
  bad "断言 7:真实 evidence/ 状态发生变化,请立即人工核对!"
fi

if [ "$FAILED" -ne 0 ]; then
  echo "" >&2
  echo "[FAIL] 故障注入回归测试未通过" >&2
  exit 1
fi
echo "[PASS] 故障注入回归测试通过(7 项断言,全部在隔离沙箱执行)"
