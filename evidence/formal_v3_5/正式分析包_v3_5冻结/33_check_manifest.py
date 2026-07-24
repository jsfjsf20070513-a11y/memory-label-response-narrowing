#!/usr/bin/env python3
"""创建或核验冻结包清单；任何未登记文件、缺失文件和字节码均失败。"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "SHA256SUMS.txt"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def actual_files() -> list[Path]:
    files = []
    residues = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE)
        if path.name == "__pycache__" or path.suffix == ".pyc":
            residues.append(str(relative) + ("/" if path.is_dir() else ""))
        if path.is_file() and path != MANIFEST:
            files.append(path)
    if residues:
        raise SystemExit(f"字节码残留：{sorted(residues)}")
    return sorted(files, key=lambda path: str(path.relative_to(HERE)))


def create() -> None:
    lines = [f"{sha256(path)}  {path.relative_to(HERE)}" for path in actual_files()]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(lines)}")
    print(f"manifest_sha256={sha256(MANIFEST)}")


def check() -> None:
    if not MANIFEST.exists():
        raise SystemExit("缺 SHA256SUMS.txt")
    expected = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative in expected:
            raise SystemExit(f"清单重复：{relative}")
        expected[relative] = digest
    actual = {str(path.relative_to(HERE)): path for path in actual_files()}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    bad = sorted(relative for relative, path in actual.items()
                 if relative in expected and sha256(path) != expected[relative])
    if missing or extra or bad:
        raise SystemExit(f"清单核验失败：缺={missing} 多={extra} 哈希错={bad}")
    print(f"[PASS] manifest files={len(actual)} sha256={sha256(MANIFEST)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    create() if args.create else check()


if __name__ == "__main__":
    main()
