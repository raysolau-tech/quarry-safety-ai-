"""The requirements library: a plain CSV you keep in Git.

Why a CSV and not a vector database: the library is a small, hand-checked
table (30 rows this week, a few hundred later). Every row must be exact and
traceable to a page of a source. It is the product's source of truth; search
indexes are built from it, never the other way round. When you have paying
customers it moves to a database table with the same columns."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path

import config
from schema import CANDIDATE_EXTRA, LIBRARY_COLUMNS


# --- Reference data ----------------------------------------------------------


def load_topics(path: str | None = None) -> list[dict]:
    return json.loads(Path(path or config.TOPICS_JSON).read_text())["topics"]


def load_evidence_types(path: str | None = None) -> dict[str, dict]:
    items = json.loads(Path(path or config.EVIDENCE_JSON).read_text())["evidence_types"]
    return {e["id"]: e for e in items}


# --- CSV in and out ------------------------------------------------------------


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_rows(path: str, rows: list[dict], columns: list[str]):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})
    os.replace(tmp, path)  # never leaves a half-written library


def load_library(path: str | None = None, verified_only: bool = False) -> list[dict]:
    rows = read_rows(path or config.LIBRARY_CSV)
    return [r for r in rows if r.get("status") == "verified"] if verified_only else rows


def save_library(rows: list[dict], path: str | None = None):
    write_rows(path or config.LIBRARY_CSV, rows, LIBRARY_COLUMNS)


def load_candidates(path: str | None = None) -> list[dict]:
    return read_rows(path or config.CANDIDATES_CSV)


def save_candidates(rows: list[dict], path: str | None = None):
    write_rows(path or config.CANDIDATES_CSV, rows, LIBRARY_COLUMNS + CANDIDATE_EXTRA)


# --- Review: candidates become library rows only through you --------------------


def next_id(library: list[dict], topic: str) -> str:
    nums = [
        int(r["req_id"].split("-")[1])
        for r in library
        if r.get("req_id", "").startswith(f"{topic}-") and r["req_id"].split("-")[1].isdigit()
    ]
    return f"{topic}-{(max(nums) + 1) if nums else 1:03d}"


def accept_candidate(candidate: dict, library: list[dict], reviewer: str, edits: dict | None = None) -> dict:
    if not reviewer:
        raise ValueError("Set REVIEWER (your name) before accepting rows")
    row = {c: candidate.get(c, "") for c in LIBRARY_COLUMNS}
    row.update(edits or {})
    row["req_id"] = next_id(library, row["topic"])
    row["status"] = "verified"
    row["verified_by"] = reviewer
    row["verified_on"] = dt.date.today().isoformat()
    library.append(row)
    candidate["status"] = "verified"
    candidate["req_id"] = row["req_id"]
    return row


def reject_candidate(candidate: dict, reason: str):
    candidate["status"] = "rejected"
    candidate["notes"] = "; ".join(x for x in [candidate.get("notes", ""), f"rejected: {reason}"] if x)


# --- Validation (run before every check, and in CI from week 4) -----------------


def validate(library: list[dict], topics: list[dict], evidence: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors mean the library can't be used."""
    errors, warnings = [], []
    topic_ids = {t["id"] for t in topics}
    seen = set()
    for i, r in enumerate(library, start=2):  # row 1 is the header
        where = f"row {i} ({r.get('req_id') or 'no id'})"
        if r.get("status") not in {"draft", "verified", "rejected"}:
            errors.append(f"{where}: status must be draft, verified or rejected")
        if r.get("status") != "verified":
            continue
        rid = r.get("req_id", "")
        if not rid:
            errors.append(f"{where}: verified row without req_id")
        elif rid in seen:
            errors.append(f"{where}: duplicate req_id {rid}")
        seen.add(rid)
        if r.get("topic") not in topic_ids:
            errors.append(f"{where}: unknown topic '{r.get('topic')}'")
        for col in ("requirement", "quote", "source", "page", "evidence_types", "verified_by", "verified_on"):
            if not str(r.get(col, "")).strip():
                errors.append(f"{where}: '{col}' is empty")
        if r.get("obligation") not in {"must", "should"}:
            errors.append(f"{where}: obligation must be 'must' or 'should'")
        for e in filter(None, (x.strip() for x in r.get("evidence_types", "").split(";"))):
            if e not in evidence:
                errors.append(f"{where}: evidence type '{e}' isn't in evidence_types.json")
        if not r.get("url"):
            warnings.append(f"{where}: no url; add where the source can be downloaded")
        if "quote_fuzzy" in r.get("notes", ""):
            warnings.append(f"{where}: quote matched its source only approximately; re-check the wording")
    return errors, warnings


def coverage(library: list[dict], topics: list[dict]) -> dict[str, int]:
    verified = [r for r in library if r.get("status") == "verified"]
    return {t["id"]: sum(1 for r in verified if r["topic"] == t["id"]) for t in topics}
