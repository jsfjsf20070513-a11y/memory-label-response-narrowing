#!/usr/bin/env python3
"""生成或核验 v3.4 每个复核批次的任务键固定 Schema。"""

from __future__ import annotations

import argparse
from pathlib import Path

import analysis_v2 as a
import core as c
import pipeline as p


HERE = Path(__file__).resolve().parent
OUT = HERE / "review_schemas"


def schema_for(slot: str, task_ids: list[str]) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "items": {
                "additionalProperties": False,
                "properties": {
                    task_id: {"$ref": "#/$defs/judgment"}
                    for task_id in task_ids
                },
                "required": task_ids,
                "type": "object",
            },
            "slot": {"const": slot, "type": "string"},
        },
        "required": ["slot", "items"],
        "type": "object",
        "$defs": {
            "judgment": {
                "additionalProperties": False,
                "properties": {
                    "reason": {"minLength": 1, "type": "string"},
                    "supported": {"type": "boolean"},
                },
                "required": ["supported", "reason"],
                "type": "object",
            }
        },
    }


def expected_files() -> dict[Path, str]:
    codings = a.load_v32_codings()
    blinded = c.load(a.V32_RUN / "answers_blinded.json")
    rows = {}
    for slot in c.CONFIG["analysis_v3_4"]["new_review_slots"]:
        tasks = p.review_tasks_for(slot, codings, blinded)
        for index, chunk in enumerate(a.review_chunks(tasks), 1):
            path = OUT / f"REVIEW_V34_{slot}_C{index:02d}.schema.json"
            rows[path] = c.canonical_json(schema_for(slot, [task["task_id"] for task in chunk]))
    return rows


def create() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = expected_files()
    for path, text in rows.items():
        path.write_text(text, encoding="utf-8")
    extras = sorted(path for path in OUT.glob("*.json") if path not in rows)
    if extras:
        raise SystemExit(f"存在多余复核 Schema：{[path.name for path in extras]}")
    print(f"[PASS] created keyed review schemas={len(rows)}")


def check() -> None:
    rows = expected_files()
    actual = sorted(OUT.glob("*.json")) if OUT.exists() else []
    if set(actual) != set(rows):
        raise SystemExit("复核 Schema 文件集合不符")
    bad = [path.name for path, text in rows.items() if path.read_text(encoding="utf-8") != text]
    if bad:
        raise SystemExit(f"复核 Schema 内容不符：{bad}")
    print(f"[PASS] keyed review schemas={len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    create() if args.create else check()


if __name__ == "__main__":
    main()
