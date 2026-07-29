#!/usr/bin/env python3
"""Download the license-approved PDFs listed in the generated manifest.

The academic-search downloader is used first to build the policy-aware
manifest. This fallback downloader exists because Node's built-in fetch can
stall indefinitely on some scholarly hosts. It preserves the same fail-closed
semantics while adding per-request timeouts, retries, atomic writes and bounded
parallelism.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path
from typing import Any


USER_AGENT = "memory-label-response-narrowing-literature-download/1.0"


def probe_pdf(url: str) -> tuple[int | None, bool]:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--head",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "40",
            "--user-agent",
            USER_AGENT,
            url,
        ],
        check=True,
        capture_output=True,
        timeout=50,
        text=True,
    )
    lengths = re.findall(
        r"(?im)^content-length:\s*(\d+)\s*$", result.stdout
    )
    byte_size = int(lengths[-1]) if lengths else None
    accepts_ranges = bool(
        re.search(r"(?im)^accept-ranges:\s*bytes\s*$", result.stdout)
    )
    return byte_size, accepts_ranges


def download_segment(
    url: str, output_path: Path, start: int, end: int
) -> None:
    subprocess.run(
        [
            "curl",
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--retry-all-errors",
            "--retry-delay",
            "2",
            "--connect-timeout",
            "20",
            "--max-time",
            "600",
            "--user-agent",
            USER_AGENT,
            "--header",
            "Accept: application/pdf,*/*;q=0.8",
            "--range",
            f"{start}-{end}",
            "--output",
            str(output_path),
            url,
        ],
        check=True,
        timeout=2460,
    )
    expected = end - start + 1
    if output_path.stat().st_size != expected:
        raise RuntimeError(
            f"range size mismatch for {start}-{end}: "
            f"expected {expected}, got {output_path.stat().st_size}"
        )


def segmented_download(
    item: dict[str, Any],
    output_path: Path,
    part_path: Path,
    byte_size: int,
    segments: int,
) -> None:
    part_path.unlink(missing_ok=True)
    segment_paths: list[Path] = []
    ranges: list[tuple[int, int]] = []
    segment_size = (byte_size + segments - 1) // segments
    for index in range(segments):
        start = index * segment_size
        if start >= byte_size:
            break
        end = min(byte_size - 1, start + segment_size - 1)
        ranges.append((start, end))
        segment_path = part_path.with_suffix(part_path.suffix + f".{index:03d}")
        segment_path.unlink(missing_ok=True)
        segment_paths.append(segment_path)

    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(segment_paths)
        ) as executor:
            futures = [
                executor.submit(
                    download_segment,
                    item["pdf_url"],
                    segment_path,
                    start,
                    end,
                )
                for segment_path, (start, end) in zip(segment_paths, ranges)
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        with part_path.open("wb") as output:
            for segment_path in segment_paths:
                with segment_path.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(block)
        if part_path.stat().st_size != byte_size:
            raise RuntimeError(
                f"assembled size mismatch: expected {byte_size}, "
                f"got {part_path.stat().st_size}"
            )
        with part_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise RuntimeError("assembled response did not start with %PDF-")
        part_path.replace(output_path)
    finally:
        for segment_path in segment_paths:
            segment_path.unlink(missing_ok=True)


def download_one(
    item: dict[str, Any], out_dir: Path, segments: int
) -> dict[str, Any]:
    output_path = out_dir / item["filename"]
    part_path = output_path.with_suffix(output_path.suffix + ".part")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_file():
        with output_path.open("rb") as handle:
            if handle.read(5) == b"%PDF-":
                item["download_status"] = "downloaded"
                item["download_error"] = None
                item["local_pdf_path"] = output_path.as_posix()
                return item
    if item.get("download_status") == "downloaded":
        item["download_status"] = "eligible"
        item["download_error"] = None
        item["local_pdf_path"] = None
    elif item.get("download_status") != "eligible":
        return item
    if segments > 1:
        try:
            byte_size, accepts_ranges = probe_pdf(item["pdf_url"])
            if byte_size and accepts_ranges and byte_size >= 2_000_000:
                segmented_download(
                    item,
                    output_path,
                    part_path,
                    byte_size,
                    segments,
                )
                item["download_status"] = "downloaded"
                item["download_error"] = None
                item["local_pdf_path"] = output_path.as_posix()
                return item
        except (
            OSError,
            RuntimeError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            part_path.unlink(missing_ok=True)
    command = [
        "curl",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--retry",
        "3",
        "--retry-all-errors",
        "--retry-delay",
        "2",
        "--connect-timeout",
        "20",
        "--max-time",
        "300",
        "--user-agent",
        USER_AGENT,
        "--header",
        "Accept: application/pdf,*/*;q=0.8",
        "--continue-at",
        "-",
    ]
    command.extend(
        [
            "--output",
            str(part_path),
            item["pdf_url"],
        ]
    )
    try:
        subprocess.run(command, check=True, timeout=1260)
        with part_path.open("rb") as handle:
            magic = handle.read(5)
        if magic != b"%PDF-":
            part_path.unlink(missing_ok=True)
            item["download_status"] = "not_pdf"
            item["download_error"] = "response did not start with %PDF-"
            item["local_pdf_path"] = None
            return item
        part_path.replace(output_path)
        item["download_status"] = "downloaded"
        item["download_error"] = None
        item["local_pdf_path"] = output_path.as_posix()
        return item
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        part_path.unlink(missing_ok=True)
        item["download_status"] = "failed"
        item["download_error"] = str(error)
        item["local_pdf_path"] = None
        return item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--segments",
        type=int,
        default=1,
        help="Parallel HTTP byte ranges per large PDF; 1 disables segmentation.",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, args.workers)
    ) as executor:
        futures = {
            executor.submit(
                download_one,
                item,
                args.out_dir,
                max(1, args.segments),
            ): index
            for index, item in enumerate(manifest)
        }
        for future in concurrent.futures.as_completed(futures):
            index = futures[future]
            manifest[index] = future.result()
            item = manifest[index]
            if item.get("download_status") in {"downloaded", "failed", "not_pdf"}:
                print(
                    f"{item['download_status']}: "
                    f"{item.get('source_id') or item.get('arxiv_id') or item['title']}",
                    flush=True,
                )

    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for item in manifest:
        status = item.get("download_status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps(counts, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
