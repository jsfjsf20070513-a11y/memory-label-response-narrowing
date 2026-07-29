#!/usr/bin/env python3
"""Normalize downloaded paper names and make the manifest portable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")


def target_name(record: dict[str, Any]) -> str:
    platforms = record.get("source_platforms") or []
    source_id = record.get("source_id") or record.get("arxiv_id") or "paper"
    if "acl_anthology" in platforms:
        return f"acl-{safe_name(source_id)}.pdf"
    if "pubmed_central" in platforms:
        return f"pmc-{safe_name(record.get('pmcid') or source_id)}.pdf"
    if "arxiv" in platforms:
        version = record.get("source_version") or ""
        return f"arxiv-{safe_name(source_id + version)}.pdf"
    if "pmlr" in platforms:
        return f"pmlr-{safe_name(source_id.replace('/', '-'))}.pdf"
    if "crossref" in platforms:
        return f"journal-{safe_name(source_id)}.pdf"
    return f"paper-{safe_name(source_id)}.pdf"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--papers-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    records = json.loads(args.papers.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records_by_identity = {
        (
            record.get("doi"),
            record.get("arxiv_id"),
            record.get("title"),
        ): record
        for record in records
    }

    for item in manifest:
        identity = (item.get("doi"), item.get("arxiv_id"), item.get("title"))
        record = records_by_identity.get(identity)
        if record is None:
            raise RuntimeError(f"manifest record not found in papers.json: {identity}")

        item["source_id"] = record.get("source_id")
        item["source_version"] = record.get("source_version")
        item["landing_url"] = record.get("landing_url")
        item["license"] = record.get("license")
        item["license_evidence_url"] = record.get("license_evidence_url")
        item["redistribution_status"] = record.get("redistribution_status")
        item["redistribution_note"] = record.get("redistribution_note")

        if item.get("download_status") != "downloaded":
            item["local_pdf_path"] = None
            item["sha256"] = None
            item["byte_size"] = None
            record["download_status"] = item.get("download_status")
            record["download_error"] = item.get("download_error")
            record["local_pdf_path"] = None
            continue

        old_path = Path(item["local_pdf_path"])
        if not old_path.is_absolute():
            old_path = args.repo_root / old_path
        new_path = args.papers_dir / target_name(record)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.resolve() != new_path.resolve():
            old_path.replace(new_path)
        relative_path = new_path.resolve().relative_to(args.repo_root.resolve())
        item["filename"] = new_path.name
        item["local_pdf_path"] = relative_path.as_posix()
        item["sha256"] = sha256(new_path)
        item["byte_size"] = new_path.stat().st_size
        record["download_status"] = "downloaded"
        record["download_error"] = None
        record["local_pdf_path"] = relative_path.as_posix()
        record["download_source"] = item.get("download_source")

    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.papers.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
