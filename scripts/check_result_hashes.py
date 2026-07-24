#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "evidence" / "formal_v3_5" / "正式分析运行_v3_5"
EXPECTED = {
    "summary.json": "d49be125db9ac42ea860a51f580270f93f2e83c3f34b41f48dba4f8e1a5062bf",
    "audit.json": "a9117b1d839c57adbde7598e0229f32694d145954ce1c2692d2453e78028683f",
    "manifest_results.json": "709d9d3d23f32b3aa0b642a15915e23f7544310c3fd5eba53a70ea3a96e219b2",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    failures = []
    for name, expected in EXPECTED.items():
        path = RUN / name
        actual = sha256(path) if path.is_file() else "MISSING"
        if actual != expected:
            failures.append(f"{name}: expected={expected} actual={actual}")
    if failures:
        raise SystemExit("[FAIL] result hashes\n" + "\n".join(failures))
    print("[PASS] formal v3.5 result hashes are byte-identical")


if __name__ == "__main__":
    main()
