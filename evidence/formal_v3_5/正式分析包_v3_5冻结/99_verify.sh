#!/bin/sh
set -eu

export LC_ALL=C
export LANG=C
export PYTHONDONTWRITEBYTECODE=1

python3 33_check_manifest.py
python3 02_prepare.py --check
python3 51_build_review_schemas.py
python3 - <<'PY'
from importlib.metadata import version
from pathlib import Path
for line in Path('requirements.lock.txt').read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    name, expected = line.split('==', 1)
    actual = version(name)
    if actual != expected:
        raise SystemExit(f'[FAIL] dependency {name}: expected={expected} actual={actual}')
print('[PASS] frozen Python dependencies')
PY
python3 32_tests.py
python3 - <<'PY'
import json
from pathlib import Path
import jsonschema
for path in sorted(Path('.').glob('*schema*.json')):
    jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding='utf-8')))
print('[PASS] JSON Schemas')
PY

if [ -e "../正式分析运行_v3_5/00_open_analysis_v3_5.json" ]; then
  echo "[FAIL] 调用闸门已被打开；当前准备阶段不应存在开跑登记" >&2
  exit 1
fi

echo "[PASS] formal analysis v3.5 quota-resume package verified; run gate closed"
