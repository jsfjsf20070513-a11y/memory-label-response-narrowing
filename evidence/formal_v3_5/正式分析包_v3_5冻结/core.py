#!/usr/bin/env python3
"""正式实验共用的冻结算法、调用封装与语义校验。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import jsonschema


HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent / "正式分析运行_v3_5"
SOURCE_RUN_DIR = HERE.parent / "正式运行_v1_1"
AUTH_FILENAME = "00_open_analysis_v3_5.json"
AUTH_SCOPE = "formal_analysis_v3_5_quota_resume_up_to_23_calls"
CONFIG = json.loads((HERE / "01_config.json").read_text(encoding="utf-8"))
RANDOM_TABLE = json.loads((HERE / "04_random_table.json").read_text(encoding="utf-8"))
PAIRS = ("A_vs_B", "A_vs_C", "B_vs_C")
ACCOUNTS = ("math_focus", "nonmath_breadth")
LABELS = ("A", "B", "C")
TOOL_ITEM_TYPES = {
    "command_execution", "file_change", "mcp_tool_call", "web_search",
    "image_view", "collab_tool_call",
}


def stream_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def prompt_with_json_schema(prompt: str, schema_path: Path) -> str:
    """把程序实际使用的冻结 Schema 明文附到 JSON 任务末尾。"""
    schema_text = canonical_json(load(schema_path)).rstrip()
    return (
        prompt.rstrip()
        + "\n\n## 提供的输出 JSON Schema\n\n"
        + "以下内容只约束输出结构，不改变前文的判断规则。必须严格遵守；"
          "不要把 Schema 复制进答案。\n\n"
        + "```json\n"
        + schema_text
        + "\n```\n"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def native_output_schema(provider: str, schema_path: Path) -> dict:
    schema = load(schema_path)
    if provider == "claude":
        # Claude CLI 2.1.207 接受业务 Schema，但拒绝 2020-12 元声明 URI。
        schema = dict(schema)
        schema.pop("$schema", None)
    return schema


def native_output_schema_sha(provider: str, schema_path: Path) -> str:
    if provider == "codex":
        return sha256(schema_path)
    # Claude 参数是无尾换行的 JSON 字符串，哈希必须与实际 CLI 参数字节一致。
    return sha256_text(canonical_json(native_output_schema(provider, schema_path)).rstrip())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def live_cli_versions() -> dict[str, str]:
    values = {}
    for name, command in {
        "claude_cli_version": ["claude", "--version"],
        "codex_cli_version": ["codex", "--version"],
    }.items():
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0 or not proc.stdout.strip():
            raise SystemExit(f"无法复验运行时版本：{name}：{proc.stderr.strip()}")
        values[name] = proc.stdout.strip()
    return values


def verify_run_authorization() -> dict:
    auth_path = RUN_DIR / AUTH_FILENAME
    if not auth_path.exists():
        raise SystemExit("缺正式开跑登记，拒绝调用模型")
    auth = load(auth_path)
    required_text = ("user_instruction", "authorized_at", "claude_cli_version", "codex_cli_version")
    if auth.get("authorization_scope") != AUTH_SCOPE or any(
        not isinstance(auth.get(key), str) or not auth[key].strip() for key in required_text
    ):
        raise SystemExit("正式开跑登记不完整或范围不符")
    live_versions = live_cli_versions()
    if any(auth[key] != value for key, value in live_versions.items()):
        raise SystemExit(f"开跑登记的 CLI 版本与现场不符：{live_versions}")
    manifest = HERE / "SHA256SUMS.txt"
    if not manifest.exists():
        raise SystemExit("执行包未冻结：缺 SHA256SUMS.txt")
    if auth.get("package_manifest_sha256") != sha256(manifest):
        raise SystemExit("开跑登记与冻结包哈希不符")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"冻结包文件缺失或哈希不符：{relative}")
    return auth


def state() -> dict:
    raw_root = RUN_DIR / "raw"
    records = []
    if raw_root.exists():
        for path in raw_root.glob("*/attempt*.json"):
            try:
                records.append(load(path))
            except Exception as exc:
                raise SystemExit(f"原始请求记录损坏：{path}：{exc}")
    value = {
        "first_attempt_failed_units": sorted({
            row["unit_id"] for row in records
            if row.get("attempt") == 1 and not row.get("valid")
        }),
        "request_attempts": len(records),
    }
    dump(value, RUN_DIR / "01_run_state.json")
    return value


def enforce_request_limits(before_new_request: bool = False) -> dict:
    value = state()
    limit = CONFIG["thresholds"]["max_first_attempt_failures"]
    if len(value["first_attempt_failed_units"]) > limit:
        raise SystemExit(f"第一次失败的调用单元超过 {limit} 个，按预注册停止")
    request_limit = CONFIG["thresholds"]["max_requests_for_completed_run"]
    if value["request_attempts"] > request_limit or (
        before_new_request and value["request_attempts"] >= request_limit
    ):
        raise SystemExit(f"请求尝试超过预注册上限 {request_limit}")
    return value


def update_request_state(unit_id: str, attempt: int, valid: bool) -> None:
    enforce_request_limits()


def write_stage_manifest(name: str, paths: list[Path]) -> None:
    rows = {}
    for path in sorted(set(paths), key=str):
        if not path.is_file() or RUN_DIR not in path.parents:
            raise SystemExit(f"阶段清单输入非法：{path}")
        rows[str(path.relative_to(RUN_DIR))] = sha256(path)
    dump({"files": rows, "stage": name}, RUN_DIR / f"manifest_{name}.json")


def verify_stage_manifest(name: str) -> None:
    path = RUN_DIR / f"manifest_{name}.json"
    if not path.exists():
        raise SystemExit(f"缺阶段清单：{name}")
    doc = load(path)
    if doc.get("stage") != name:
        raise SystemExit(f"阶段清单名称不符：{name}")
    for relative, expected in doc.get("files", {}).items():
        target = RUN_DIR / relative
        if not target.is_file() or sha256(target) != expected:
            raise SystemExit(f"阶段产物缺失或被修改：{relative}")


def has_valid_raw(raw_dir: Path, prompt_sha: str, effective_sha: str,
                  provider: str, model: str, effort: str | None,
                  system_sha: str | None = None, json_mode: bool = False,
                  output_schema_sha: str | None = None) -> bool:
    for path in raw_dir.glob("attempt*.json"):
        row = load(path)
        try:
            text = recorded_text(row)
            raw_effective_sha = (
                sha256_text(canonical_json(parse_exact_json(text)))
                if json_mode else sha256_text(text)
            )
        except (SystemExit, Exception):
            raw_effective_sha = None
        if (
            valid_record_matches(
                row, prompt_sha, provider, model, effort, system_sha, output_schema_sha
            )
            and row.get("effective_sha256") == effective_sha
            and raw_effective_sha == effective_sha
        ):
            return True
    return False


def valid_record_matches(row: dict, prompt_sha: str, provider: str, model: str,
                         effort: str | None, system_sha: str | None = None,
                         output_schema_sha: str | None = None) -> bool:
    expected_effort = effort if effort is not None else "default_unset"
    shape = (row.get("raw") or {}).get("command_shape") or {}
    return bool(
        row.get("valid")
        and row.get("prompt_sha256") == prompt_sha
        and row.get("provider") == provider
        and row.get("model") == model
        and shape.get("provider") == provider
        and shape.get("model") == model
        and shape.get("effort") == expected_effort
        and (system_sha is None or shape.get("system_prompt_sha256") == system_sha)
        and (
            output_schema_sha is None
            or shape.get("output_schema_sha256") == output_schema_sha
        )
    )


def recorded_text(row: dict) -> str:
    raw = row.get("raw") or {}
    if row.get("provider") == "claude":
        parsed = raw.get("parsed") or {}
        shape = raw.get("command_shape") or {}
        if shape.get("output_schema_sha256"):
            structured = parsed.get("structured_output")
            value = canonical_json(structured) if isinstance(structured, dict) else None
        else:
            value = parsed.get("result")
    elif row.get("provider") == "codex":
        messages = [
            (event.get("item") or {}).get("text", "")
            for event in raw.get("events", [])
            if (event.get("item") or {}).get("type") == "agent_message"
        ]
        value = messages[-1] if messages else None
    else:
        value = None
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("标记有效的原始返回无法重建正文")
    return value


def matching_valid_record(raw_dir: Path, prompt_sha: str, provider: str,
                          model: str, effort: str | None,
                          system_sha: str | None,
                          output_schema_sha: str | None = None) -> dict | None:
    for path in sorted(raw_dir.glob("attempt*.json")):
        row = load(path)
        if not row.get("valid"):
            continue
        if not valid_record_matches(
            row, prompt_sha, provider, model, effort, system_sha, output_schema_sha
        ):
            raise SystemExit(f"有效原始返回与当前调用单元不匹配：{path}")
        return row
    return None


def parse_exact_json(text: str) -> Any:
    return json.loads(text.strip())


def call_claude(
    prompt: str,
    model: str,
    effort: str | None,
    system: str = "",
    output_schema_path: Path | None = None,
) -> dict:
    cmd = [
        "claude", "--safe-mode", "--no-session-persistence", "--tools", "",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--system-prompt", system, "--model", model,
    ]
    if effort is not None:
        cmd.extend(["--effort", effort])
    output_schema_sha = (
        native_output_schema_sha("claude", output_schema_path)
        if output_schema_path is not None else None
    )
    if output_schema_path is not None:
        cmd.extend([
            "--json-schema",
            canonical_json(native_output_schema("claude", output_schema_path)).rstrip(),
        ])
    cmd.extend(["-p", prompt, "--output-format", "json"])
    command_shape = {
        "provider": "claude", "model": model,
        "effort": effort if effort is not None else "default_unset",
        "system_prompt_sha256": sha256_text(system),
        "output_schema_sha256": output_schema_sha,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="formal-claude-") as cwd:
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False, "error": "Claude CLI 900 秒超时",
            "raw": {
                "command_shape": command_shape, "returncode": None,
                "stderr": stream_text(exc.stderr), "stdout": stream_text(exc.stdout),
                "timed_out": True,
            },
        }
    envelope: dict[str, Any] = {
        "command_shape": {
            **command_shape,
        },
        "returncode": proc.returncode,
        "stderr": proc.stderr,
        "stdout": proc.stdout,
    }
    if proc.returncode != 0:
        return {"ok": False, "error": f"Claude CLI 退出码 {proc.returncode}", "raw": envelope}
    try:
        raw = json.loads(proc.stdout)
    except Exception as exc:
        return {"ok": False, "error": f"Claude 外层 JSON 解析失败：{exc}", "raw": envelope}
    envelope["parsed"] = raw
    text = raw.get("result", "")
    if raw.get("is_error") or not isinstance(text, str) or not text.strip():
        return {"ok": False, "error": "Claude 返回状态或正文不合格", "raw": envelope}
    if raw.get("permission_denials"):
        return {"ok": False, "error": "Claude 出现工具或权限请求", "raw": envelope}
    if model not in (raw.get("modelUsage") or {}):
        return {"ok": False, "error": f"Claude 回执未登记指定模型 {model}", "raw": envelope}
    if output_schema_path is not None:
        structured = raw.get("structured_output")
        if not isinstance(structured, dict):
            return {"ok": False, "error": "Claude 缺原生 structured_output", "raw": envelope}
        try:
            result_doc = parse_exact_json(text)
        except Exception as exc:
            return {"ok": False, "error": f"Claude result 不是同一份 JSON：{exc}", "raw": envelope}
        if result_doc != structured:
            return {"ok": False, "error": "Claude result 与 structured_output 不一致", "raw": envelope}
        # 原生结构化输出会额外经历 Schema 工具回合，不能沿用普通文本的单轮约束。
        return {"ok": True, "text": canonical_json(structured), "raw": envelope}
    if raw.get("num_turns") != 1:
        return {"ok": False, "error": "Claude 普通文本调用不是单轮返回", "raw": envelope}
    return {"ok": True, "text": text, "raw": envelope}


def call_codex(
    prompt: str,
    model: str,
    effort: str,
    output_schema_path: Path | None = None,
) -> dict:
    cmd = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--skip-git-repo-check", "--sandbox", "read-only", "--model", model,
        "-c", f'model_reasoning_effort="{effort}"', "--json", "-",
    ]
    output_schema_sha = (
        native_output_schema_sha("codex", output_schema_path)
        if output_schema_path is not None else None
    )
    if output_schema_path is not None:
        json_index = cmd.index("--json")
        cmd[json_index:json_index] = ["--output-schema", str(output_schema_path.resolve())]
    command_shape = {
        "provider": "codex",
        "model": model,
        "effort": effort,
        "output_schema_sha256": output_schema_sha,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="formal-codex-") as cwd:
            proc = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True,
                                  text=True, timeout=900)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False, "error": "Codex CLI 900 秒超时",
            "raw": {
                "command_shape": command_shape, "returncode": None,
                "stderr": stream_text(exc.stderr), "stdout": stream_text(exc.stdout),
                "timed_out": True,
            },
        }
    envelope: dict[str, Any] = {
        "command_shape": command_shape,
        "returncode": proc.returncode,
        "stderr": proc.stderr,
        "stdout": proc.stdout,
    }
    if proc.returncode != 0:
        return {"ok": False, "error": f"Codex CLI 退出码 {proc.returncode}", "raw": envelope}
    events, messages, tools = [], [], []
    try:
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            events.append(event)
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            if item.get("type") in TOOL_ITEM_TYPES:
                tools.append(item.get("type"))
    except Exception as exc:
        return {"ok": False, "error": f"Codex JSONL 解析失败：{exc}", "raw": envelope}
    envelope["events"] = events
    envelope["tool_events"] = tools
    if tools:
        return {"ok": False, "error": f"Codex 出现工具调用：{tools}", "raw": envelope}
    if not messages or not messages[-1].strip():
        return {"ok": False, "error": "Codex 没有最终正文", "raw": envelope}
    return {"ok": True, "text": messages[-1], "raw": envelope}


def provider_call(provider: str, prompt: str, model: str, effort: str | None,
                  system: str = "", output_schema_path: Path | None = None) -> dict:
    if provider == "claude":
        return call_claude(prompt, model, effort, system, output_schema_path)
    if provider == "codex":
        assert effort is not None
        return call_codex(prompt, model, effort, output_schema_path)
    raise ValueError(f"未知 provider：{provider}")


def pending_attempt_record(unit_id: str, attempt: int, provider: str, model: str,
                           effort: str | None, prompt_sha: str, system: str,
                           output_schema_sha: str | None = None) -> dict:
    shape = {
        "provider": provider, "model": model,
        "effort": effort if effort is not None else "default_unset",
    }
    if provider == "claude":
        shape["system_prompt_sha256"] = sha256_text(system)
    if output_schema_sha is not None:
        shape["output_schema_sha256"] = output_schema_sha
    return {
        "attempt": attempt,
        "effective_sha256": None,
        "errors": ["请求已登记，尚无完成回执；按一次尝试保守计数"],
        "model": model,
        "prompt_sha256": prompt_sha,
        "provider": provider,
        "raw": {"command_shape": shape, "in_flight": True},
        "request_registered_at_utc": utc_now(),
        "response_recorded_at_utc": None,
        "unit_id": unit_id,
        "valid": False,
    }


def run_json_unit(
    unit_id: str,
    provider: str,
    model: str,
    effort: str | None,
    prompt: str,
    schema_path: Path,
    semantic_validate: Callable[[dict], list[str]],
    output_path: Path,
    system: str = "",
    max_attempts: int = 2,
) -> dict:
    verify_run_authorization()
    prompt = prompt_with_json_schema(prompt, schema_path)
    prompt_path = RUN_DIR / "prompts" / f"{unit_id}.txt"
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8") != prompt:
        raise SystemExit(f"{unit_id} 提示词与既存版本不一致")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    raw_dir = RUN_DIR / "raw" / unit_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    enforce_request_limits()
    schema = load(schema_path)
    prompt_sha = sha256_text(prompt)
    system_sha = sha256_text(system) if provider == "claude" else None
    output_schema_sha = native_output_schema_sha(provider, schema_path)
    if output_path.exists():
        doc = load(output_path)
        errors = []
        try:
            jsonschema.validate(doc, schema)
            errors.extend(semantic_validate(doc))
        except Exception as exc:
            errors.append(str(exc))
        if errors or not has_valid_raw(
            raw_dir, prompt_sha, sha256(output_path), provider, model, effort, system_sha,
            json_mode=True, output_schema_sha=output_schema_sha,
        ):
            raise SystemExit(f"{unit_id} 既有有效文件无法复验：{errors}")
        return doc
    recovered = matching_valid_record(
        raw_dir, prompt_sha, provider, model, effort, system_sha, output_schema_sha
    )
    if recovered is not None:
        try:
            doc = parse_exact_json(recorded_text(recovered))
            jsonschema.validate(doc, schema)
            errors = semantic_validate(doc)
        except Exception as exc:
            raise SystemExit(f"{unit_id} 原始有效包重建失败：{exc}") from exc
        if errors or recovered.get("effective_sha256") != sha256_text(canonical_json(doc)):
            raise SystemExit(f"{unit_id} 原始有效包重建校验失败：{errors}")
        dump(doc, output_path)
        state()
        return doc
    existing = sorted(raw_dir.glob("attempt*.json"))
    start = len(existing) + 1
    if max_attempts not in (1, 2):
        raise ValueError("max_attempts 只允许 1 或 2")
    if start > max_attempts:
        raise SystemExit(f"{unit_id} 已用完 {max_attempts} 次尝试")
    for attempt in range(start, max_attempts + 1):
        enforce_request_limits(before_new_request=True)
        attempt_path = raw_dir / f"attempt{attempt}.json"
        pending = pending_attempt_record(
            unit_id, attempt, provider, model, effort, prompt_sha, system,
            output_schema_sha,
        )
        dump(pending, attempt_path)
        response = provider_call(
            provider, prompt, model, effort, system,
            schema_path,
        )
        errors: list[str] = []
        doc = None
        if not response["ok"]:
            errors.append(response["error"])
        else:
            try:
                doc = parse_exact_json(response["text"])
                jsonschema.validate(doc, schema)
                errors.extend(semantic_validate(doc))
            except Exception as exc:
                errors.append(str(exc))
        valid = not errors
        record = {
            "attempt": attempt,
            "effective_sha256": sha256_text(canonical_json(doc)) if valid else None,
            "errors": errors,
            "model": model,
            "provider": provider,
            "prompt_sha256": prompt_sha,
            "raw": response["raw"],
            "request_registered_at_utc": pending["request_registered_at_utc"],
            "response_recorded_at_utc": utc_now(),
            "unit_id": unit_id,
            "valid": valid,
        }
        dump(record, attempt_path)
        update_request_state(unit_id, attempt, valid)
        if valid:
            dump(doc, output_path)
            return doc
        if attempt < max_attempts:
            continue
        raise SystemExit(f"{unit_id} {max_attempts} 次均失败：{errors[:3]}")
    raise AssertionError("unreachable")


def run_text_unit(
    unit_id: str,
    provider: str,
    model: str,
    effort: str | None,
    prompt: str,
    output_path: Path,
    system: str = "",
) -> str:
    verify_run_authorization()
    prompt_path = RUN_DIR / "prompts" / f"{unit_id}.txt"
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8") != prompt:
        raise SystemExit(f"{unit_id} 提示词与既存版本不一致")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    raw_dir = RUN_DIR / "raw" / unit_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    enforce_request_limits()
    prompt_sha = sha256_text(prompt)
    system_sha = sha256_text(system) if provider == "claude" else None
    if output_path.exists():
        text = output_path.read_text(encoding="utf-8")
        if not text.strip() or not has_valid_raw(
            raw_dir, prompt_sha, sha256(output_path), provider, model, effort, system_sha,
            json_mode=False,
        ):
            raise SystemExit(f"{unit_id} 既有回答无法由有效原始包复验")
        return text
    recovered = matching_valid_record(
        raw_dir, prompt_sha, provider, model, effort, system_sha
    )
    if recovered is not None:
        text = recorded_text(recovered)
        if recovered.get("effective_sha256") != sha256_text(text):
            raise SystemExit(f"{unit_id} 原始有效回答哈希不符")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        state()
        return text
    existing = sorted(raw_dir.glob("attempt*.json"))
    start = len(existing) + 1
    if start > 2:
        raise SystemExit(f"{unit_id} 已用完两次尝试")
    for attempt in range(start, 3):
        enforce_request_limits(before_new_request=True)
        attempt_path = raw_dir / f"attempt{attempt}.json"
        pending = pending_attempt_record(
            unit_id, attempt, provider, model, effort, prompt_sha, system
        )
        dump(pending, attempt_path)
        response = provider_call(provider, prompt, model, effort, system)
        valid = bool(response["ok"] and response.get("text", "").strip())
        errors = [] if valid else [response.get("error", "空回答")]
        dump({
            "attempt": attempt, "effective_sha256": sha256_text(response.get("text", "")) if valid else None,
            "errors": errors, "model": model,
            "provider": provider, "prompt_sha256": prompt_sha,
            "raw": response["raw"],
            "request_registered_at_utc": pending["request_registered_at_utc"],
            "response_recorded_at_utc": utc_now(),
            "unit_id": unit_id, "valid": valid,
        }, attempt_path)
        update_request_state(unit_id, attempt, valid)
        if valid:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(response["text"], encoding="utf-8")
            return response["text"]
        if attempt == 1:
            continue
        raise SystemExit(f"{unit_id} 两次运输失败：{errors}")
    raise AssertionError("unreachable")


def remove_emphasis(text: str) -> str:
    return remove_emphasis_with_map(text)[0]


def remove_emphasis_with_map(text: str) -> tuple[str, list[int]]:
    removed = set()
    for marker in ("**", "__"):
        positions, start = [], 0
        while True:
            pos = text.find(marker, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + len(marker)
        if len(positions) % 2 == 0:
            for pos in positions:
                removed.update((pos, pos + 1))
    chars, original_indexes = [], []
    index = 0
    while index < len(text):
        if index in removed:
            index += 1
            continue
        chars.append(text[index])
        original_indexes.append(index)
        index += 1
    return "".join(chars), original_indexes


def nth_find(text: str, needle: str, occurrence: int) -> int | None:
    start = 0
    found = -1
    for _ in range(occurrence):
        found = text.find(needle, start)
        if found < 0:
            return None
        start = found + len(needle)
    return found


def locate_evidence(text: str, evidence: str, occurrence: int) -> dict | None:
    pos = nth_find(text, evidence, occurrence)
    if pos is not None:
        return {
            "mode": "exact",
            "normalized_end": pos + len(evidence), "normalized_start": pos,
            "original_end": pos + len(evidence), "original_start": pos,
            "trigger_reason": "原始连续字符串精确匹配",
        }
    clean_text, original_indexes = remove_emphasis_with_map(text)
    clean_evidence = remove_emphasis(evidence)
    if not clean_evidence:
        return None
    pos = nth_find(clean_text, clean_evidence, occurrence)
    if pos is not None:
        original_start = original_indexes[pos]
        original_end = original_indexes[pos + len(clean_evidence) - 1] + 1
        return {
            "mode": "remove_markdown_emphasis",
            "normalized_end": pos + len(clean_evidence), "normalized_start": pos,
            "original_end": original_end, "original_start": original_start,
            "trigger_reason": "原始匹配失败；仅移除成对 Markdown 强调标记后匹配",
        }
    return None


def menu_definitions() -> dict[str, tuple[str, str]]:
    values = {}
    pattern = re.compile(r"^- `(S(?:2|8|10)-D\d+) ([^`]*)`——(.+)$")
    for line in (HERE / "03_menu_excerpt.md").read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = (
                match.group(2).strip(), match.group(3).strip().rstrip("⚠").strip()
            )
    return values


def pair_labels(pair: str) -> tuple[str, str]:
    left, right = pair.split("_vs_")
    return left, right


def validate_coding(doc: dict, slot: str, question: str, answers: dict) -> list[str]:
    errors: list[str] = []
    method = CONFIG["coding_slots"][slot]["method"]
    if doc.get("slot") != slot or doc.get("method") != method or doc.get("question") != question:
        errors.append("slot/method/question 与调用单元不符")
    expected_blocks = sorted(answers)
    got_blocks = [block.get("block_id") for block in doc.get("blocks", [])]
    if sorted(got_blocks) != expected_blocks or len(got_blocks) != len(set(got_blocks)):
        errors.append(f"块集合不符：expected={expected_blocks}, got={got_blocks}")
        return errors
    menu = menu_definitions()
    prefix = question
    for block in doc["blocks"]:
        block_id = block["block_id"]
        decisive_refs = {
            (verdict["choice"], verdict["decisive"]["local_id"])
            for pair in PAIRS for account in ACCOUNTS
            for verdict in [block["comparisons"][pair][account]]
            if verdict["choice"] in LABELS and isinstance(verdict.get("decisive"), dict)
        }
        for label in LABELS:
            text = answers[block_id][label]
            coded = block["answers"][label]
            ids = [direction["local_id"] for direction in coded["directions"]]
            if len(ids) != len(set(ids)):
                errors.append(f"{block_id}/{label} local_id 重复")
            if method == "open" and ids != [f"d{i}" for i in range(1, len(ids) + 1)]:
                errors.append(f"{block_id}/{label} 开放方向必须从 d1 连续编号")
            menu_ids = [
                direction["menu_id"] for direction in coded["directions"]
                if method == "menu" and direction["from_menu"]
            ]
            if len(menu_ids) != len(set(menu_ids)):
                errors.append(f"{block_id}/{label} 同一菜单方向重复登记")
            by_id = {direction["local_id"]: direction for direction in coded["directions"]}
            for direction in coded["directions"]:
                if (
                    locate_evidence(text, direction["evidence"], direction["occurrence"]) is None
                    and (label, direction["local_id"]) not in decisive_refs
                ):
                    errors.append(f"{block_id}/{label}/{direction['local_id']} 证据无法定位")
                if method == "menu":
                    if direction["from_menu"]:
                        mid = direction["menu_id"]
                        if not isinstance(mid, str) or not mid.startswith(prefix + "-") or mid not in menu:
                            errors.append(f"{block_id}/{label} 菜单编号不属于当前题：{mid}")
                        elif direction["name"] != menu[mid][0] or direction["definition"].strip().rstrip("⚠").strip() != menu[mid][1]:
                            errors.append(f"{block_id}/{label}/{mid} 名称或定义未逐字继承冻结菜单")
                    elif direction["menu_id"] is not None:
                        errors.append(f"{block_id}/{label} 菜单外方向 menu_id 必须为 null")
            if coded["identity_explicit"]:
                evidence = coded["identity_evidence"]
                if not evidence or locate_evidence(text, evidence, 1) is None:
                    errors.append(f"{block_id}/{label} 身份显形证据无法定位")
            elif coded["identity_evidence"] is not None:
                errors.append(f"{block_id}/{label} identity=false 时证据必须为 null")

        for pair in PAIRS:
            allowed = set(pair_labels(pair))
            for account in ACCOUNTS:
                verdict = block["comparisons"][pair][account]
                choice = verdict["choice"]
                if choice in LABELS and choice not in allowed:
                    errors.append(f"{block_id}/{pair}/{account} 选择了对子外标签 {choice}")
                decisive = verdict["decisive"]
                if choice in LABELS:
                    if decisive["answer"] != choice:
                        errors.append(f"{block_id}/{pair}/{account} decisive.answer 不等于胜方")
                    source = block["answers"][choice]["directions"]
                    matches = [d for d in source if d["local_id"] == decisive["local_id"]]
                    if len(matches) != 1:
                        errors.append(f"{block_id}/{pair}/{account} decisive 未引用唯一已登记方向")
                    else:
                        d = matches[0]
                        fields = ("name", "definition", "evidence", "occurrence")
                        if any(decisive[field] != d[field] for field in fields):
                            errors.append(f"{block_id}/{pair}/{account} decisive 未逐字复制方向")
                        required_tag = "数学" if account == "math_focus" else "非数学"
                        if d["tag"] != required_tag:
                            errors.append(
                                f"{block_id}/{pair}/{account} decisive 方向标签必须为 {required_tag}"
                            )
                elif decisive is not None:
                    errors.append(f"{block_id}/{pair}/{account} 非方向票 decisive 必须为 null")
    return errors


def exact_sign_p(n: int, k: int) -> float:
    if not 0 <= k <= n:
        raise ValueError("k 必须位于 0..n")
    return sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)


def group_vote(votes: dict[str, str]) -> dict:
    if len(votes) != 3:
        raise ValueError("组票必须恰有三个槽位")
    counts = Counter(votes.values())
    minority_flag = len(counts) > 1
    if counts["无法判断"] >= 2:
        return {
            "minority_flag": minority_flag, "status": "measurement_failure",
            "result": "无法判断", "votes": votes,
        }
    for value, count in counts.most_common():
        if count < 2:
            break
        if value == "相当":
            return {
                "minority_flag": minority_flag, "status": "equal",
                "result": value, "votes": votes,
            }
        if value in LABELS:
            agreeing = {slot for slot, choice in votes.items() if choice == value}
            has_codex = any(slot.endswith("3") for slot in agreeing)
            has_claude = any(not slot.endswith("3") for slot in agreeing)
            if has_codex and has_claude:
                return {
                    "minority_flag": minority_flag, "status": "direction",
                    "result": value, "votes": votes,
                }
            return {
                "minority_flag": True, "status": "family_split",
                "result": None, "votes": votes,
            }
    return {
        "minority_flag": True, "status": "no_majority",
        "result": None, "votes": votes,
    }


def method_score(math_result: str | None, nonmath_result: str | None,
                 focal: str, reference: str) -> int:
    if math_result == focal and nonmath_result == reference:
        return 1
    if math_result == reference and nonmath_result == focal:
        return -1
    return 0


def fixed_sequence(primary_pass: bool, secondary_pass: bool) -> dict:
    return {
        "secondary_inferentially_tested": primary_pass,
        "specificity_supported": primary_pass and secondary_pass,
    }


def length_entanglement_alarm(m_median: float, n_median: float,
                              m_nonmath_less: int, m_nonmath_more: int,
                              shorter_fraction: float) -> bool:
    return (
        m_median < (1 - shorter_fraction) * n_median
        and m_nonmath_less > m_nonmath_more
    )


def blind_pair(mapping: dict[str, str], arm1: str, arm2: str) -> tuple[str, str, str]:
    inverse = {arm: label for label, arm in mapping.items()}
    left, right = inverse[arm1], inverse[arm2]
    pair = f"{min(left, right)}_vs_{max(left, right)}"
    return pair, left, right


def review_order_key(slot: str, task_id: str) -> str:
    seed = RANDOM_TABLE["seed"]
    return sha256_text(f"{seed}|{slot}|{task_id}")
