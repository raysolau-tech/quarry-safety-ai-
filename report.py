"""Turn findings into the report you send: Markdown, plus HTML you can print to PDF."""

from __future__ import annotations

import datetime as dt
from collections import Counter

ORDER = ["not found", "partly documented", "needs review", "documented"]
ICON = {"not found": "✗", "partly documented": "◐", "needs review": "?", "documented": "✓"}

FINDING_COLUMNS = [
    "req_id", "topic", "requirement", "obligation", "source", "page", "url",
    "status", "file", "doc_page", "quote", "match", "gap", "fix",
    "evidence_types", "evidence_example", "reviewer_status", "reviewer_note",
]


def final_status(f: dict) -> str:
    return (f.get("reviewer_status") or f["status"]).strip()


def _cell(text: str) -> str:
    return str(text or "").replace("|", "/").replace("\n", " ").strip()


def to_markdown(meta: dict, findings: list[dict], topic_names: dict[str, str]) -> str:
    reviewed = all(f.get("reviewer_status") for f in findings)
    counts = Counter(final_status(f) for f in findings)
    lines = []
    if not reviewed:
        lines += ["> **DRAFT: not yet reviewed.** Check every row, fill `reviewer_status` in findings.csv, then re-render.", ""]
    lines += [
        f"# Pre-inspection check: {meta['client']}",
        "",
        f"**Date:** {meta.get('date', dt.date.today().isoformat())}  ",
        f"**Documents checked:** {', '.join(meta['files'])}  ",
        f"**What they are:** {meta.get('document_type', '')}  ",
        f"**Topics:** {', '.join(topic_names.get(t, t) for t in meta['topics'])}  ",
        f"**Prepared by:** {meta.get('prepared_by', '')}",
        "",
        "## Summary",
        "",
        f"We compared your documents with **{len(findings)} requirements** from NSW and national guidance.",
        "",
        "| Result | Count |",
        "| --- | --- |",
    ]
    for s in ORDER:
        lines.append(f"| {ICON[s]} {s} | {counts.get(s, 0)} |")

    top = [f for f in findings if final_status(f) == "not found" and f.get("obligation") == "must"][:3]
    if top:
        lines += ["", "**Most important gaps:**", ""]
        lines += [f"- **{f['req_id']}** {f['requirement']} ({f['source']}, p. {f['page']})" for f in top]

    for tid in meta["topics"]:
        rows = [f for f in findings if f["topic"] == tid]
        if not rows:
            continue
        rows.sort(key=lambda f: (ORDER.index(final_status(f)) if final_status(f) in ORDER else 9, f["req_id"]))
        lines += [
            "",
            f"## {topic_names.get(tid, tid)}",
            "",
            "| | Requirement | Source | What we found in your documents | Suggested change | What an inspector may ask to see |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for f in rows:
            st = final_status(f)
            found = f'"{_cell(f["quote"])}" ({f["file"]}, p. {f["doc_page"]})' if f.get("quote") else "Nothing found"
            change = _cell(f.get("reviewer_note") or f.get("fix") or f.get("gap") or "")
            src = f"{_cell(f['source'])}, p. {f['page']}"
            if f.get("url"):
                src = f"[{src}]({f['url']})"
            lines.append(
                f"| {ICON.get(st, '')} {st} | **{f['req_id']}** {_cell(f['requirement'])} ({f['obligation']}) | {src} "
                f"| {found} | {change} | {_cell(f.get('evidence_example'))} |"
            )

    lines += [
        "",
        "## Documents are only half of it",
        "",
        "This check reads what your documents say. An inspector will also ask for proof that it happens: "
        "signed records, registers and, increasingly, camera and machine data. The last column shows what "
        "that proof looks like for each requirement. If you'd like, we can check the records you already "
        "keep against the same requirements and show which ones have no evidence behind them.",
        "",
        "## How this check was done",
        "",
        f"- Requirements library {meta.get('library_version', '')}: each requirement is quoted from its source "
        "and checked by a person against the source page.",
        "- Your documents were read and searched in Amazon Web Services in Sydney; the AI model ran through "
        "Amazon Bedrock's Australian profile (Sydney and Melbourne). Your documents were not used to train any model.",
        "- Every quote from your documents was checked automatically against the text; anything that didn't "
        "match was marked for review, then every row was reviewed by a person.",
        f"- {meta.get('retention', 'Your documents will be deleted within 30 days, or sooner if you ask.')}",
        "",
        "*This report is general information to help you prepare. It is not legal advice and doesn't confirm "
        "compliance. Check the source documents, and talk to the NSW Resources Regulator or a WHS professional "
        "about your obligations.*",
    ]
    return "\n".join(lines) + "\n"


CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:1100px;margin:32px auto;padding:0 16px;color:#1d1d1f;line-height:1.45}
h1{font-size:26px;margin-bottom:8px}h2{font-size:19px;margin-top:32px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
th,td{border:1px solid #ddd;padding:6px 8px;vertical-align:top;text-align:left}th{background:#f4f4f2}
blockquote{background:#fff4e5;border-left:4px solid #f0a020;margin:0 0 16px;padding:8px 12px}
@media print{body{margin:0;max-width:none}a{color:inherit}}
"""


def to_html(markdown_text: str, title: str) -> str:
    import markdown

    body = markdown.markdown(markdown_text, extensions=["tables"])
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
