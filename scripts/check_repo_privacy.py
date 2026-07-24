#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_SUFFIXES = {".pyc", ".pdf", ".tgz", ".tar", ".zip", ".jsonl"}
FORBIDDEN_PARTS = {"__pycache__", "管理员私有_v0_1", "private", "private-data"}
FORBIDDEN_NAME_FRAGMENTS = ("盲判结果", "盲化映射")
CONTENT_PATTERNS = {
    "absolute_user_path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    "OpenAI_style_key": re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    "GitHub_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "private_key": re.compile(rb"BEGIN [A-Z ]+ PRIVATE KEY"),
}


def iter_files():
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        yield path


def main() -> None:
    failures = []
    for path in iter_files():
        relative = path.relative_to(ROOT)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden suffix: {relative}")
        if FORBIDDEN_PARTS.intersection(relative.parts):
            failures.append(f"forbidden directory: {relative}")
        if any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS):
            failures.append(f"forbidden private filename: {relative}")
        if path.stat().st_size > 20 * 1024 * 1024:
            failures.append(f"file larger than 20 MiB: {relative}")
        data = path.read_bytes()
        for label, pattern in CONTENT_PATTERNS.items():
            if pattern.search(data):
                failures.append(f"{label}: {relative}")
    if failures:
        raise SystemExit("[FAIL] repository privacy boundary\n" + "\n".join(sorted(set(failures))))
    print("[PASS] repository privacy boundary")


if __name__ == "__main__":
    main()
