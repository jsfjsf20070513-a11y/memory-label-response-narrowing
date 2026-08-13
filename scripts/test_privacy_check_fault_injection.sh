#!/bin/sh
# check_repo_privacy.py 的故障注入回归测试(隔离沙箱版)。
#
# 由来:2026-08-13 扫描范围变更——_local/ 本地档案迁入工作树后,旧的 rglob 全树
# 扫描令守卫永久报红;改为"已追踪 + 未追踪且未被忽略"口径。本测试固化该口径的
# 每一条行为边界,遵守既有两条纪律(见 test_verify_fault_injection.sh):
#   1. 一切注入都发生在 mktemp -d 沙箱里的独立仓库上,真实仓库零写入;
#   2. 每个断言都匹配精确的失败信息,不认"随便什么非零退出"。
# 沙箱内 PII 样例(手机号)以拆写拼接构造,避免本文件自身触发内容扫描。
#
# 用法: sh scripts/test_privacy_check_fault_injection.sh

set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

FAILED=0
ok()  { echo "[OK] $1"; }
bad() { echo "[NG] $1" >&2; FAILED=1; }

SANDBOX=$(mktemp -d)
cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

REPO="$SANDBOX/repo"
mkdir -p "$REPO/scripts" "$REPO/docs" "$REPO/_local"
cp "$ROOT/scripts/check_repo_privacy.py" "$REPO/scripts/"
printf '_local/\n' > "$REPO/.gitignore"
printf '# placeholder\n' > "$REPO/docs/clean.md"
git -C "$REPO" init -q
git -C "$REPO" config user.name fi-test
git -C "$REPO" config user.email fi@test.invalid
git -C "$REPO" add -A
git -C "$REPO" commit -qm baseline

# 受控 PII:拆写拼接,防止本测试文件被内容扫描误报
PHONE=138$(printf '0013')8000

run_check() { # $1 = repo dir;输出存 $SANDBOX/out,返回退出码
  ( cd "$1" && python3 scripts/check_repo_privacy.py ) >"$SANDBOX/out" 2>&1
}

# T1 基线:干净沙箱仓库必须 PASS
if run_check "$REPO" && grep -q '\[PASS\] repository privacy boundary' "$SANDBOX/out"; then
  ok "T1 干净基线 PASS"
else
  bad "T1 干净基线未 PASS: $(cat "$SANDBOX/out")"
fi

# T2 未追踪、未被忽略的 PII 必须被抓住(精确到检查项与路径)
printf 'tel: %s\n' "$PHONE" > "$REPO/docs/leak.md"
if run_check "$REPO"; then
  bad "T2 未追踪 PII 被放行"
else
  grep -q 'cn_mobile: docs/leak.md' "$SANDBOX/out" \
    && ok "T2 未追踪非忽略 PII 检出 cn_mobile" \
    || bad "T2 退出非零但错误信息不符: $(cat "$SANDBOX/out")"
fi
rm "$REPO/docs/leak.md"

# T3 被忽略且未追踪的 PII 不再报红(新口径的核心行为)
printf 'tel: %s\n' "$PHONE" > "$REPO/_local/leak.md"
if run_check "$REPO" && grep -q '\[PASS\] repository privacy boundary' "$SANDBOX/out"; then
  ok "T3 被忽略未追踪文件不扫描"
else
  bad "T3 被忽略文件仍导致失败: $(cat "$SANDBOX/out")"
fi

# T4 同一文件被 git add -f 强行加入后必须被抓住(封堵绕过路径)
git -C "$REPO" add -f _local/leak.md
if run_check "$REPO"; then
  bad "T4 强行加入的被忽略 PII 被放行"
else
  grep -q 'cn_mobile: _local/leak.md' "$SANDBOX/out" \
    && ok "T4 add -f 后文件回到扫描范围" \
    || bad "T4 退出非零但错误信息不符: $(cat "$SANDBOX/out")"
fi
git -C "$REPO" rm -q --cached _local/leak.md
rm "$REPO/_local/leak.md"

# T5 禁止后缀在未追踪、未忽略位置仍然生效
: > "$REPO/docs/x.pdf"
if run_check "$REPO"; then
  bad "T5 禁止后缀被放行"
else
  grep -q 'forbidden suffix: docs/x.pdf' "$SANDBOX/out" \
    && ok "T5 禁止后缀检出" \
    || bad "T5 退出非零但错误信息不符: $(cat "$SANDBOX/out")"
fi
rm "$REPO/docs/x.pdf"

# T6 无 git 仓库时 fail closed,不静默退化为全树扫描或跳过
NOGIT="$SANDBOX/nogit"
mkdir -p "$NOGIT/scripts"
cp "$ROOT/scripts/check_repo_privacy.py" "$NOGIT/scripts/"
if ( cd "$NOGIT" && GIT_CEILING_DIRECTORIES="$SANDBOX" python3 scripts/check_repo_privacy.py ) \
    >"$SANDBOX/out" 2>&1; then
  bad "T6 无 git 环境未 fail closed"
else
  grep -q 'git file listing failed closed' "$SANDBOX/out" \
    && ok "T6 git 缺失 fail closed" \
    || bad "T6 退出非零但错误信息不符: $(cat "$SANDBOX/out")"
fi

# T7 既有提交元数据检查在新口径下仍生效(回归)
git -C "$REPO" -c user.email=fi@example.com -c user.name=fi-test \
  commit -q --allow-empty -m nonpseudo
if run_check "$REPO"; then
  bad "T7 非化名 HEAD 邮箱被放行"
else
  grep -q 'HEAD commit author/committer email is not pseudonymous' "$SANDBOX/out" \
    && ok "T7 提交元数据检查仍生效" \
    || bad "T7 退出非零但错误信息不符: $(cat "$SANDBOX/out")"
fi

if [ "$FAILED" -ne 0 ]; then
  echo "[FAIL] privacy check fault injection" >&2
  exit 1
fi
echo "[PASS] privacy check fault injection (7 assertions)"
