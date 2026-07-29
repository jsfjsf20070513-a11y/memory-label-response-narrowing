#!/usr/bin/env python3
"""Fail closed when the committed literature package is incomplete or unsafe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    seed = json.loads(
        (root / "literature/search/corpus_seed.json").read_text(encoding="utf-8")
    )
    records = json.loads(
        (root / "literature/metadata/papers.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (root / "literature/metadata/download_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    errors: list[str] = []
    if len(seed) != len(records) or len(records) != len(manifest):
        errors.append(
            f"count mismatch: seed={len(seed)}, records={len(records)}, "
            f"manifest={len(manifest)}"
        )

    seed_ids = [item.get("id") for item in seed]
    source_ids = [record.get("source_id") for record in records]
    manifest_ids = [item.get("source_id") for item in manifest]
    if len(seed_ids) != len(set(seed_ids)):
        errors.append("duplicate id in corpus_seed.json")
    if len(source_ids) != len(set(source_ids)):
        errors.append("duplicate source_id in papers.json")
    if len(manifest_ids) != len(set(manifest_ids)):
        errors.append("duplicate source_id in download_manifest.json")
    if set(seed_ids) != set(source_ids):
        errors.append("corpus_seed.json and papers.json source ID sets differ")
    if set(source_ids) != set(manifest_ids):
        errors.append("papers.json and download_manifest.json source ID sets differ")

    manifest_by_source_id = {
        item.get("source_id"): item for item in manifest
    }
    expected_paths: set[Path] = set()
    downloaded_items = 0
    for record in records:
        source_id = record.get("source_id")
        item = manifest_by_source_id.get(source_id)
        if item is None:
            errors.append(f"missing manifest item for {source_id}")
            continue

        allowed = record.get("redistribution_status") == "allowed"
        downloaded = item.get("download_status") == "downloaded"
        if allowed != downloaded:
            errors.append(
                f"download policy mismatch for {source_id}: "
                f"allowed={allowed}, downloaded={downloaded}"
            )

        local_path = item.get("local_pdf_path")
        if record.get("download_status") != item.get("download_status"):
            errors.append(f"papers/manifest status mismatch: {source_id}")
        if record.get("local_pdf_path") != local_path:
            errors.append(f"papers/manifest path mismatch: {source_id}")
        if not downloaded:
            if local_path:
                errors.append(f"skipped item has local path: {source_id}")
            continue
        if not local_path:
            errors.append(f"downloaded item lacks local path: {source_id}")
            continue
        downloaded_items += 1
        relative_path = Path(local_path)
        path = (root / relative_path).resolve()
        if (
            relative_path.is_absolute()
            or relative_path.parent != Path("literature/papers")
            or path.parent != (root / "literature/papers").resolve()
        ):
            errors.append(f"invalid local PDF path: {local_path}")
            continue
        expected_paths.add(path.resolve())
        if not path.is_file():
            errors.append(f"missing PDF: {local_path}")
            continue
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                errors.append(f"not a PDF binary: {local_path}")
        if path.stat().st_size != item.get("byte_size"):
            errors.append(f"size mismatch: {local_path}")
        if digest(path) != item.get("sha256"):
            errors.append(f"sha256 mismatch: {local_path}")
        if not record.get("license_evidence_url"):
            errors.append(f"downloaded PDF lacks license evidence: {source_id}")

    if downloaded_items != len(expected_paths):
        errors.append("duplicate local PDF path in download manifest")

    actual_paths = {
        path.resolve()
        for path in (root / "literature/papers").glob("*.pdf")
    }
    unexpected = actual_paths - expected_paths
    missing = expected_paths - actual_paths
    if unexpected:
        errors.append(
            "unexpected PDFs: "
            + ", ".join(str(path.relative_to(root)) for path in sorted(unexpected))
        )
    if missing:
        errors.append(
            "manifest PDFs missing from directory: "
            + ", ".join(str(path.relative_to(root)) for path in sorted(missing))
        )

    if errors:
        raise SystemExit("\n".join(f"ERROR: {error}" for error in errors))
    print(
        f"OK: {len(records)} records, {len(expected_paths)} licensed PDFs, "
        f"{len(records) - len(expected_paths)} link-only records"
    )


if __name__ == "__main__":
    main()
