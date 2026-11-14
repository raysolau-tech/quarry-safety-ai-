"""The free pre-inspection check: a client's documents against your verified library.

    python pre_inspection_check.py --client "Ridgeview Quarry" --docs sample_site_docs
    python pre_inspection_check.py --client "Ridgeview Quarry" --docs clients/ridgeview --ocr
    python pre_inspection_check.py --render reports/ridgeview-quarry/findings.csv   # after your review
    python pre_inspection_check.py --demo     # offline, no AWS: fake model + test library

Steps: load the documents -> index them in memory -> pick the topics they
cover -> for each verified requirement, find the closest passages and ask
Claude whether the document provides for it -> check every quote really is
in the document (otherwise 'needs review') -> write findings.csv and a DRAFT
report -> you review every row -> re-render the final report.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import config
from grounding import is_grounded
from library import load_evidence_types, load_library, load_topics
from llm import METER, get_llm, structured
from report import FINDING_COLUMNS, to_html, to_markdown
from schema import DocFinding, TopicChoice
from site_docs import KeywordRetriever, chunk_pages, load_folder, vector_retriever

TOPIC_SYSTEM = (
    "You sort a quarry's site document into compliance topics. Say what the document is and which of the "
    "listed topic ids it is meant to cover. Choose only topics the document is actually about."
)

CHECK_SYSTEM = """You check whether a quarry's own document provides for one regulatory requirement.
You see the requirement and numbered excerpts from the site's documents.

