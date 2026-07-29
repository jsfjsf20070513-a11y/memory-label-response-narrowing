#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
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
    # 红线审计 2026-07-29 扩充(对抗测试曾证明旧版对下列内容全部 PASS):
    "student_id_email": re.compile(rb"\b[0-9]{8,13}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "personal_email": re.compile(
        rb"\b[A-Za-z0-9._%+-]+@(?:gmail|qq|163|126|outlook|hotmail|foxmail)\.(?:com|cn)\b"
    ),
    "cn_mobile": re.compile(rb"\b1[3-9][0-9]{9}\b"),
    "wechat_export_marker": re.compile(("微信聊天" "导出|聊天记录" "导出").encode("utf-8"))  # 拆写避免自匹配,
}
# 文件名级标记:聊天导出与逐判官表格类文件不得入库,无论内容
FORBIDDEN_FILENAME_PATTERNS = ("聊天" "导出", "chat.txt")  # 拆写避免自匹配
FORBIDDEN_EXTRA_SUFFIXES = {".tsv", ".7z"}

# 提交元数据(红线审计 2026-07-29):git 历史的作者/提交者身份也可能泄露 PII。
# 规则:HEAD 的作者与提交者邮箱必须是化名(allowlist 后缀),否则 FAIL——止住增量;
# 历史中已存在的非化名邮箱只 WARN 计数(存量处理走脱敏镜像策略,见披露登记 E4)。
PSEUDONYM_EMAIL_SUFFIXES = ("users.noreply.github.com", "test.invalid")
LITERATURE_MANIFEST = ROOT / "literature/metadata/download_manifest.json"
REDISTRIBUTABLE_PDF_LICENSES = {
    "CC-BY-3.0",
    "CC-BY-4.0",
    "CC-BY-NC-ND-4.0",
    "CC-BY-NC-SA-4.0",
}


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def licensed_literature_pdfs(failures: list[str]) -> set[Path]:
    """Return a fail-closed allowlist for licensed, manifest-pinned PDFs."""
    if not LITERATURE_MANIFEST.exists():
        return set()
    try:
        manifest = json.loads(LITERATURE_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"literature manifest cannot be parsed: {exc}")
        return set()
    if not isinstance(manifest, list):
        failures.append("literature manifest must be a JSON list")
        return set()

    allowed: set[Path] = set()
    for item in manifest:
        if item.get("download_status") != "downloaded":
            continue
        local_path = item.get("local_pdf_path")
        if not isinstance(local_path, str):
            failures.append("downloaded literature item lacks local_pdf_path")
            continue
        relative = Path(local_path)
        path = (ROOT / relative).resolve()
        if (
            relative.is_absolute()
            or relative.parent != Path("literature/papers")
            or relative.suffix.lower() != ".pdf"
            or path.parent != (ROOT / "literature/papers").resolve()
        ):
            failures.append(f"invalid literature PDF path in manifest: {local_path}")
            continue
        if item.get("redistribution_status") != "allowed":
            failures.append(f"literature PDF is not marked redistributable: {local_path}")
            continue
        if item.get("license") not in REDISTRIBUTABLE_PDF_LICENSES:
            failures.append(f"literature PDF has unapproved license: {local_path}")
            continue
        if not item.get("license_evidence_url"):
            failures.append(f"literature PDF lacks license evidence: {local_path}")
            continue
        if not path.is_file():
            failures.append(f"manifest-listed literature PDF is missing: {local_path}")
            continue
        if path.stat().st_size != item.get("byte_size"):
            failures.append(f"literature PDF size mismatch: {local_path}")
            continue
        if file_sha256(path) != item.get("sha256"):
            failures.append(f"literature PDF hash mismatch: {local_path}")
            continue
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                failures.append(f"manifest-listed file is not a PDF: {local_path}")
                continue
        if path in allowed:
            failures.append(f"duplicate literature PDF path in manifest: {local_path}")
            continue
        allowed.add(path)
    return allowed


def check_git_identity(failures: list) -> None:
    import subprocess
    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%ae%n%ce"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except Exception as exc:
        failures.append(f"git identity check failed closed: {exc}")
        return
    for email in head:
        if not email.endswith(PSEUDONYM_EMAIL_SUFFIXES):
            failures.append(
                "HEAD commit author/committer email is not pseudonymous; "
                "set repo-local git config user.email to a noreply address"
            )
            break
    try:
        history = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--all", "--format=%ae%n%ce"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except Exception:
        return
    legacy = sum(1 for e in set(history) if not e.endswith(PSEUDONYM_EMAIL_SUFFIXES))
    if legacy:
        print(
            f"[WARN] git history contains {legacy} non-pseudonymous identity value(s); "
            "covered by mirror strategy (disclosure ledger E4), fix before any publication"
        )


def iter_files():
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        yield path


def main() -> None:
    failures: list[str] = []
    literature_pdf_allowlist = licensed_literature_pdfs(failures)
    for path in iter_files():
        relative = path.relative_to(ROOT)
        is_licensed_literature_pdf = path.resolve() in literature_pdf_allowlist
        if (
            path.suffix.lower() in FORBIDDEN_SUFFIXES | FORBIDDEN_EXTRA_SUFFIXES
            and not is_licensed_literature_pdf
        ):
            failures.append(f"forbidden suffix: {relative}")
        if any(marker in path.name for marker in FORBIDDEN_FILENAME_PATTERNS):
            failures.append(f"forbidden chat-export filename: {relative}")
        if FORBIDDEN_PARTS.intersection(relative.parts):
            failures.append(f"forbidden directory: {relative}")
        if any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS):
            failures.append(f"forbidden private filename: {relative}")
        if path.stat().st_size > 20 * 1024 * 1024 and not is_licensed_literature_pdf:
            failures.append(f"file larger than 20 MiB: {relative}")
        # PDF binary streams can coincidentally match PII byte patterns. Only
        # manifest-pinned, licensed, hash-verified PDFs bypass content scanning.
        if is_licensed_literature_pdf:
            continue
        data = path.read_bytes()
        for label, pattern in CONTENT_PATTERNS.items():
            if pattern.search(data):
                failures.append(f"{label}: {relative}")
    check_git_identity(failures)
    if failures:
        raise SystemExit("[FAIL] repository privacy boundary\n" + "\n".join(sorted(set(failures))))
    print("[PASS] repository privacy boundary")


if __name__ == "__main__":
    main()
