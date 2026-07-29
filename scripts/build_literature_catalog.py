#!/usr/bin/env python3
"""Build the literature-search catalog from official metadata sources.

This script is intentionally conservative about PDF redistribution:

* ACL Anthology papers from 2016 onward are marked redistributable under
  CC BY 4.0, using ACL's copyright FAQ as the license evidence.
* PMLR papers are marked redistributable under CC BY 4.0, using PMLR's
  publication agreement as the license evidence.
* arXiv papers are marked redistributable only when the paper page names a
  Creative Commons license that grants sharing. arXiv's default
  non-exclusive distribution license is *not* treated as permission for a
  third party to re-host the PDF.
* Open availability alone never implies redistribution permission.

The generated files are reproducible snapshots. Network metadata can change,
so the fetch date and exact source URLs are preserved in every record.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import html
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


FETCH_DATE = "2026-07-29"
USER_AGENT = "memory-label-response-narrowing-literature-catalog/1.0"
ACL_LICENSE_URL = "https://aclanthology.org/faq/copyright/"
PMLR_LICENSE_URL = "https://proceedings.mlr.press/pmlr-license-agreement.html"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class CitationMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value is not None}
        name = values.get("name", "")
        content = values.get("content", "")
        if name.startswith("citation_") and content:
            self.meta.setdefault(name, []).append(html.unescape(content))


def fetch_text(url: str, retries: int = 4) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/atom+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "40",
                url,
            ],
            check=True,
            capture_output=True,
            timeout=50,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"failed to fetch {url}: {last_error}; curl: {error}") from error


def one(values: dict[str, list[str]], name: str) -> str | None:
    entries = values.get(name, [])
    return entries[0].strip() if entries else None


def normalize_date(raw: str | None) -> str | None:
    if not raw:
        return None
    parts = re.findall(r"\d+", raw)
    if not parts:
        return None
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def base_record(seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": seed.get("title"),
        "authors": [],
        "year": None,
        "publication_date": None,
        "publication_type": None,
        "venue": None,
        "doi": None,
        "arxiv_id": None,
        "pubmed_id": None,
        "pmcid": None,
        "orcid": [],
        "issn": None,
        "isbn": None,
        "cnki_url": None,
        "abstract": None,
        "keywords": [],
        "mesh_terms": [],
        "jel_codes": [],
        "msc_codes": [],
        "acm_ccs": [],
        "study_type": None,
        "sample_size": None,
        "population": None,
        "citation_count": None,
        "citation_count_source": None,
        "download_count": None,
        "open_access_status": "unknown",
        "license": None,
        "license_evidence_url": None,
        "redistribution_status": "not_confirmed",
        "redistribution_note": None,
        "full_text_status": "unknown",
        "landing_url": None,
        "pdf_url": None,
        "local_pdf_path": None,
        "download_status": "not_requested",
        "download_error": None,
        "download_source": None,
        "data_availability": None,
        "code_url": seed.get("code_url"),
        "bibtex": None,
        "source_platforms": [],
        "source_id": seed["id"],
        "search_role": seed.get("role", []),
        "in_final_review": seed.get("in_final_review", False),
        "screening_decision": seed.get("screening_decision"),
        "exclusion_reason": seed.get("exclusion_reason"),
        "verification_level": "metadata_verified",
        "fetched_at": FETCH_DATE,
    }


def parse_citation_page(url: str) -> tuple[dict[str, list[str]], str]:
    page = fetch_text(url)
    parser = CitationMetaParser()
    parser.feed(page)
    return parser.meta, page


def record_from_acl(seed: dict[str, Any]) -> dict[str, Any]:
    anthology_id = seed["id"]
    landing_url = f"https://aclanthology.org/{anthology_id}/"
    meta, _ = parse_citation_page(landing_url)
    publication_date = normalize_date(one(meta, "citation_publication_date"))
    bibtex = fetch_text(f"https://aclanthology.org/{anthology_id}.bib").strip()
    record = base_record(seed)
    journal_title = one(meta, "citation_journal_title")
    record.update(
        {
            "title": one(meta, "citation_title"),
            "authors": meta.get("citation_author", []),
            "year": int(publication_date[:4]) if publication_date else None,
            "publication_date": publication_date,
            "publication_type": "journal-article" if journal_title else "conference",
            "venue": one(meta, "citation_conference_title")
            or journal_title,
            "doi": one(meta, "citation_doi"),
            "isbn": one(meta, "citation_isbn"),
            "open_access_status": "gold",
            "license": "CC-BY-4.0",
            "license_evidence_url": ACL_LICENSE_URL,
            "redistribution_status": "allowed",
            "redistribution_note": (
                "ACL states that all Anthology materials published in or after "
                "2016 are licensed under CC BY 4.0."
            ),
            "full_text_status": "open_pdf",
            "landing_url": landing_url,
            "pdf_url": one(meta, "citation_pdf_url")
            or f"https://aclanthology.org/{anthology_id}.pdf",
            "download_source": "acl_anthology",
            "bibtex": bibtex,
            "source_platforms": ["acl_anthology"],
        }
    )
    return record


def parse_arxiv_entries(ids: list[str]) -> dict[str, ET.Element]:
    query = urllib.parse.urlencode(
        {"id_list": ",".join(ids), "max_results": str(len(ids))}
    )
    xml_text = fetch_text(f"https://export.arxiv.org/api/query?{query}")
    root = ET.fromstring(xml_text)
    entries: dict[str, ET.Element] = {}
    for entry in root.findall("atom:entry", ARXIV_NS):
        raw_id = entry.findtext("atom:id", default="", namespaces=ARXIV_NS)
        match = re.search(r"/abs/([^v]+)(?:v\d+)?$", raw_id)
        if match:
            entries[match.group(1)] = entry
    return entries


def arxiv_license(arxiv_id: str) -> tuple[str | None, str]:
    landing_url = f"https://arxiv.org/abs/{arxiv_id}"
    page = fetch_text(landing_url)
    match = re.search(
        r'<div class="abs-license">\s*<a href="([^"]+)"',
        page,
        flags=re.IGNORECASE,
    )
    return (html.unescape(match.group(1)) if match else None), landing_url


def text_at(entry: ET.Element, path: str) -> str | None:
    value = entry.findtext(path, default="", namespaces=ARXIV_NS).strip()
    return re.sub(r"\s+", " ", value) if value else None


def record_from_arxiv(
    seed: dict[str, Any], entry: ET.Element
) -> dict[str, Any]:
    arxiv_id = seed["id"]
    publication_date = text_at(entry, "atom:published")
    license_url, landing_url = arxiv_license(arxiv_id)
    authors = [
        re.sub(
            r"\s+",
            " ",
            author.findtext("atom:name", default="", namespaces=ARXIV_NS),
        ).strip()
        for author in entry.findall("atom:author", ARXIV_NS)
    ]
    pdf_url = None
    for link in entry.findall("atom:link", ARXIV_NS):
        if link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href")
            break
    doi = text_at(entry, "arxiv:doi")
    raw_entry_id = text_at(entry, "atom:id") or ""
    version_match = re.search(r"v(\d+)$", raw_entry_id)
    source_version = (
        f"v{version_match.group(1)}" if version_match else None
    )
    license_slug = None
    redistribution_status = "not_confirmed"
    redistribution_note = (
        "No paper-specific license granting third-party redistribution was found."
    )
    if license_url:
        if "creativecommons.org/licenses/" in license_url:
            path = urllib.parse.urlparse(license_url).path
            license_match = re.search(r"/licenses/([^/]+)/([^/]+)/?", path)
            license_slug = (
                f"CC-{license_match.group(1).upper()}-{license_match.group(2)}"
                if license_match
                else license_url
            )
            redistribution_status = "allowed"
            redistribution_note = (
                "The arXiv record names a Creative Commons license that permits "
                "sharing, subject to its stated conditions."
            )
        elif "nonexclusive-distrib" in license_url:
            license_slug = "ARXIV-NONEXCLUSIVE-DISTRIB-1.0"
            redistribution_note = (
                "The arXiv non-exclusive distribution license permits arXiv to "
                "host the paper; it is not treated here as permission for this "
                "project to re-host the PDF."
            )
    date_only = publication_date[:10] if publication_date else None
    record = base_record(seed)
    record.update(
        {
            "title": text_at(entry, "atom:title"),
            "authors": authors,
            "year": int(date_only[:4]) if date_only else None,
            "publication_date": date_only,
            "publication_type": "preprint",
            "venue": "arXiv",
            "doi": doi,
            "arxiv_id": arxiv_id,
            "source_version": source_version,
            "abstract": text_at(entry, "atom:summary"),
            "open_access_status": "green",
            "license": license_slug,
            "license_evidence_url": license_url or landing_url,
            "redistribution_status": redistribution_status,
            "redistribution_note": redistribution_note,
            "full_text_status": "open_pdf",
            "landing_url": landing_url,
            "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
            "download_source": "arxiv",
            "source_platforms": ["arxiv"],
        }
    )
    record["bibtex"] = make_bibtex(record)
    return record


def record_from_pmlr(seed: dict[str, Any]) -> dict[str, Any]:
    volume, paper_id = seed["id"].split("/", 1)
    landing_url = f"https://proceedings.mlr.press/{volume}/{paper_id}.html"
    meta, page = parse_citation_page(landing_url)
    publication_date = normalize_date(one(meta, "citation_publication_date"))
    abstract_match = re.search(
        r'<div id="abstract"[^>]*>.*?<p[^>]*>(.*?)</p>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    abstract = None
    if abstract_match:
        abstract = re.sub(r"<[^>]+>", " ", abstract_match.group(1))
        abstract = re.sub(r"\s+", " ", html.unescape(abstract)).strip()
    record = base_record(seed)
    record.update(
        {
            "title": one(meta, "citation_title"),
            "authors": meta.get("citation_author", []),
            "year": int(publication_date[:4]) if publication_date else None,
            "publication_date": publication_date,
            "publication_type": "conference",
            "venue": one(meta, "citation_conference_title")
            or one(meta, "citation_inbook_title"),
            "issn": one(meta, "citation_issn"),
            "abstract": abstract,
            "open_access_status": "gold",
            "license": "CC-BY-4.0",
            "license_evidence_url": PMLR_LICENSE_URL,
            "redistribution_status": "allowed",
            "redistribution_note": (
                "PMLR's publication agreement grants the public a CC BY 4.0 "
                "license and requires attribution to the proceedings page."
            ),
            "full_text_status": "open_pdf",
            "landing_url": landing_url,
            "pdf_url": one(meta, "citation_pdf_url"),
            "download_source": "pmlr",
            "source_platforms": ["pmlr"],
        }
    )
    record["bibtex"] = make_bibtex(record)
    return record


def record_from_neurips(seed: dict[str, Any]) -> dict[str, Any]:
    year, paper_hash = seed["id"].split("/", 1)
    landing_url = (
        "https://proceedings.neurips.cc/paper_files/paper/"
        f"{year}/hash/{paper_hash}-Abstract-Conference.html"
    )
    meta, _ = parse_citation_page(landing_url)
    publication_date = normalize_date(one(meta, "citation_publication_date"))
    record = base_record(seed)
    record.update(
        {
            "title": one(meta, "citation_title"),
            "authors": meta.get("citation_author", []),
            "year": int(publication_date[:4]) if publication_date else int(year),
            "publication_date": publication_date,
            "publication_type": "conference",
            "venue": one(meta, "citation_conference_title")
            or f"NeurIPS {year}",
            "doi": one(meta, "citation_doi"),
            "abstract": one(meta, "citation_abstract"),
            "open_access_status": "bronze",
            "redistribution_status": "not_confirmed",
            "redistribution_note": (
                "The official PDF is publicly readable, but this search did not "
                "find a paper-specific public license allowing third-party "
                "redistribution."
            ),
            "full_text_status": "open_pdf",
            "landing_url": landing_url,
            "pdf_url": one(meta, "citation_pdf_url"),
            "download_source": "neurips",
            "source_platforms": ["neurips"],
        }
    )
    record["bibtex"] = make_bibtex(record)
    return record


def record_from_unverified(seed: dict[str, Any]) -> dict[str, Any]:
    record = base_record(seed)
    record.update(
        {
            "title": seed.get("title"),
            "doi": seed["id"] if seed["id"].startswith("10.") else None,
            "landing_url": (
                f"https://doi.org/{seed['id']}"
                if seed["id"].startswith("10.")
                else None
            ),
            "redistribution_status": "not_confirmed",
            "full_text_status": "unknown",
            "download_status": "skipped",
            "download_error": seed.get("exclusion_reason"),
            "source_platforms": ["search_lead_only"],
            "verification_level": "unable_to_verify",
        }
    )
    return record


def strip_markup(value: str | None) -> str | None:
    if not value:
        return None
    plain = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(plain)).strip()


def record_from_crossref_journal(seed: dict[str, Any]) -> dict[str, Any]:
    doi = seed["id"]
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
    payload = json.loads(fetch_text(url))
    message = payload["message"]
    date_parts = (
        message.get("published-online", {}).get("date-parts")
        or message.get("published", {}).get("date-parts")
        or message.get("issued", {}).get("date-parts")
        or []
    )
    date_values = date_parts[0] if date_parts else []
    publication_date = None
    if date_values:
        publication_date = "-".join(
            [
                f"{date_values[0]:04d}",
                *[f"{value:02d}" for value in date_values[1:]],
            ]
        )
    authors = [
        " ".join(
            value
            for value in [author.get("given"), author.get("family")]
            if value
        )
        for author in message.get("author", [])
    ]
    record = base_record(seed)
    record.update(
        {
            "title": (message.get("title") or [seed.get("title")])[0],
            "authors": authors,
            "year": date_values[0] if date_values else None,
            "publication_date": publication_date,
            "publication_type": message.get("type") or "journal-article",
            "venue": html.unescape((message.get("container-title") or [""])[0]),
            "doi": doi,
            "arxiv_id": seed.get("arxiv_id"),
            "issn": (message.get("ISSN") or [None])[0],
            "abstract": strip_markup(message.get("abstract")),
            "citation_count": message.get("is-referenced-by-count"),
            "citation_count_source": "crossref",
            "open_access_status": "gold",
            "full_text_status": "open_pdf",
            "landing_url": message.get("URL") or f"https://doi.org/{doi}",
            "pdf_url": next(
                (
                    link.get("URL")
                    for link in message.get("link", [])
                    if link.get("content-type") == "application/pdf"
                ),
                None,
            ),
            "download_source": "publisher",
            "source_platforms": ["crossref", "publisher"],
        }
    )
    return record


def apply_seed_overrides(
    record: dict[str, Any], seed: dict[str, Any]
) -> dict[str, Any]:
    mapping = {
        "year_override": "year",
        "publication_date_override": "publication_date",
        "venue_override": "venue",
        "doi_override": "doi",
        "landing_url_override": "landing_url",
        "pdf_url_override": "pdf_url",
        "license_override": "license",
        "license_evidence_url_override": "license_evidence_url",
        "redistribution_status_override": "redistribution_status",
        "redistribution_note_override": "redistribution_note",
        "pmcid_override": "pmcid",
        "download_source_override": "download_source",
    }
    for seed_field, record_field in mapping.items():
        if seed.get(seed_field) is not None:
            record[record_field] = seed[seed_field]
    additions = seed.get("source_platforms_add") or []
    record["source_platforms"] = list(
        dict.fromkeys([*(record.get("source_platforms") or []), *additions])
    )
    if seed.get("code_url"):
        record["code_url"] = seed["code_url"]
    if seed.get("arxiv_id"):
        record["arxiv_id"] = seed["arxiv_id"]
    if record.get("redistribution_status") == "allowed":
        record["open_access_status"] = (
            record.get("open_access_status")
            if record.get("open_access_status") != "unknown"
            else "gold"
        )
        record["full_text_status"] = "open_pdf"
    if seed.get("source") != "acl_anthology":
        record["bibtex"] = make_bibtex(record)
    else:
        record["bibtex"] = record.get("bibtex") or make_bibtex(record)
    return record


def make_key(record: dict[str, Any]) -> str:
    first_author = record.get("authors", ["unknown"])[0] if record.get("authors") else "unknown"
    surname = re.sub(r"[^A-Za-z0-9]", "", first_author.split()[-1]).lower() or "unknown"
    title_words = re.findall(r"[A-Za-z0-9]+", record.get("title") or "")
    stop = {"a", "an", "the", "of", "on", "in", "for", "and", "with", "how", "does"}
    first_word = next((word.lower() for word in title_words if word.lower() not in stop), "paper")
    return f"{surname}{record.get('year') or 'nd'}{first_word}"


def bib_escape(value: str) -> str:
    return value.replace("&", r"\&")


def make_bibtex(record: dict[str, Any]) -> str:
    kind = (
        "inproceedings"
        if record.get("publication_type") == "conference"
        else "misc"
    )
    key = make_key(record)
    fields: list[tuple[str, str]] = [
        ("title", record.get("title") or "Unknown title"),
        ("author", " and ".join(record.get("authors") or ["Unknown"])),
        ("year", str(record.get("year") or "")),
    ]
    if kind == "inproceedings" and record.get("venue"):
        fields.append(("booktitle", record["venue"]))
    if record.get("doi"):
        fields.append(("doi", record["doi"]))
    if record.get("arxiv_id"):
        fields.extend(
            [
                ("eprint", record["arxiv_id"]),
                ("archivePrefix", "arXiv"),
            ]
        )
    if record.get("landing_url"):
        fields.append(("url", record["landing_url"]))
    lines = [f"@{kind}{{{key},"]
    for index, (name, value) in enumerate(fields):
        comma = "," if index < len(fields) - 1 else ""
        lines.append(f"  {name:<13} = {{{bib_escape(value)}}}{comma}")
    lines.append("}")
    return "\n".join(lines)


def build_records(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    arxiv_ids = [seed["id"] for seed in seeds if seed["source"] == "arxiv"]
    arxiv_entries = parse_arxiv_entries(arxiv_ids) if arxiv_ids else {}

    def build_one(seed: dict[str, Any]) -> dict[str, Any]:
        source = seed["source"]
        if source == "acl_anthology":
            record = record_from_acl(seed)
        elif source == "arxiv":
            entry = arxiv_entries.get(seed["id"])
            if entry is None:
                raise RuntimeError(f"arXiv metadata not returned for {seed['id']}")
            record = record_from_arxiv(seed, entry)
        elif source == "pmlr":
            record = record_from_pmlr(seed)
        elif source == "neurips":
            record = record_from_neurips(seed)
        elif source == "crossref_journal":
            record = record_from_crossref_journal(seed)
        elif source == "unverified":
            record = record_from_unverified(seed)
        else:
            raise RuntimeError(f"unsupported source: {source}")
        record = apply_seed_overrides(record, seed)
        if record.get("title") is None:
            raise RuntimeError(f"missing title for {source}:{seed['id']}")
        return record

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        records = list(executor.map(build_one, seeds))
    return sorted(
        records,
        key=lambda item: (
            item.get("screening_decision") == "exclude_unverified",
            -(item.get("year") or 0),
            item.get("title") or "",
        ),
    )


def download_policy_record(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record)
    if record.get("redistribution_status") != "allowed":
        item["full_text_status"] = "license_not_redistributable"
        item["download_status"] = "skipped"
        item["download_error"] = (
            "Public reading link retained; repository redistribution permission "
            "was not confirmed."
        )
    return item


def write_csv(path: Path, records: Iterable[dict[str, Any]]) -> None:
    fields = [
        "title",
        "authors",
        "year",
        "venue",
        "doi",
        "arxiv_id",
        "landing_url",
        "search_role",
        "in_final_review",
        "screening_decision",
        "exclusion_reason",
        "verification_level",
        "full_text_status",
        "license",
        "redistribution_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in fields}
            row["authors"] = "; ".join(record.get("authors") or [])
            row["search_role"] = "; ".join(record.get("search_role") or [])
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("literature/search/corpus_seed.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("literature/metadata"),
    )
    parser.add_argument(
        "--screening-csv",
        type=Path,
        default=Path("literature/search/screening_inventory.csv"),
    )
    args = parser.parse_args()

    seeds = json.loads(args.seed.read_text(encoding="utf-8"))
    records = build_records(seeds)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.screening_csv.parent.mkdir(parents=True, exist_ok=True)

    (args.out_dir / "papers.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "download_policy_input.json").write_text(
        json.dumps(
            [download_policy_record(record) for record in records],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    bibliography = "\n\n".join(
        record["bibtex"]
        for record in records
        if record.get("bibtex")
    )
    (args.out_dir / "references.bib").write_text(
        bibliography.rstrip() + "\n",
        encoding="utf-8",
    )
    write_csv(args.screening_csv, records)
    print(
        json.dumps(
            {
                "records": len(records),
                "redistributable_pdfs": sum(
                    record.get("redistribution_status") == "allowed"
                    for record in records
                ),
                "link_only": sum(
                    record.get("full_text_status") == "open_pdf"
                    and record.get("redistribution_status") != "allowed"
                    for record in records
                ),
                "unverified": sum(
                    record.get("verification_level") == "unable_to_verify"
                    for record in records
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
