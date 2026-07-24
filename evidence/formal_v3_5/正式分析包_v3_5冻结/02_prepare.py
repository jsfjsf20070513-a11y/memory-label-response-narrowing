#!/usr/bin/env python3
"""从冻结菜单重建三题节选，并在研究回答产生前生成完整随机表。"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
FROZEN_MENU = HERE.parent.parent / "22_菜单冻结版.md"
FROZEN_MENU_SHA256 = "13f291bdf3cc1801aec26da093586f22bc93ab3ab2e9f999abafe65a96665f3b"
CONFIG_PATH = HERE / "01_config.json"
MENU_OUT = HERE / "03_menu_excerpt.md"
RANDOM_OUT = HERE / "04_random_table.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_json(value: object, path: Path) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def section(lines: list[str], start: str, ends: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    active = False
    for line in lines:
        if not active and line.startswith(start):
            active = True
        elif active and any(line.startswith(end) for end in ends):
            break
        if active:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    if not out:
        raise SystemExit(f"未找到冻结菜单节：{start}")
    return out


def build_menu_excerpt() -> str:
    if sha256(FROZEN_MENU) != FROZEN_MENU_SHA256:
        raise SystemExit("22 号冻结菜单哈希不符，拒绝准备正式实验")
    lines = FROZEN_MENU.read_text(encoding="utf-8").splitlines()
    parts = [
        section(lines, "## 编码者共通说明", ("## F 题菜单",)),
        section(lines, "### S2〔", ("### S3〔",)),
        section(lines, "### S8'〔", ("### S9'〔",)),
        section(lines, "### S10'〔", ()),
    ]
    header = [
        "# 正式实验菜单节选（S2 / S8' / S10'）",
        "",
        f"> 由 02_prepare.py 从 22_菜单冻结版.md（SHA-256 `{FROZEN_MENU_SHA256}`）机械抽取。",
        "> 节内文字未经人工修改；S8' 只用于登记复现。",
        "",
    ]
    body: list[str] = []
    for part in parts:
        body.extend(part)
        body.append("")
    return "\n".join(header + body).rstrip() + "\n"


def has_bad_arm_run(specs: list[dict]) -> bool:
    arms = [row["arm"] for row in specs]
    if any(arms[i] == arms[i + 1] == arms[i + 2] for i in range(len(arms) - 2)):
        return True
    return any(len(set(arms[i:i + 6])) < 3 for i in range(len(arms) - 5))


def build_random_table(config: dict) -> dict:
    rng = random.Random(config["random_seed"])
    blocks: list[dict] = []
    for question, spec in config["questions"].items():
        for i in range(1, spec["blocks"] + 1):
            blocks.append({
                "block_id": f"{question}-B{i:02d}",
                "question": question,
                "role": spec["role"],
            })

    permutations = list(itertools.permutations(("N", "G", "M")))
    # 18 个完整排列原本每个“位置×实验臂”各出现 6 次。16 块需去掉
    # 两个排列；固定去掉两个逐位都不同的排列，使九个位置格均为 5 或 6，
    # 避免某一臂在 A/B/C 中的位置明显偏斜。
    mapping_pool = permutations * 3
    removals = next(
        pair for pair in itertools.combinations(permutations, 2)
        if all(left != right for left, right in zip(*pair, strict=True))
    )
    for permutation in removals:
        mapping_pool.remove(permutation)
    if len(mapping_pool) != len(blocks):
        raise SystemExit("盲标平衡池大小与块数不符")
    rng.shuffle(mapping_pool)
    rng.shuffle(blocks)
    blind_mapping = {}
    for block, perm in zip(blocks, mapping_pool, strict=True):
        blind_mapping[block["block_id"]] = dict(zip(("A", "B", "C"), perm, strict=True))

    units = [
        {"block_id": block["block_id"], "question": block["question"], "arm": arm}
        for block in blocks
        for arm in ("N", "G", "M")
    ]
    for _ in range(100_000):
        rng.shuffle(units)
        if not has_bad_arm_run(units):
            break
    else:
        raise SystemExit("未能生成满足交错约束的生成顺序")

    question_order = {}
    for slot in sorted(config["coding_slots"]):
        order = list(config["questions"])
        rng.shuffle(order)
        question_order[slot] = order

    sentinel_order = {}
    for slot in sorted(config["coding_slots"]):
        order = [f"T{i}" for i in range(1, 7)]
        rng.shuffle(order)
        sentinel_order[slot] = order

    return {
        "version": config["version"],
        "seed": config["random_seed"],
        "blind_mapping": dict(sorted(blind_mapping.items())),
        "generation_order": [dict(call_index=i, **unit) for i, unit in enumerate(units, 1)],
        "encoding_question_order": question_order,
        "sentinel_task_order": sentinel_order,
        "review_order_rule": "按 sha256(f'{seed}|{reviewer_slot}|{task_id}') 升序；任务集出现后不新增随机数",
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    menu = build_menu_excerpt()
    table = build_random_table(config)
    if "--check" in sys.argv:
        if MENU_OUT.read_text(encoding="utf-8") != menu:
            raise SystemExit("菜单节选无法逐字重建")
        if json.loads(RANDOM_OUT.read_text(encoding="utf-8")) != table:
            raise SystemExit("随机表无法由冻结种子重建")
        print("[PASS] 菜单节选与随机表可重建")
        return
    MENU_OUT.write_text(menu, encoding="utf-8")
    dump_json(table, RANDOM_OUT)
    print(f"menu_sha256={sha256(MENU_OUT)}")
    print(f"random_sha256={sha256(RANDOM_OUT)}")


if __name__ == "__main__":
    main()
