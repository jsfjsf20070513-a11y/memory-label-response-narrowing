#!/bin/sh
set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PACKAGE="$ROOT/evidence/formal_v3_5/正式分析包_v3_5冻结"

python3 "$ROOT/scripts/check_repo_privacy.py"
cd "$PACKAGE"
python3 analysis_v2.py aggregate >/dev/null
cd "$ROOT"
python3 scripts/check_result_hashes.py

if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && ! git diff --quiet -- evidence/formal_v3_5; then
  echo "[FAIL] aggregate changed frozen tracked evidence" >&2
  git diff --stat -- evidence/formal_v3_5 >&2
  exit 1
fi

echo "[PASS] formal v3.5 collaboration snapshot reproduced"
