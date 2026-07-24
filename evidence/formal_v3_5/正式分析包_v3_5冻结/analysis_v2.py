#!/usr/bin/env python3
"""正式分析 v3.5：复建 M1/M2/M3 完整复核，额度恢复后续跑 O1/O2/O3。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema

import core as c
import pipeline as legacy


HERE = c.HERE
RUN = c.RUN_DIR
SOURCE = c.SOURCE_RUN_DIR
PARENT_PACKAGE = HERE.parent / "正式分析包_v3冻结"
PARENT_RUN = HERE.parent / "正式分析运行_v3"
V31_PACKAGE = HERE.parent / "正式分析包_v3_1冻结"
V31_RUN = HERE.parent / "正式分析运行_v3_1"
V32_PACKAGE = HERE.parent / "正式分析包_v3_2冻结"
V32_RUN = HERE.parent / "正式分析运行_v3_2"
V33_PACKAGE = HERE.parent / "正式分析包_v3_3冻结"
V33_RUN = HERE.parent / "正式分析运行_v3_3"
V34_PACKAGE = HERE.parent / "正式分析包_v3_4冻结"
V34_RUN = HERE.parent / "正式分析运行_v3_4"
EFFECTIVE = RUN / "effective"
TRANSPORT_SCHEMA = HERE / "15_schema_transport.json"
CODEX_MENU_TRANSPORT_SCHEMA = HERE / "15_schema_transport_codex_menu.json"
CODEX_OPEN_TRANSPORT_SCHEMA = HERE / "17_schema_transport_codex_open.json"
CANONICAL_SCHEMAS = {
    "menu": HERE / "12_schema_coding_menu.json",
    "open": HERE / "13_schema_coding_open.json",
}


def verify_source_generation() -> dict:
    cfg = c.CONFIG["analysis_v2"]
    manifest_path = SOURCE / "manifest_generation.json"
    if c.sha256(manifest_path) != cfg["source_generation_manifest_sha256"]:
        raise SystemExit("源 generation manifest 哈希不符")
    manifest = c.load(manifest_path)
    if manifest.get("stage") != "generation":
        raise SystemExit("源 generation manifest 阶段名不符")
    for relative, expected in manifest.get("files", {}).items():
        path = SOURCE / relative
        if not path.is_file() or c.sha256(path) != expected:
            raise SystemExit(f"源生成证据链缺失或被修改：{relative}")
    expected_answers = {
        "answers_blinded.json": cfg["source_answers_blinded_sha256"],
        "answers_unblinded.json": cfg["source_answers_unblinded_sha256"],
    }
    for name, expected in expected_answers.items():
        if c.sha256(SOURCE / name) != expected:
            raise SystemExit(f"源回答哈希不符：{name}")
    sentinel = c.load(SOURCE / "02_sentinel_report.json")
    if sentinel.get("status") != "PASS":
        raise SystemExit("源哨兵报告不是 PASS")
    return manifest


def parent_reuse_paths() -> list[Path]:
    paths: list[Path] = []
    for slot in c.CONFIG["analysis_v2"]["reused_slots"]:
        paths.extend(sorted((PARENT_RUN / "effective" / "coding").glob(f"{slot}_*.json")))
        paths.extend(sorted((PARENT_RUN / "effective" / "transport").glob(f"ENCODE_V3_{slot}_*.json")))
        paths.extend(sorted((PARENT_RUN / "prompts").glob(f"ENCODE_V3_{slot}_*.txt")))
        paths.extend(sorted((PARENT_RUN / "raw").glob(f"ENCODE_V3_{slot}_*/attempt1.json")))
    return sorted(paths, key=lambda path: str(path.relative_to(PARENT_RUN)))


def parent_reuse_bundle_sha256() -> str:
    rows = {
        str(path.relative_to(PARENT_RUN)): c.sha256(path)
        for path in parent_reuse_paths()
    }
    return c.sha256_text(c.canonical_json(rows))


def verify_parent_v3_failure() -> None:
    cfg = c.CONFIG["analysis_v2"]
    if c.sha256(PARENT_PACKAGE / "SHA256SUMS.txt") != cfg["parent_analysis_package_manifest_sha256"]:
        raise SystemExit("父版 v3 冻结清单哈希不符")
    state_path = PARENT_RUN / "01_run_state.json"
    if c.sha256(state_path) != cfg["parent_run_state_sha256"]:
        raise SystemExit("父版 v3 请求状态哈希不符")
    state = c.load(state_path)
    if state != {
        "first_attempt_failed_units": ["ENCODE_V3_M3_S2_C02"],
        "request_attempts": 25,
    }:
        raise SystemExit("父版 v3 请求状态不符")
    for key, expected in cfg["parent_raw_sha256"].items():
        unit, attempt = key.rsplit("/", 1)
        path = PARENT_RUN / "raw" / unit / f"{attempt}.json"
        if c.sha256(path) != expected:
            raise SystemExit(f"父版 v3 raw 哈希不符：{key}")
    if c.sha256(PARENT_RUN / "03_calibration_report.json") != cfg["parent_calibration_report_sha256"]:
        raise SystemExit("父版 v3 校准报告哈希不符")
    if c.sha256(PARENT_RUN / "manifest_calibration.json") != cfg["parent_calibration_manifest_sha256"]:
        raise SystemExit("父版 v3 校准清单哈希不符")
    if c.load(PARENT_RUN / "03_calibration_report.json").get("status") != "PASS":
        raise SystemExit("父版 v3 六槽校准未通过")
    failures = [
        c.load(PARENT_RUN / "raw" / "ENCODE_V3_M3_S2_C02" / f"attempt{attempt}.json")
        for attempt in (1, 2)
    ]
    for attempt, failure in enumerate(failures, 1):
        errors = failure.get("errors", [])
        if (
            failure.get("valid") is not False
            or failure.get("attempt") != attempt
            or (failure.get("raw") or {}).get("returncode") != 0
            or len(errors) != 1
            or "菜单方向不得重复填写名称边界" not in errors[0]
        ):
            raise SystemExit(f"父版 v3 正式失败记录不符：attempt{attempt}")
    if (PARENT_RUN / "manifest_coding.json").exists():
        raise SystemExit("父版 v3 不应存在完整正式编码清单")
    if parent_reuse_bundle_sha256() != cfg["parent_reuse_bundle_sha256"]:
        raise SystemExit("父版 v3 M1/M2 复用证据束哈希不符")
    if len(parent_reuse_paths()) != 54:
        raise SystemExit("父版 v3 M1/M2 复用证据束文件数不符")
    formal_rows = [c.load(path) for path in (PARENT_RUN / "raw").glob("ENCODE*/attempt*.json")]
    if sum(row.get("valid") is True for row in formal_rows) != 17:
        raise SystemExit("父版 v3 有效正式 raw 数不符")
    verify_parent_reused_canonical()


def verify_v31_transport_rejection() -> None:
    """锁定 v3.1 在推理前因 Codex 严格 Schema 拒绝而停止的事实。"""
    cfg = c.CONFIG["analysis_v2"]
    if c.sha256(V31_PACKAGE / "SHA256SUMS.txt") != cfg["v31_package_manifest_sha256"]:
        raise SystemExit("v3.1 冻结清单哈希不符")
    state_path = V31_RUN / "01_run_state.json"
    raw_path = V31_RUN / "raw" / "CAL_V31_M3" / "attempt1.json"
    if c.sha256(state_path) != cfg["v31_run_state_sha256"]:
        raise SystemExit("v3.1 请求状态哈希不符")
    if c.sha256(raw_path) != cfg["v31_raw_sha256"]:
        raise SystemExit("v3.1 校准拒绝 raw 哈希不符")
    if c.load(state_path) != {
        "first_attempt_failed_units": ["CAL_V31_M3"],
        "request_attempts": 1,
    }:
        raise SystemExit("v3.1 请求状态内容不符")
    raw = c.load(raw_path)
    stdout = ((raw.get("raw") or {}).get("stdout") or "")
    if (
        raw.get("valid") is not False
        or raw.get("attempt") != 1
        or raw.get("effective_sha256") is not None
        or (raw.get("raw") or {}).get("returncode") != 1
        or "invalid_json_schema" not in stdout
        or "properties', 'method" not in stdout
        or "schema must have a 'type' key" not in stdout
        or '"type":"agent_message"' in stdout
    ):
        raise SystemExit("v3.1 并非登记的推理前 Schema 拒绝")
    raw_files = sorted((V31_RUN / "raw").glob("*/attempt*.json"))
    if raw_files != [raw_path]:
        raise SystemExit("v3.1 应只有一次推理前校准请求")
    if (V31_RUN / "03_calibration_report.json").exists() or (V31_RUN / "manifest_coding.json").exists():
        raise SystemExit("v3.1 不应通过校准或进入正式编码")


def verify_external_stage(run_dir: Path, name: str) -> None:
    path = run_dir / f"manifest_{name}.json"
    if not path.is_file():
        raise SystemExit(f"v3.2 缺阶段清单：{name}")
    doc = c.load(path)
    if doc.get("stage") != name:
        raise SystemExit(f"v3.2 阶段清单名称不符：{name}")
    for relative, expected in doc.get("files", {}).items():
        target = run_dir / relative
        if not target.is_file() or c.sha256(target) != expected:
            raise SystemExit(f"v3.2 阶段产物缺失或被修改：{relative}")


def v32_coding_paths() -> list[Path]:
    return sorted((V32_RUN / "effective" / "coding").glob("*.json"), key=lambda path: path.name)


def v32_coding_bundle_sha256() -> str:
    rows = {
        str(path.relative_to(V32_RUN)): c.sha256(path)
        for path in v32_coding_paths()
    }
    return c.sha256_text(c.canonical_json(rows))


def verify_v32_completed_coding_and_review_failure() -> None:
    cfg = c.CONFIG["analysis_v3_3"]
    if c.sha256(V32_PACKAGE / "SHA256SUMS.txt") != cfg["v32_package_manifest_sha256"]:
        raise SystemExit("v3.2 冻结清单哈希不符")
    state_path = V32_RUN / "01_run_state.json"
    if c.sha256(state_path) != cfg["v32_run_state_sha256"]:
        raise SystemExit("v3.2 请求状态哈希不符")
    if c.load(state_path) != {
        "first_attempt_failed_units": ["REVIEW_M1"],
        "request_attempts": 36,
    }:
        raise SystemExit("v3.2 请求状态内容不符")
    if c.sha256(V32_RUN / "manifest_coding.json") != cfg["v32_coding_manifest_sha256"]:
        raise SystemExit("v3.2 正式编码清单哈希不符")
    for stage in ("sentinel", "generation", "calibration", "coding"):
        verify_external_stage(V32_RUN, stage)
    if len(v32_coding_paths()) != 18 or v32_coding_bundle_sha256() != cfg["v32_coding_bundle_sha256"]:
        raise SystemExit("v3.2 的 18 份规范盲化编码证据束不符")
    raw_paths = [V32_RUN / "raw" / "REVIEW_M1" / f"{attempt}.json" for attempt in ("attempt1", "attempt2")]
    for path, (attempt, expected) in zip(raw_paths, sorted(cfg["v32_review_raw_sha256"].items())):
        if c.sha256(path) != expected:
            raise SystemExit(f"v3.2 无效复核 raw 哈希不符：{attempt}")
        row = c.load(path)
        errors = row.get("errors", [])
        if (
            row.get("valid") is not False
            or row.get("effective_sha256") is not None
            or (row.get("raw") or {}).get("returncode") != 0
            or len(errors) != 1
            or "复核任务集不符" not in errors[0]
        ):
            raise SystemExit(f"v3.2 无效复核记录内容不符：{attempt}")
    raw_records = sorted((V32_RUN / "raw").glob("*/attempt*.json"))
    if len(raw_records) != 36 or sum(c.load(path).get("valid") is True for path in raw_records) != 34:
        raise SystemExit("v3.2 请求总数或有效请求数不符")
    if (V32_RUN / "manifest_review.json").exists() or (V32_RUN / "summary.json").exists():
        raise SystemExit("v3.2 不应完成复核或汇总")


def load_v32_codings() -> dict[str, dict[str, dict]]:
    codings: dict[str, dict[str, dict]] = {}
    for slot in c.CONFIG["analysis_v3_3"]["inherited_coding_slots"]:
        codings[slot] = {}
        for question in c.CONFIG["questions"]:
            codings[slot][question] = c.load(V32_RUN / "effective" / "coding" / f"{slot}_{question}.json")
    return codings


def prepare_review_inputs() -> None:
    auth = c.verify_run_authorization()
    verify_v32_completed_coding_and_review_failure()
    cfg = c.CONFIG["analysis_v3_3"]
    copied_codings = []
    for name in ("answers_blinded.json", "answers_unblinded.json", "02_sentinel_report.json", "03_calibration_report.json"):
        source = V32_RUN / name
        copy_exact(source, RUN / name, c.sha256(source))
    for source in v32_coding_paths():
        target = EFFECTIVE / "coding" / source.name
        copy_exact(source, target, c.sha256(source))
        copied_codings.append(target)
    attestation = {
        "analysis_package_manifest_sha256": auth["package_manifest_sha256"],
        "inherited_coding_files": len(copied_codings),
        "v32_coding_bundle_sha256": cfg["v32_coding_bundle_sha256"],
        "v32_coding_manifest_sha256": cfg["v32_coding_manifest_sha256"],
        "v32_package_manifest_sha256": cfg["v32_package_manifest_sha256"],
        "v32_review_failure_unit": "REVIEW_M1",
        "v32_review_raw_sha256": cfg["v32_review_raw_sha256"],
        "v32_run_state_sha256": cfg["v32_run_state_sha256"],
    }
    c.dump(attestation, RUN / "source_v32_attestation.json")
    c.write_stage_manifest("sentinel", [
        RUN / c.AUTH_FILENAME,
        RUN / "02_sentinel_report.json",
        RUN / "source_v32_attestation.json",
    ])
    c.write_stage_manifest("generation", [
        RUN / "answers_blinded.json",
        RUN / "answers_unblinded.json",
        RUN / "manifest_sentinel.json",
        RUN / "source_v32_attestation.json",
    ])
    c.write_stage_manifest("calibration", [
        RUN / "03_calibration_report.json",
        RUN / "manifest_generation.json",
        RUN / "source_v32_attestation.json",
    ])
    c.write_stage_manifest("coding", copied_codings + [
        RUN / c.AUTH_FILENAME,
        RUN / "manifest_calibration.json",
        RUN / "manifest_generation.json",
        RUN / "source_v32_attestation.json",
    ])
    print("[PASS] 已复建并锁定 v3.2 的 18 份完整盲化编码；两份无效复核输出未复用")


def review_chunks(tasks: list[dict]) -> list[list[dict]]:
    size = c.CONFIG["analysis_v3_4"]["review_chunk_size"]
    return [tasks[index:index + size] for index in range(0, len(tasks), size)]


def v33_m1_bundle_paths() -> list[Path]:
    paths = []
    paths.extend(sorted((V33_RUN / "effective" / "review_chunks").glob("REVIEW_V33_M1_*.json")))
    paths.extend(sorted((V33_RUN / "prompts").glob("REVIEW_V33_M1_*.txt")))
    paths.extend(sorted((V33_RUN / "raw").glob("REVIEW_V33_M1_*/attempt1.json")))
    paths.append(V33_RUN / "effective" / "review" / "M1.json")
    return sorted(paths, key=lambda path: str(path.relative_to(V33_RUN)))


def v33_m1_bundle_sha256() -> str:
    rows = {str(path.relative_to(V33_RUN)): c.sha256(path) for path in v33_m1_bundle_paths()}
    return c.sha256_text(c.canonical_json(rows))


def verify_v33_m1_review_and_m2_failure() -> None:
    cfg = c.CONFIG["analysis_v3_4"]
    if c.sha256(V33_PACKAGE / "SHA256SUMS.txt") != cfg["v33_package_manifest_sha256"]:
        raise SystemExit("v3.3 冻结清单哈希不符")
    if c.sha256(V33_RUN / "01_run_state.json") != cfg["v33_run_state_sha256"]:
        raise SystemExit("v3.3 请求状态哈希不符")
    if c.load(V33_RUN / "01_run_state.json") != {
        "first_attempt_failed_units": ["REVIEW_V33_M2_C01"],
        "request_attempts": 7,
    }:
        raise SystemExit("v3.3 请求状态内容不符")
    for stage in ("sentinel", "generation", "calibration", "coding"):
        verify_external_stage(V33_RUN, stage)
    if len(v33_m1_bundle_paths()) != 16 or v33_m1_bundle_sha256() != cfg["v33_m1_review_bundle_sha256"]:
        raise SystemExit("v3.3 M1 完整复核证据束不符")
    merged_path = V33_RUN / "effective" / "review" / "M1.json"
    if c.sha256(merged_path) != cfg["v33_m1_review_sha256"]:
        raise SystemExit("v3.3 M1 合并复核哈希不符")
    items = []
    for index in range(1, 6):
        unit = f"REVIEW_V33_M1_C{index:02d}"
        prompt_path = V33_RUN / "prompts" / f"{unit}.txt"
        output_path = V33_RUN / "effective" / "review_chunks" / f"{unit}.json"
        raw_path = V33_RUN / "raw" / unit / "attempt1.json"
        raw = c.load(raw_path)
        if (
            raw.get("valid") is not True
            or raw.get("attempt") != 1
            or raw.get("prompt_sha256") != c.sha256(prompt_path)
            or raw.get("effective_sha256") != c.sha256(output_path)
            or raw.get("errors") != []
        ):
            raise SystemExit(f"v3.3 M1 有效复核原始链不符：{unit}")
        items.extend(c.load(output_path)["items"])
    reconstructed = {"items": items, "slot": "M1"}
    if c.canonical_json(reconstructed).encode() != merged_path.read_bytes():
        raise SystemExit("v3.3 M1 五批不能逐字重建合并文件")
    codings = load_v32_codings()
    blinded = c.load(V32_RUN / "answers_blinded.json")
    errors = legacy.validate_review(reconstructed, "M1", legacy.review_tasks_for("M1", codings, blinded))
    if errors:
        raise SystemExit(f"v3.3 M1 完整复核语义复验失败：{errors[:3]}")
    for attempt, expected in sorted(cfg["v33_m2_failure_raw_sha256"].items()):
        path = V33_RUN / "raw" / "REVIEW_V33_M2_C01" / f"{attempt}.json"
        if c.sha256(path) != expected:
            raise SystemExit(f"v3.3 M2 无效复核 raw 哈希不符：{attempt}")
        row = c.load(path)
        if (
            row.get("valid") is not False
            or row.get("effective_sha256") is not None
            or (row.get("raw") or {}).get("returncode") != 0
            or len(row.get("errors", [])) != 1
            or "复核任务集不符" not in row["errors"][0]
        ):
            raise SystemExit(f"v3.3 M2 无效复核内容不符：{attempt}")
    raw_records = sorted((V33_RUN / "raw").glob("*/attempt*.json"))
    if len(raw_records) != 7 or sum(c.load(path).get("valid") is True for path in raw_records) != 5:
        raise SystemExit("v3.3 请求总数或有效请求数不符")
    if (V33_RUN / "manifest_review.json").exists() or (V33_RUN / "summary.json").exists():
        raise SystemExit("v3.3 不应完成全槽复核或汇总")


def prepare_keyed_review_inputs() -> None:
    auth = c.verify_run_authorization()
    verify_v32_completed_coding_and_review_failure()
    verify_v33_m1_review_and_m2_failure()
    cfg = c.CONFIG["analysis_v3_4"]
    copied_codings = []
    for name in ("answers_blinded.json", "answers_unblinded.json", "02_sentinel_report.json", "03_calibration_report.json"):
        source = V33_RUN / name
        copy_exact(source, RUN / name, c.sha256(source))
    for source in sorted((V33_RUN / "effective" / "coding").glob("*.json")):
        target = EFFECTIVE / "coding" / source.name
        copy_exact(source, target, c.sha256(source))
        copied_codings.append(target)
    source_review = V33_RUN / "effective" / "review" / "M1.json"
    copied_review = EFFECTIVE / "review" / "M1.json"
    copy_exact(source_review, copied_review, cfg["v33_m1_review_sha256"])
    attestation = {
        "analysis_package_manifest_sha256": auth["package_manifest_sha256"],
        "inherited_coding_files": len(copied_codings),
        "reused_complete_review_slots": cfg["reused_review_slots"],
        "v33_m1_review_bundle_sha256": cfg["v33_m1_review_bundle_sha256"],
        "v33_m1_review_sha256": cfg["v33_m1_review_sha256"],
        "v33_m2_failure_raw_sha256": cfg["v33_m2_failure_raw_sha256"],
        "v33_package_manifest_sha256": cfg["v33_package_manifest_sha256"],
        "v33_run_state_sha256": cfg["v33_run_state_sha256"],
    }
    c.dump(attestation, RUN / "source_v33_attestation.json")
    c.write_stage_manifest("sentinel", [RUN / c.AUTH_FILENAME, RUN / "02_sentinel_report.json", RUN / "source_v33_attestation.json"])
    c.write_stage_manifest("generation", [RUN / "answers_blinded.json", RUN / "answers_unblinded.json", RUN / "manifest_sentinel.json", RUN / "source_v33_attestation.json"])
    c.write_stage_manifest("calibration", [RUN / "03_calibration_report.json", RUN / "manifest_generation.json", RUN / "source_v33_attestation.json"])
    c.write_stage_manifest("coding", copied_codings + [RUN / c.AUTH_FILENAME, RUN / "manifest_calibration.json", RUN / "manifest_generation.json", RUN / "source_v33_attestation.json"])
    print("[PASS] 已复建 18 份编码与 v3.3 完整 M1 复核；M2 两份无效输出未复用")


def render_keyed_review_prompt(slot: str, tasks: list[dict]) -> str:
    template = (HERE / "52_prompt_review_keyed.md").read_text(encoding="utf-8")
    rows = []
    for task in tasks:
        rows.append(
            f"【{task['task_id']}】\n完整回答：{task['answer_text']}\n"
            f"证据短语：{json.dumps(task['evidence'], ensure_ascii=False)}\n"
            f"方向名称：{task['name']}\n方向边界：{task['definition']}"
        )
    return template.replace("{{SLOT}}", slot).replace("{{TASKS}}", "\n\n".join(rows))


def keyed_schema_path(slot: str, index: int) -> Path:
    return HERE / "review_schemas" / f"REVIEW_V34_{slot}_C{index:02d}.schema.json"


def validate_keyed_review(doc: dict, slot: str, tasks: list[dict]) -> list[str]:
    errors = []
    if doc.get("slot") != slot:
        errors.append("slot 不符")
    expected = [task["task_id"] for task in tasks]
    got = list((doc.get("items") or {}).keys())
    if set(got) != set(expected) or len(got) != len(expected):
        errors.append(f"任务键集合不符：缺={sorted(set(expected)-set(got))[:5]} 多={sorted(set(got)-set(expected))[:5]}")
    return errors


def normalize_keyed_review(doc: dict, tasks: list[dict]) -> dict:
    return {
        "items": [
            {"task_id": task["task_id"], **doc["items"][task["task_id"]]}
            for task in tasks
        ],
        "slot": doc["slot"],
    }


def v34_m2_m3_bundle_paths() -> list[Path]:
    paths = []
    for slot in ("M2", "M3"):
        paths.extend(sorted((V34_RUN / "effective" / "review_transport").glob(f"REVIEW_V34_{slot}_*.json")))
        paths.extend(sorted((V34_RUN / "prompts").glob(f"REVIEW_V34_{slot}_*.txt")))
        paths.extend(sorted((V34_RUN / "raw").glob(f"REVIEW_V34_{slot}_*/attempt1.json")))
        paths.append(V34_RUN / "effective" / "review" / f"{slot}.json")
    return sorted(paths, key=lambda path: str(path.relative_to(V34_RUN)))


def v34_m2_m3_bundle_sha256() -> str:
    rows = {str(path.relative_to(V34_RUN)): c.sha256(path) for path in v34_m2_m3_bundle_paths()}
    return c.sha256_text(c.canonical_json(rows))


def verify_v34_completed_reviews_and_quota_failure() -> None:
    cfg = c.CONFIG["analysis_v3_5"]
    if c.sha256(V34_PACKAGE / "SHA256SUMS.txt") != cfg["v34_package_manifest_sha256"]:
        raise SystemExit("v3.4 冻结清单哈希不符")
    if c.sha256(V34_RUN / "01_run_state.json") != cfg["v34_run_state_sha256"]:
        raise SystemExit("v3.4 请求状态哈希不符")
    if c.load(V34_RUN / "01_run_state.json") != {
        "first_attempt_failed_units": ["REVIEW_V34_O1_C01"],
        "request_attempts": 12,
    }:
        raise SystemExit("v3.4 请求状态内容不符")
    for stage in ("sentinel", "generation", "calibration", "coding"):
        verify_external_stage(V34_RUN, stage)
    if len(v34_m2_m3_bundle_paths()) != 32 or v34_m2_m3_bundle_sha256() != cfg["v34_m2_m3_review_bundle_sha256"]:
        raise SystemExit("v3.4 M2/M3 完整复核证据束不符")
    codings = load_v32_codings()
    blinded = c.load(V32_RUN / "answers_blinded.json")
    for slot, expected_sha in (("M2", cfg["v34_m2_review_sha256"]), ("M3", cfg["v34_m3_review_sha256"])):
        full_tasks = legacy.review_tasks_for(slot, codings, blinded)
        items = []
        for index, tasks in enumerate(review_chunks(full_tasks), 1):
            unit = f"REVIEW_V34_{slot}_C{index:02d}"
            prompt_path = V34_RUN / "prompts" / f"{unit}.txt"
            output_path = V34_RUN / "effective" / "review_transport" / f"{unit}.json"
            raw = c.load(V34_RUN / "raw" / unit / "attempt1.json")
            if (
                raw.get("valid") is not True
                or raw.get("attempt") != 1
                or raw.get("prompt_sha256") != c.sha256(prompt_path)
                or raw.get("effective_sha256") != c.sha256(output_path)
                or raw.get("errors") != []
            ):
                raise SystemExit(f"v3.4 有效复核原始链不符：{unit}")
            doc = c.load(output_path)
            errors = validate_keyed_review(doc, slot, tasks)
            if errors:
                raise SystemExit(f"v3.4 任务键复验失败：{unit}：{errors[:3]}")
            items.extend(normalize_keyed_review(doc, tasks)["items"])
        reconstructed = {"items": items, "slot": slot}
        merged_path = V34_RUN / "effective" / "review" / f"{slot}.json"
        if c.sha256(merged_path) != expected_sha or c.canonical_json(reconstructed).encode() != merged_path.read_bytes():
            raise SystemExit(f"v3.4 {slot} 五批不能逐字重建合并文件")
        errors = legacy.validate_review(reconstructed, slot, full_tasks)
        if errors:
            raise SystemExit(f"v3.4 {slot} 完整复核语义复验失败：{errors[:3]}")
    for attempt, expected in sorted(cfg["v34_o1_quota_raw_sha256"].items()):
        path = V34_RUN / "raw" / "REVIEW_V34_O1_C01" / f"{attempt}.json"
        if c.sha256(path) != expected:
            raise SystemExit(f"v3.4 O1 额度 raw 哈希不符：{attempt}")
        row = c.load(path)
        raw = row.get("raw") or {}
        stdout = raw.get("stdout") or ""
        if (
            row.get("valid") is not False
            or row.get("effective_sha256") is not None
            or raw.get("returncode") != 1
            or '"api_error_status":429' not in stdout
            or "You've hit your session limit" not in stdout
            or '"input_tokens":0' not in stdout
            or '"output_tokens":0' not in stdout
        ):
            raise SystemExit(f"v3.4 O1 不是登记的推理前额度拒绝：{attempt}")
    raw_records = sorted((V34_RUN / "raw").glob("*/attempt*.json"))
    if len(raw_records) != 12 or sum(c.load(path).get("valid") is True for path in raw_records) != 10:
        raise SystemExit("v3.4 请求总数或有效请求数不符")
    if (V34_RUN / "manifest_review.json").exists() or (V34_RUN / "summary.json").exists():
        raise SystemExit("v3.4 不应完成全槽复核或汇总")


def prepare_quota_resume_inputs() -> None:
    auth = c.verify_run_authorization()
    verify_v32_completed_coding_and_review_failure()
    verify_v33_m1_review_and_m2_failure()
    verify_v34_completed_reviews_and_quota_failure()
    cfg = c.CONFIG["analysis_v3_5"]
    copied_codings = []
    copied_reviews = []
    for name in ("answers_blinded.json", "answers_unblinded.json", "02_sentinel_report.json", "03_calibration_report.json"):
        source = V34_RUN / name
        copy_exact(source, RUN / name, c.sha256(source))
    for source in sorted((V34_RUN / "effective" / "coding").glob("*.json")):
        target = EFFECTIVE / "coding" / source.name
        copy_exact(source, target, c.sha256(source))
        copied_codings.append(target)
    for slot in cfg["reused_review_slots"]:
        source = V34_RUN / "effective" / "review" / f"{slot}.json"
        target = EFFECTIVE / "review" / source.name
        copy_exact(source, target, c.sha256(source))
        copied_reviews.append(target)
    attestation = {
        "analysis_package_manifest_sha256": auth["package_manifest_sha256"],
        "reused_complete_review_slots": cfg["reused_review_slots"],
        "v34_m2_m3_review_bundle_sha256": cfg["v34_m2_m3_review_bundle_sha256"],
        "v34_o1_quota_raw_sha256": cfg["v34_o1_quota_raw_sha256"],
        "v34_package_manifest_sha256": cfg["v34_package_manifest_sha256"],
        "v34_run_state_sha256": cfg["v34_run_state_sha256"],
    }
    c.dump(attestation, RUN / "source_v34_attestation.json")
    c.write_stage_manifest("sentinel", [RUN / c.AUTH_FILENAME, RUN / "02_sentinel_report.json", RUN / "source_v34_attestation.json"])
    c.write_stage_manifest("generation", [RUN / "answers_blinded.json", RUN / "answers_unblinded.json", RUN / "manifest_sentinel.json", RUN / "source_v34_attestation.json"])
    c.write_stage_manifest("calibration", [RUN / "03_calibration_report.json", RUN / "manifest_generation.json", RUN / "source_v34_attestation.json"])
    c.write_stage_manifest("coding", copied_codings + [RUN / c.AUTH_FILENAME, RUN / "manifest_calibration.json", RUN / "manifest_generation.json", RUN / "source_v34_attestation.json"])
    c.write_stage_manifest("inherited_review", copied_reviews + [RUN / "manifest_coding.json", RUN / "source_v34_attestation.json"])
    print("[PASS] 已复建 18 份编码与 M1/M2/M3 完整复核；O1 两次推理前额度拒绝未复用")


def run_review_v35() -> None:
    c.verify_run_authorization()
    for stage in ("sentinel", "generation", "calibration", "coding", "inherited_review"):
        c.verify_stage_manifest(stage)
    legacy.require_sentinel_pass()
    blinded = c.load(RUN / "answers_blinded.json")
    codings = legacy.load_codings()
    cfg = c.CONFIG["analysis_v3_5"]
    plans = {slot: review_chunks(legacy.review_tasks_for(slot, codings, blinded)) for slot in cfg["new_review_slots"]}
    if sum(len(chunks) for chunks in plans.values()) != cfg["review_calls"]:
        raise SystemExit("额度续跑复核调用数漂移")
    called_units = []
    transport_paths = []
    merged_paths = [EFFECTIVE / "review" / f"{slot}.json" for slot in cfg["reused_review_slots"]]
    for slot in cfg["new_review_slots"]:
        spec = c.CONFIG["coding_slots"][slot]
        full_tasks = legacy.review_tasks_for(slot, codings, blinded)
        items = []
        for index, tasks in enumerate(plans[slot], 1):
            unit = f"REVIEW_V35_{slot}_C{index:02d}"
            output = EFFECTIVE / "review_transport" / f"{unit}.json"
            print(f"[REVIEW] {slot} quota_resume={index}/{len(plans[slot])} tasks={len(tasks)}", flush=True)
            doc = c.run_json_unit(
                unit_id=unit,
                provider=spec["provider"],
                model=spec["model"],
                effort=spec["effort"],
                prompt=render_keyed_review_prompt(slot, tasks),
                schema_path=keyed_schema_path(slot, index),
                semantic_validate=lambda doc, slot=slot, tasks=tasks: validate_keyed_review(doc, slot, tasks),
                output_path=output,
            )
            items.extend(normalize_keyed_review(doc, tasks)["items"])
            called_units.append(unit)
            transport_paths.append(output)
        merged = {"items": items, "slot": slot}
        errors = legacy.validate_review(merged, slot, full_tasks)
        if errors:
            raise SystemExit(f"额度续跑合并后复核全集不符 {slot}：{errors[:3]}")
        merged_path = EFFECTIVE / "review" / f"{slot}.json"
        c.dump(merged, merged_path)
        merged_paths.append(merged_path)
    c.write_stage_manifest(
        "review",
        transport_paths + merged_paths + [RUN / c.AUTH_FILENAME, RUN / "manifest_coding.json", RUN / "manifest_inherited_review.json", RUN / "source_v34_attestation.json"] + legacy.request_artifacts(called_units),
    )
    print("[PASS] 复用 M1/M2/M3，O1/O2/O3 的 15 个额度续跑批次完成")


def run_review_v34() -> None:
    c.verify_run_authorization()
    for stage in ("sentinel", "generation", "calibration", "coding"):
        c.verify_stage_manifest(stage)
    legacy.require_sentinel_pass()
    blinded = c.load(RUN / "answers_blinded.json")
    codings = legacy.load_codings()
    cfg = c.CONFIG["analysis_v3_4"]
    plans = {
        slot: review_chunks(legacy.review_tasks_for(slot, codings, blinded))
        for slot in cfg["new_review_slots"]
    }
    if sum(len(chunks) for chunks in plans.values()) != cfg["review_calls"]:
        raise SystemExit("任务键固定复核调用数漂移")
    called_units = []
    transport_paths = []
    merged_paths = [EFFECTIVE / "review" / "M1.json"]
    for slot in cfg["new_review_slots"]:
        spec = c.CONFIG["coding_slots"][slot]
        full_tasks = legacy.review_tasks_for(slot, codings, blinded)
        items = []
        for index, tasks in enumerate(plans[slot], 1):
            unit = f"REVIEW_V34_{slot}_C{index:02d}"
            output = EFFECTIVE / "review_transport" / f"{unit}.json"
            print(f"[REVIEW] {slot} keyed_chunk={index}/{len(plans[slot])} tasks={len(tasks)}", flush=True)
            doc = c.run_json_unit(
                unit_id=unit,
                provider=spec["provider"],
                model=spec["model"],
                effort=spec["effort"],
                prompt=render_keyed_review_prompt(slot, tasks),
                schema_path=keyed_schema_path(slot, index),
                semantic_validate=lambda doc, slot=slot, tasks=tasks: validate_keyed_review(doc, slot, tasks),
                output_path=output,
            )
            items.extend(normalize_keyed_review(doc, tasks)["items"])
            called_units.append(unit)
            transport_paths.append(output)
        merged = {"items": items, "slot": slot}
        errors = legacy.validate_review(merged, slot, full_tasks)
        if errors:
            raise SystemExit(f"任务键分批合并后复核全集不符 {slot}：{errors[:3]}")
        merged_path = EFFECTIVE / "review" / f"{slot}.json"
        c.dump(merged, merged_path)
        merged_paths.append(merged_path)
    c.write_stage_manifest(
        "review",
        transport_paths + merged_paths + [RUN / c.AUTH_FILENAME, RUN / "manifest_coding.json", RUN / "source_v33_attestation.json"] + legacy.request_artifacts(called_units),
    )
    print("[PASS] 复用 M1 完整复核，25 个任务键固定批次完成并逐槽无损合并")


def run_review_v33() -> None:
    c.verify_run_authorization()
    for stage in ("sentinel", "generation", "calibration", "coding"):
        c.verify_stage_manifest(stage)
    legacy.require_sentinel_pass()
    blinded = c.load(RUN / "answers_blinded.json")
    codings = legacy.load_codings()
    plans = {}
    for slot in sorted(c.CONFIG["coding_slots"]):
        tasks = legacy.review_tasks_for(slot, codings, blinded)
        plans[slot] = review_chunks(tasks)
    planned_calls = sum(len(chunks) for chunks in plans.values())
    if planned_calls != c.CONFIG["analysis_v3_3"]["review_calls"]:
        raise SystemExit(f"复核分批调用数漂移：{planned_calls}")
    called_units = []
    chunk_paths = []
    merged_paths = []
    for slot in sorted(c.CONFIG["coding_slots"]):
        spec = c.CONFIG["coding_slots"][slot]
        full_tasks = legacy.review_tasks_for(slot, codings, blinded)
        items = []
        chunks = plans[slot]
        for index, tasks in enumerate(chunks, 1):
            unit = f"REVIEW_V33_{slot}_C{index:02d}"
            output = EFFECTIVE / "review_chunks" / f"{unit}.json"
            print(f"[REVIEW] {slot} chunk={index}/{len(chunks)} tasks={len(tasks)}", flush=True)
            doc = c.run_json_unit(
                unit_id=unit,
                provider=spec["provider"],
                model=spec["model"],
                effort=spec["effort"],
                prompt=legacy.render_review_prompt(slot, tasks),
                schema_path=HERE / "14_schema_review.json",
                semantic_validate=lambda doc, slot=slot, tasks=tasks: legacy.validate_review(doc, slot, tasks),
                output_path=output,
            )
            items.extend(doc["items"])
            called_units.append(unit)
            chunk_paths.append(output)
        merged = {"items": items, "slot": slot}
        errors = legacy.validate_review(merged, slot, full_tasks)
        if errors:
            raise SystemExit(f"分批合并后复核任务集不符 {slot}：{errors[:3]}")
        merged_path = EFFECTIVE / "review" / f"{slot}.json"
        c.dump(merged, merged_path)
        merged_paths.append(merged_path)
    c.write_stage_manifest(
        "review",
        chunk_paths + merged_paths + [
            RUN / c.AUTH_FILENAME,
            RUN / "manifest_coding.json",
            RUN / "source_v32_attestation.json",
        ] + legacy.request_artifacts(called_units),
    )
    print("[PASS] 30 个分批复核单元完成并逐槽无损合并")


def run_aggregate_v33() -> None:
    legacy.run_aggregate()


def copy_exact(source: Path, target: Path, expected_sha: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if c.sha256(target) != expected_sha:
            raise SystemExit(f"既有复制件哈希不符：{target.name}")
        return
    shutil.copyfile(source, target)
    if c.sha256(target) != expected_sha:
        raise SystemExit(f"复制后哈希不符：{target.name}")


def prepare_inputs() -> None:
    auth = c.verify_run_authorization()
    verify_source_generation()
    verify_parent_v3_failure()
    verify_v31_transport_rejection()
    cfg = c.CONFIG["analysis_v2"]
    copy_exact(
        SOURCE / "answers_blinded.json",
        RUN / "answers_blinded.json",
        cfg["source_answers_blinded_sha256"],
    )
    copy_exact(
        SOURCE / "answers_unblinded.json",
        RUN / "answers_unblinded.json",
        cfg["source_answers_unblinded_sha256"],
    )
    copy_exact(
        SOURCE / "manifest_generation.json",
        RUN / "source_manifest_generation.json",
        cfg["source_generation_manifest_sha256"],
    )
    sentinel_sha = c.sha256(SOURCE / "02_sentinel_report.json")
    copy_exact(
        SOURCE / "02_sentinel_report.json",
        RUN / "02_sentinel_report.json",
        sentinel_sha,
    )
    reused_canonical: list[Path] = []
    for slot in cfg["reused_slots"]:
        for source in sorted((PARENT_RUN / "effective" / "coding").glob(f"{slot}_*.json")):
            target = EFFECTIVE / "coding" / source.name
            copy_exact(source, target, c.sha256(source))
            reused_canonical.append(target)
    attestation = {
        "analysis_package_manifest_sha256": auth["package_manifest_sha256"],
        "parent_analysis_package_manifest_sha256": cfg["parent_analysis_package_manifest_sha256"],
        "parent_failed_formal_unit": "ENCODE_V3_M3_S2_C02",
        "parent_reuse_bundle_sha256": cfg["parent_reuse_bundle_sha256"],
        "parent_valid_formal_outputs": 17,
        "v31_package_manifest_sha256": cfg["v31_package_manifest_sha256"],
        "v31_pre_inference_schema_rejection_raw_sha256": cfg["v31_raw_sha256"],
        "v31_run_state_sha256": cfg["v31_run_state_sha256"],
        "reused_complete_canonical_slots": cfg["reused_slots"],
        "reused_valid_formal_outputs": 16,
        "parent_run_state_sha256": cfg["parent_run_state_sha256"],
        "source_answers_blinded_sha256": cfg["source_answers_blinded_sha256"],
        "source_answers_unblinded_sha256": cfg["source_answers_unblinded_sha256"],
        "source_generation_manifest_sha256": cfg["source_generation_manifest_sha256"],
        "source_run_directory": SOURCE.name,
    }
    c.dump(attestation, RUN / "source_generation_attestation.json")
    c.dump(
        {
            "files": {
                str(path.relative_to(RUN)): c.sha256(path)
                for path in sorted(reused_canonical, key=str)
            },
            "parent_reuse_bundle_sha256": cfg["parent_reuse_bundle_sha256"],
            "source_run": PARENT_RUN.name,
        },
        RUN / "parent_reuse_attestation.json",
    )
    c.write_stage_manifest(
        "sentinel",
        [
            RUN / c.AUTH_FILENAME,
            RUN / "02_sentinel_report.json",
            RUN / "source_generation_attestation.json",
        ],
    )
    c.write_stage_manifest(
        "generation",
        [
            RUN / "answers_blinded.json",
            RUN / "answers_unblinded.json",
            RUN / "manifest_sentinel.json",
            RUN / "parent_reuse_attestation.json",
            RUN / "source_generation_attestation.json",
            RUN / "source_manifest_generation.json",
        ],
    )
    print("[PASS] 已接入源回答、v3 复用链、v3.1 推理前拒绝与可复算的 M1/M2 盲化编码")


def question_menu(question: str) -> str:
    return legacy.question_menu(question)


def render_blocks(question: str, question_text: str, answers: dict[str, dict[str, str]]) -> str:
    rows = [f"题目：{question_text}"]
    for block_id, values in answers.items():
        labels = []
        for label in c.LABELS:
            rendered = "\n".join(
                f"[{span_id}] {span['text']}"
                for span_id, span in evidence_spans(values[label], label).items()
            )
            labels.append(f"{label}：\n{rendered}")
        rows.append(f"【块 {block_id}】\n" + "\n\n".join(labels))
    return "\n\n".join(rows)


def evidence_spans(text: str, label: str) -> dict[str, dict[str, Any]]:
    """把原文机械切成可引用短句；每个短句仍是原文连续子串。"""
    parts = [
        match.group(0).strip()
        for match in re.finditer(r"[^\n。！？；，,:：]+(?:[\n。！？；，,:：]|$)", text)
        if match.group(0).strip()
    ]
    if not parts:
        parts = [text]
    seen: Counter[str] = Counter()
    spans = {}
    for index, part in enumerate(parts, 1):
        seen[part] += 1
        spans[f"{label}-E{index:03d}"] = {
            "occurrence": seen[part],
            "text": part,
        }
    return spans


def calibration_answers(synthetic: dict) -> dict[str, dict[str, str]]:
    """将长度压力段机械追加到六份合成回答。

    同一压力段按冻结次数重复，且在 A/B/C 中完全相同；它只增加长文定位
    与重复方向去重压力，不改变金标准差异。
    """
    repetitions = synthetic.get("common_suffix_repetitions", 1)
    if not isinstance(repetitions, int) or repetitions < 1:
        raise SystemExit("合成校准压力段重复次数非法")
    suffix = synthetic.get("common_suffix", "") * repetitions
    return {
        block_id: {label: text + suffix for label, text in values.items()}
        for block_id, values in synthetic["blocks"].items()
    }


def render_transport_prompt(
    slot: str,
    question: str,
    question_text: str,
    answers: dict[str, dict[str, str]],
) -> str:
    method = c.CONFIG["coding_slots"][slot]["method"]
    if slot == "M3":
        template_name = "25_prompt_transport_codex_menu.md"
    else:
        template_name = "23_prompt_transport_menu.md" if method == "menu" else "24_prompt_transport_open.md"
    template = (HERE / template_name).read_text(encoding="utf-8")
    prompt = template.replace("{{SLOT}}", slot).replace(
        "{{BLOCKS}}", render_blocks(question, question_text, answers)
    )
    if method == "menu":
        prompt = prompt.replace("{{MENU}}", question_menu(question))
    return prompt


def transport_schema(slot: str) -> Path:
    if slot == "M3":
        return CODEX_MENU_TRANSPORT_SCHEMA
    if slot == "O3":
        return CODEX_OPEN_TRANSPORT_SCHEMA
    return TRANSPORT_SCHEMA


def normalize_transport(doc: dict, slot: str) -> dict:
    """Codex 菜单分表只是运输外壳；合并后回到 v3 的统一内部格式。"""
    if slot != "M3":
        return doc
    blocks = []
    for block in doc["blocks"]:
        answers = {}
        for label in c.LABELS:
            coded = block["answers"][label]
            directions = [
                {
                    "definition": None,
                    "evidence_span_id": direction["evidence_span_id"],
                    "local_id": direction["local_id"],
                    "menu_id": direction["menu_id"],
                    "name": None,
                    "tag": direction["tag"],
                }
                for direction in coded["menu_directions"]
            ] + [
                {
                    "definition": direction["definition"],
                    "evidence_span_id": direction["evidence_span_id"],
                    "local_id": direction["local_id"],
                    "menu_id": None,
                    "name": direction["name"],
                    "tag": direction["tag"],
                }
                for direction in coded["extra_directions"]
            ]
            directions.sort(key=lambda direction: int(direction["local_id"][1:]))
            answers[label] = {
                "directions": directions,
                "identity_evidence_span_id": coded["identity_evidence_span_id"],
                "identity_explicit": coded["identity_explicit"],
            }
        blocks.append({
            "answers": answers,
            "block_id": block["block_id"],
            "comparisons": block["comparisons"],
        })
    return {
        "blocks": blocks,
        "method": doc["method"],
        "question": doc["question"],
        "slot": doc["slot"],
    }


def validate_transport(
    doc: dict,
    slot: str,
    question: str,
    answers: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    method = c.CONFIG["coding_slots"][slot]["method"]
    if doc.get("slot") != slot or doc.get("method") != method or doc.get("question") != question:
        errors.append("slot/method/question 不符")
    expected_blocks = list(answers)
    got_blocks = [block.get("block_id") for block in doc.get("blocks", [])]
    if got_blocks != expected_blocks or len(got_blocks) != len(set(got_blocks)):
        errors.append(f"块集合或次序不符：expected={expected_blocks}, got={got_blocks}")
        return errors
    menu = c.menu_definitions()
    for block in doc["blocks"]:
        block_id = block["block_id"]
        for label in c.LABELS:
            spans = evidence_spans(answers[block_id][label], label)
            coded = block["answers"][label]
            ids = [direction["local_id"] for direction in coded["directions"]]
            if ids != [f"d{i}" for i in range(1, len(ids) + 1)]:
                errors.append(f"{block_id}/{label} local_id 必须从 d1 连续编号")
            for direction in coded["directions"]:
                if direction["evidence_span_id"] not in spans:
                    errors.append(f"{block_id}/{label}/{direction['local_id']} 证据片段编号无效")
                mid = direction["menu_id"]
                name = direction["name"]
                definition = direction["definition"]
                if method == "menu":
                    if mid is not None:
                        if mid not in menu or not mid.startswith(question + "-"):
                            errors.append(f"{block_id}/{label} 菜单编号不属于当前题：{mid}")
                        if name is not None or definition is not None:
                            errors.append(f"{block_id}/{label}/{direction['local_id']} 菜单方向不得重复填写名称边界")
                    elif not isinstance(name, str) or not name.strip() or not isinstance(definition, str) or not definition.strip():
                        errors.append(f"{block_id}/{label}/{direction['local_id']} 菜单外方向缺名称或边界")
                elif mid is not None:
                    errors.append(f"{block_id}/{label}/{direction['local_id']} 开放方向 menu_id 必须为 null")
                elif not isinstance(name, str) or not name.strip() or not isinstance(definition, str) or not definition.strip():
                    errors.append(f"{block_id}/{label}/{direction['local_id']} 开放方向缺名称或边界")
            if coded["identity_explicit"]:
                if coded["identity_evidence_span_id"] not in spans:
                    errors.append(f"{block_id}/{label} 身份显形证据片段编号无效")
            elif coded["identity_evidence_span_id"] is not None:
                errors.append(f"{block_id}/{label} identity=false 时片段编号必须为 null")

        for pair in c.PAIRS:
            allowed = set(c.pair_labels(pair))
            for account in c.ACCOUNTS:
                verdict = block["comparisons"][pair][account]
                choice = verdict["choice"]
                decisive = verdict["decisive"]
                if choice in c.LABELS:
                    if choice not in allowed:
                        errors.append(f"{block_id}/{pair}/{account} 选择对子外标签")
                        continue
                    if not isinstance(decisive, dict) or decisive.get("answer") != choice:
                        errors.append(f"{block_id}/{pair}/{account} decisive 不属于胜方")
                        continue
                    directions = block["answers"][choice]["directions"]
                    matches = [d for d in directions if d["local_id"] == decisive.get("local_id")]
                    if len(matches) != 1:
                        errors.append(f"{block_id}/{pair}/{account} decisive 未引用唯一方向")
                    else:
                        needed = "数学" if account == "math_focus" else "非数学"
                        if matches[0]["tag"] != needed:
                            errors.append(f"{block_id}/{pair}/{account} decisive 标签必须为 {needed}")
                elif decisive is not None:
                    errors.append(f"{block_id}/{pair}/{account} 非方向性判断 decisive 必须为 null")
    return errors


def canonical_direction(
    direction: dict,
    method: str,
    menu: dict[str, tuple[str, str]],
    spans: dict[str, dict[str, Any]],
) -> dict:
    mid = direction["menu_id"]
    span = spans[direction["evidence_span_id"]]
    if method == "menu" and mid is not None:
        name, definition = menu[mid]
        return {
            "definition": definition,
            "evidence": span["text"],
            "from_menu": True,
            "local_id": direction["local_id"],
            "menu_id": mid,
            "name": name,
            "occurrence": span["occurrence"],
            "tag": direction["tag"],
        }
    base = {
        "definition": direction["definition"],
        "evidence": span["text"],
        "local_id": direction["local_id"],
        "name": direction["name"],
        "occurrence": span["occurrence"],
        "tag": direction["tag"],
    }
    if method == "menu":
        base.update({"from_menu": False, "menu_id": None})
    return base


def expand_transport(doc: dict, source_answers: dict[str, dict[str, str]]) -> dict:
    method = doc["method"]
    menu = c.menu_definitions()
    blocks = []
    for block in doc["blocks"]:
        answers = {}
        by_answer: dict[str, dict[str, dict]] = {}
        for label in c.LABELS:
            spans = evidence_spans(source_answers[block["block_id"]][label], label)
            directions = [
                canonical_direction(direction, method, menu, spans)
                for direction in block["answers"][label]["directions"]
            ]
            identity_span_id = block["answers"][label]["identity_evidence_span_id"]
            answers[label] = {
                "directions": directions,
                "identity_evidence": (
                    spans[identity_span_id]["text"] if identity_span_id is not None else None
                ),
                "identity_explicit": block["answers"][label]["identity_explicit"],
            }
            by_answer[label] = {direction["local_id"]: direction for direction in directions}
        comparisons = {}
        for pair in c.PAIRS:
            comparisons[pair] = {}
            for account in c.ACCOUNTS:
                verdict = block["comparisons"][pair][account]
                decisive = None
                if isinstance(verdict["decisive"], dict):
                    ref = verdict["decisive"]
                    direction = by_answer[ref["answer"]][ref["local_id"]]
                    decisive = {
                        "answer": ref["answer"],
                        "definition": direction["definition"],
                        "evidence": direction["evidence"],
                        "local_id": direction["local_id"],
                        "name": direction["name"],
                        "occurrence": direction["occurrence"],
                    }
                comparisons[pair][account] = {
                    "choice": verdict["choice"],
                    "decisive": decisive,
                    "reason": verdict["reason"],
                }
        blocks.append({
            "answers": answers,
            "block_id": block["block_id"],
            "comparisons": comparisons,
        })
    return {
        "blocks": blocks,
        "method": method,
        "question": doc["question"],
        "slot": doc["slot"],
    }


def verify_parent_reused_canonical() -> None:
    """逐单元从父版 prompt/raw/transport 复算 M1/M2 六份规范编码。"""
    blinded = c.load(SOURCE / "answers_blinded.json")
    for slot in c.CONFIG["analysis_v2"]["reused_slots"]:
        spec = c.CONFIG["coding_slots"][slot]
        transport_paths = sorted((PARENT_RUN / "effective" / "transport").glob(f"ENCODE_V3_{slot}_*.json"))
        if len(transport_paths) != 8:
            raise SystemExit(f"父版 {slot} transport 单元数不符")
        by_question: dict[str, list[dict]] = {question: [] for question in c.CONFIG["questions"]}
        for path in transport_paths:
            unit = path.stem
            doc = c.load(path)
            question = doc["question"]
            all_answers = legacy.blocks_for_question(blinded, question)
            answers = {
                block["block_id"]: all_answers[block["block_id"]]
                for block in doc["blocks"]
            }
            errors = validate_transport(doc, slot, question, answers)
            if errors:
                raise SystemExit(f"父版 {unit} transport 复验失败：{errors[:2]}")
            expanded = expand_transport(doc, answers)
            if validate_expanded(expanded, answers):
                raise SystemExit(f"父版 {unit} 展开后复验失败")
            by_question[question].extend(expanded["blocks"])

            prompt = PARENT_RUN / "prompts" / f"{unit}.txt"
            raw_path = PARENT_RUN / "raw" / unit / "attempt1.json"
            raw = c.load(raw_path)
            if not (
                raw.get("valid") is True
                and raw.get("unit_id") == unit
                and raw.get("provider") == spec["provider"]
                and raw.get("model") == spec["model"]
                and raw.get("prompt_sha256") == c.sha256(prompt)
                and raw.get("effective_sha256") == c.sha256(path)
                and (raw.get("raw") or {}).get("returncode") == 0
            ):
                raise SystemExit(f"父版 {unit} raw/prompt/transport 链不符")

        for question, blocks in by_question.items():
            canonical = {
                "blocks": sorted(blocks, key=lambda block: block["block_id"]),
                "method": spec["method"],
                "question": question,
                "slot": slot,
            }
            target = PARENT_RUN / "effective" / "coding" / f"{slot}_{question}.json"
            if c.canonical_json(canonical) != target.read_text(encoding="utf-8"):
                raise SystemExit(f"父版 {slot}/{question} 规范编码不能从 transport 复算")
            all_answers = legacy.blocks_for_question(blinded, question)
            errors = validate_expanded(canonical, all_answers)
            if errors:
                raise SystemExit(f"父版 {slot}/{question} 规范编码语义复验失败：{errors[:2]}")


def validate_expanded(doc: dict, answers: dict[str, dict[str, str]]) -> list[str]:
    errors = []
    try:
        jsonschema.validate(doc, c.load(CANONICAL_SCHEMAS[doc["method"]]))
        errors.extend(c.validate_coding(doc, doc["slot"], doc["question"], answers))
    except Exception as exc:
        errors.append(str(exc))
    return errors


def validate_calibration_gold(doc: dict, synthetic: dict) -> list[str]:
    errors = []
    by_block = {block["block_id"]: block for block in doc["blocks"]}
    for block_id, pairs in synthetic["expected_choices"].items():
        block = by_block[block_id]
        for pair, accounts in pairs.items():
            for account, expected in accounts.items():
                got = block["comparisons"][pair][account]["choice"]
                if got != expected:
                    errors.append(f"{block_id}/{pair}/{account} 金标准应为 {expected}，得到 {got}")
    for block_id, labels in synthetic["expected_identity"].items():
        for label, expected in labels.items():
            got = by_block[block_id]["answers"][label]["identity_explicit"]
            if got is not expected:
                errors.append(f"{block_id}/{label} identity 金标准不符")
    if doc["method"] == "menu":
        for block_id, labels in synthetic["menu_required"].items():
            for label, required in labels.items():
                got = {
                    direction["menu_id"]
                    for direction in by_block[block_id]["answers"][label]["directions"]
                    if direction["menu_id"] is not None
                }
                if not set(required).issubset(got):
                    errors.append(f"{block_id}/{label} 缺校准菜单方向：{sorted(set(required)-got)}")
    else:
        for block_id, labels in synthetic["open_minimum_tags"].items():
            for label, minimums in labels.items():
                counts = Counter(
                    direction["tag"]
                    for direction in by_block[block_id]["answers"][label]["directions"]
                )
                for tag, minimum in minimums.items():
                    if counts[tag] < minimum:
                        errors.append(f"{block_id}/{label} {tag} 方向少于 {minimum}")
    return errors


def require_prepared() -> None:
    c.verify_stage_manifest("sentinel")
    c.verify_stage_manifest("generation")
    verify_source_generation()
    attestation = c.load(RUN / "parent_reuse_attestation.json")
    for relative, expected in attestation.get("files", {}).items():
        path = RUN / relative
        if not path.is_file() or c.sha256(path) != expected:
            raise SystemExit(f"复用的 M1/M2 规范编码缺失或被修改：{relative}")


def run_calibration() -> None:
    c.verify_run_authorization()
    require_prepared()
    synthetic = c.load(HERE / "16_synthetic_calibration.json")
    answers = calibration_answers(synthetic)
    artifacts: list[Path] = []
    calibration_slots = c.CONFIG["analysis_v2"]["calibration_slots"]
    for slot in calibration_slots:
        spec = c.CONFIG["coding_slots"][slot]
        prompt = render_transport_prompt(
            slot, synthetic["question"], synthetic["question_text"], answers
        )
        output = EFFECTIVE / "calibration" / f"{slot}.json"

        def validate(doc: dict, slot: str = slot) -> list[str]:
            normalized = normalize_transport(doc, slot)
            errors = validate_transport(normalized, slot, synthetic["question"], answers)
            if not errors:
                expanded = expand_transport(normalized, answers)
                errors.extend(validate_expanded(expanded, answers))
                errors.extend(validate_calibration_gold(normalized, synthetic))
            return errors

        c.run_json_unit(
            unit_id=f"CAL_V32_{slot}",
            provider=spec["provider"],
            model=spec["model"],
            effort=spec["effort"],
            prompt=prompt,
            schema_path=transport_schema(slot),
            semantic_validate=validate,
            output_path=output,
            max_attempts=1,
        )
        artifacts.append(output)
    report = {
        "calls": len(calibration_slots),
        "criterion": "Codex M3 分表与 O3 开放运输须各自首试通过长文结构、语义、证据定位与金标准",
        "inherited_calibration_manifest_sha256": c.CONFIG["analysis_v2"]["parent_calibration_manifest_sha256"],
        "slots": calibration_slots,
        "status": "PASS",
    }
    c.dump(report, RUN / "03_calibration_report.json")
    c.write_stage_manifest(
        "calibration",
        artifacts
        + [
            RUN / "03_calibration_report.json",
            RUN / "manifest_generation.json",
        ]
        + legacy.request_artifacts([f"CAL_V32_{slot}" for slot in calibration_slots]),
    )
    print("[PASS] Codex M3 菜单分表与 O3 开放运输长合成校准")


def require_calibration_pass() -> None:
    c.verify_stage_manifest("calibration")
    report = c.load(RUN / "03_calibration_report.json")
    if report.get("status") != "PASS":
        raise SystemExit("编码器校准未通过")


def chunks_for_question(
    blinded: dict,
    question: str,
) -> list[dict[str, dict[str, str]]]:
    blocks = legacy.blocks_for_question(blinded, question)
    ordered = sorted(blocks)
    size = c.CONFIG["analysis_v2"]["chunk_size"]
    return [
        {block_id: blocks[block_id] for block_id in ordered[index:index + size]}
        for index in range(0, len(ordered), size)
    ]


def run_encode() -> None:
    c.verify_run_authorization()
    require_prepared()
    require_calibration_pass()
    blinded = c.load(RUN / "answers_blinded.json")
    called_units: list[str] = []
    transport_paths: list[Path] = []
    canonical_paths: list[Path] = sorted((EFFECTIVE / "coding").glob("M[12]_*.json"))
    if len(canonical_paths) != 6:
        raise SystemExit("缺父版复算并锁定的 M1/M2 六份规范编码")
    for slot in c.CONFIG["analysis_v2"]["encoding_slots"]:
        spec = c.CONFIG["coding_slots"][slot]
        for question in c.RANDOM_TABLE["encoding_question_order"][slot]:
            merged_blocks = []
            chunks = chunks_for_question(blinded, question)
            for chunk_index, answers in enumerate(chunks, 1):
                unit = f"ENCODE_V32_{slot}_{question}_C{chunk_index:02d}"
                prompt = render_transport_prompt(
                    slot,
                    question,
                    c.CONFIG["questions"][question]["text"],
                    answers,
                )
                output = EFFECTIVE / "transport" / f"{unit}.json"

                def validate(
                    doc: dict,
                    slot: str = slot,
                    question: str = question,
                    answers: dict = answers,
                ) -> list[str]:
                    normalized = normalize_transport(doc, slot)
                    errors = validate_transport(normalized, slot, question, answers)
                    if not errors:
                        errors.extend(validate_expanded(expand_transport(normalized, answers), answers))
                    return errors

                print(f"[ENCODE] {slot}/{question} chunk={chunk_index}/{len(chunks)}", flush=True)
                doc = c.run_json_unit(
                    unit_id=unit,
                    provider=spec["provider"],
                    model=spec["model"],
                    effort=spec["effort"],
                    prompt=prompt,
                    schema_path=transport_schema(slot),
                    semantic_validate=validate,
                    output_path=output,
                )
                normalized = normalize_transport(doc, slot)
                merged_blocks.extend(expand_transport(normalized, answers)["blocks"])
                called_units.append(unit)
                transport_paths.append(output)
            canonical = {
                "blocks": sorted(merged_blocks, key=lambda block: block["block_id"]),
                "method": spec["method"],
                "question": question,
                "slot": slot,
            }
            all_answers = legacy.blocks_for_question(blinded, question)
            errors = validate_expanded(canonical, all_answers)
            if errors:
                raise SystemExit(f"合并后主编码复验失败 {slot}/{question}：{errors[:3]}")
            path = EFFECTIVE / "coding" / f"{slot}_{question}.json"
            c.dump(canonical, path)
            canonical_paths.append(path)
    c.write_stage_manifest(
        "coding",
        transport_paths
        + canonical_paths
        + [
            RUN / "manifest_calibration.json",
            RUN / "manifest_generation.json",
            RUN / "parent_reuse_attestation.json",
            RUN / c.AUTH_FILENAME,
        ]
        + legacy.request_artifacts(called_units),
    )
    print("[PASS] 复用 16 个可复算盲化编码，新完成 32 个单元，合并为 18 份规范编码")


def run_review() -> None:
    require_calibration_pass()
    legacy.run_review()


def run_aggregate() -> None:
    require_calibration_pass()
    legacy.run_aggregate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=("prepare", "review", "aggregate"),
    )
    args = parser.parse_args()
    {
        "prepare": prepare_quota_resume_inputs,
        "review": run_review_v35,
        "aggregate": run_aggregate_v33,
    }[args.stage]()


if __name__ == "__main__":
    main()