Rules:
- Judge only what the excerpts say. A document that mentions a topic does not necessarily meet the requirement.
- 'documented' needs the whole requirement to be provided for; if any part is missing, use 'partly documented'.
- Copy 'quote' exactly from the excerpt you cite. Never write a quote that isn't in the excerpts.
- If nothing in the excerpts addresses the requirement, use 'not found', excerpt_n 0 and an empty quote.
- Gap and fix are for a busy quarry manager: plain, specific, under 25 words each."""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "client"


def library_version(path: str) -> str:
    data = Path(path).read_bytes() if Path(path).exists() else b""
    return f"#{hashlib.sha256(data).hexdigest()[:8]}"


def choose_topics(llm, chunks, topics) -> TopicChoice:
    sample = "\n\n".join(c.page_content for c in chunks[:6])[:5000]
    listing = "\n".join(f"- {t['id']}: {t['name']}: {t['description']}" for t in topics)
    choice: TopicChoice = structured(
        llm, TopicChoice, [("system", TOPIC_SYSTEM), ("human", f"Topics:\n{listing}\n\nDocument:\n\n{sample}")]
    )
    valid = {t["id"] for t in topics}
    choice.topics = [t for t in choice.topics if t in valid]
    return choice


def check_requirement(req: dict, retriever, llm, evidence: dict) -> dict:
    ev_labels = [evidence[e]["label"] for e in req["evidence_types"].split(";") if e in evidence]
    query = f"{req['requirement']} {req.get('evidence_example', '')} {' '.join(ev_labels)}"
    hits = retriever.invoke(query)
    excerpts = "\n\n".join(
        f"[{i}] ({h.metadata.get('file')}, p. {h.metadata.get('page')})\n{h.page_content}" for i, h in enumerate(hits, 1)
    )
    f: DocFinding = structured(
        llm,
        DocFinding,
        [
            ("system", CHECK_SYSTEM),
            ("human", f"Requirement {req['req_id']}: {req['requirement']}\n\nSite document excerpts:\n\n{excerpts}"),
        ],
    )
    status, file, page, match, quote = f.status, "", "", "", f.quote.strip()
    if status == "unclear":
        status = "needs review"
    if status in ("documented", "partly documented"):
        if not quote or not 1 <= f.excerpt_n <= len(hits):
            status, quote = "needs review", ""
        else:
            hit = hits[f.excerpt_n - 1]
            ok, score = is_grounded(quote, hit.page_content, config.QUOTE_MATCH)
            match = str(score)
            if ok:
                file, page = hit.metadata.get("file", ""), hit.metadata.get("page", "")
            else:  # the model's quote isn't in the document: never report it as evidence
                status, quote = "needs review", ""
    if status == "not found":
        quote = ""
    return {
        "req_id": req["req_id"],
        "topic": req["topic"],
        "requirement": req["requirement"],
        "obligation": req["obligation"],
        "source": req["source"],
        "page": req["page"],
        "url": req.get("url", ""),
        "status": status,
        "file": file,
        "doc_page": page,
        "quote": quote,
        "match": match,
        "gap": f.gap.strip() if status != "documented" else "",
        "fix": f.fix.strip() if status != "documented" else "",
        "evidence_types": req["evidence_types"],
        "evidence_example": req.get("evidence_example", ""),
        "reviewer_status": "",
        "reviewer_note": "",
    }


def write_outputs(out_dir: Path, meta: dict, findings: list[dict], topic_names: dict):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "findings.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FINDING_COLUMNS)
        w.writeheader()
        w.writerows(findings)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    render(out_dir, meta, findings, topic_names)


def render(out_dir: Path, meta: dict, findings: list[dict], topic_names: dict):
    md = to_markdown(meta, findings, topic_names)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    (out_dir / "report.html").write_text(to_html(md, f"Pre-inspection check: {meta['client']}"), encoding="utf-8")


def run(client: str, docs: str, topics_arg: str = "auto", ocr: bool = False, llm=None, retriever_factory=None,
        library_path: str | None = None, out_root: str = "reports") -> Path:
    if config.LLM_BACKEND != "bedrock" and llm is None:
        raise SystemExit("Customer documents only go to Claude on Bedrock (Australian profile). Set LLM_BACKEND=bedrock.")
    topics = load_topics()
    topic_names = {t["id"]: t["name"] for t in topics}
    evidence = load_evidence_types()
    library = load_library(library_path, verified_only=True)
    if not library:
        raise SystemExit("No verified requirements yet. Build the library first (steps 7-8).")

    pages, warnings = load_folder(docs, ocr=ocr)
    for w in warnings:
        print(f"  ! {w}")
    chunks = chunk_pages(pages)
    files = sorted({p[0] for p in pages})
    print(f"{len(files)} documents, {len(chunks)} passages")

    llm = llm or get_llm()
    retriever = (retriever_factory or vector_retriever)(chunks, config.SITE_TOP_K)

    if topics_arg == "auto":
        choice = choose_topics(llm, chunks, topics)
        chosen, doc_type = choice.topics, choice.document_type
        print(f"Looks like: {doc_type}. Topics: {chosen}")
    else:
        chosen, doc_type = [t.strip() for t in topics_arg.split(",")], ""
    reqs = [r for r in library if r["topic"] in chosen]
    if not reqs:
        raise SystemExit(f"No verified requirements for topics {chosen}")

    findings = []
    for r in reqs:
        f = check_requirement(r, retriever, llm, evidence)
        print(f"  {r['req_id']}: {f['status']}")
        findings.append(f)

    meta = {
        "client": client,
        "date": dt.date.today().isoformat(),
        "files": files,
        "document_type": doc_type,
        "topics": chosen,
        "prepared_by": config.REVIEWER,
        "library_version": f"{library_version(library_path or config.LIBRARY_CSV)} ({len(library)} verified requirements)",
        "warnings": warnings,
        "cost": METER.line(),
    }
    out_dir = Path(out_root) / slug(client)
    write_outputs(out_dir, meta, findings, topic_names)
    print(f"\nDraft report: {out_dir}/report.html\n{METER.line()}")
    print(f"Next: review every row in {out_dir}/findings.csv (reviewer_status, reviewer_note), then --render it.")
    return out_dir


def rerender(findings_csv: str):
    out_dir = Path(findings_csv).parent
    meta = json.loads((out_dir / "meta.json").read_text())
    with open(findings_csv, newline="", encoding="utf-8") as fh:
        findings = list(csv.DictReader(fh))
    allowed = {"documented", "partly documented", "not found", "needs review", ""}
    bad = [f["req_id"] for f in findings if f.get("reviewer_status", "").strip() not in allowed]
    if bad:
        raise SystemExit(f"reviewer_status must be one of {sorted(allowed - {''})}; check {bad}")
    topic_names = {t["id"]: t["name"] for t in load_topics()}
    render(out_dir, meta, findings, topic_names)
    left = sum(1 for f in findings if not f.get("reviewer_status"))
    print(f"Rendered {out_dir}/report.html" + (f" (still DRAFT: {left} rows not reviewed)" if left else " (final)"))


def demo():
    """Offline run with a fake model and the test library, to see the whole flow."""
    from tests.fakes import FakeLLM

    out = run(
        "DEMO Ridgeview Quarry",
        "sample_site_docs",
        llm=FakeLLM(),
        retriever_factory=KeywordRetriever,
        library_path="tests/fixtures/requirements_fixture.csv",
    )
    print(f"Demo report written to {out}/report.md (fake model: the findings are not real)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client")
    ap.add_argument("--docs", help="folder with the client's documents")
    ap.add_argument("--topics", default="auto", help="auto, or e.g. PRE,CTR")
    ap.add_argument("--ocr", action="store_true", help="read scanned PDFs and photos with Amazon Textract")
    ap.add_argument("--render", help="re-render a reviewed findings.csv")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        demo()
    elif a.render:
        rerender(a.render)
    elif a.client and a.docs:
        run(a.client, a.docs, a.topics, a.ocr)
    else:
        ap.error("use --client and --docs, or --render, or --demo")
