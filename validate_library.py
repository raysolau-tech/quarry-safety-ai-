"""Check the library before you use it (and in CI from week 4).

    python validate_library.py            # exit code 1 if there are errors
    python validate_library.py --min 30   # also fail if fewer than 30 verified rows
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

import config
from library import coverage, load_evidence_types, load_library, load_topics, validate


def main(minimum: int = 0, path: str | None = None) -> int:
    topics = load_topics()
    evidence = load_evidence_types()
    rows = load_library(path)
    errors, warnings = validate(rows, topics, evidence)
    cov = coverage(rows, topics)
    total = sum(cov.values())

    print(f"Library: {path or config.LIBRARY_CSV}")
    for t in topics:
        print(f"  {t['id']} {t['name']}: {cov[t['id']]} verified")
    ev = Counter(e for r in rows if r.get("status") == "verified" for e in r["evidence_types"].split(";") if e)
    if ev:
        print("  Evidence types used: " + ", ".join(f"{k} {v}" for k, v in ev.most_common()))
    sensor = sum(
        1
        for r in rows
        if r.get("status") == "verified"
        and any(evidence.get(e, {}).get("source") == "sensor or camera" for e in r["evidence_types"].split(";"))
    )
    print(f"  Rows a camera or sensor could help prove: {sensor} (your edge product's opening)")

    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    if minimum and total < minimum:
        errors.append(f"only {total} verified rows; need {minimum}")
        print(f"  ERROR: only {total} verified rows; need {minimum}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=0)
    ap.add_argument("--library")
    a = ap.parse_args()
    sys.exit(main(a.min, a.library))
