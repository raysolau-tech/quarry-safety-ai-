"""Ask the verified library a question; answers cite requirement IDs and source pages.

    python ask_library.py "What do we need to check before using a loader each shift?"
    python ask_library.py --interactive

Answers come from verified rows only (not raw PDFs), so every answer traces
to a row you checked. The Bedrock guardrail (step 6) blocks off-topic
questions and masks personal details.
"""

from __future__ import annotations

import argparse
import sys

from library import load_evidence_types, load_library
from llm import METER, get_llm, text_of

SYSTEM = """You answer questions from quarry managers in NSW using ONLY the numbered requirements provided.
- Cite requirement IDs in square brackets, e.g. [PRE-003], and give the source and page for each.
- Say what evidence would show each requirement is met.
- If none of the requirements answers the question, say "The requirements library doesn't cover this yet." and stop.
- Under 200 words. General information, not legal advice."""


def row_text(r: dict, evidence: dict) -> str:
    ev = ", ".join(evidence[e]["label"] for e in r["evidence_types"].split(";") if e in evidence)
    return (
        f"[{r['req_id']}] {r['requirement']} ({r['obligation']}). Source: {r['source']}, page {r['page']}. "
        f"Evidence: {ev}. Example: {r.get('evidence_example', '')}"
    )


def build_retriever(rows: list[dict], evidence: dict, k: int = 6):
    from langchain_core.documents import Document
    from langchain_core.vectorstores import InMemoryVectorStore

    from llm import get_embeddings

    store = InMemoryVectorStore(get_embeddings())
    store.add_documents([Document(page_content=row_text(r, evidence), metadata={"req_id": r["req_id"]}) for r in rows])
    return store.as_retriever(search_kwargs={"k": k})


def ask(question: str, retriever, llm) -> dict:
    hits = retriever.invoke(question)
    context = "\n".join(h.page_content for h in hits)
    reply = llm.invoke([("system", SYSTEM), ("human", f"Requirements:\n{context}\n\nQuestion: {question}")])
    METER.add(getattr(reply, "usage_metadata", None))
    meta = getattr(reply, "response_metadata", {}) or {}
    blocked = meta.get("stopReason") == "guardrail_intervened" or meta.get("stop_reason") == "guardrail_intervened"
    return {"answer": text_of(reply).strip(), "ids": [h.metadata.get("req_id") for h in hits], "blocked": blocked}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args()
    rows = load_library(verified_only=True)
    if not rows:
        sys.exit("No verified requirements yet.")
    evidence = load_evidence_types()
    retriever = build_retriever(rows, evidence)
    llm = get_llm(guardrail=True, max_tokens=800)
    questions = [a.question] if a.question else []
    if a.interactive or not questions:
        print("Ask a question (blank line to quit).")
        while q := input("> ").strip():
            r = ask(q, retriever, llm)
            print(("[blocked by guardrail] " if r["blocked"] else "") + r["answer"] + "\n")
    for q in questions:
        r = ask(q, retriever, llm)
        print(("[blocked by guardrail] " if r["blocked"] else "") + r["answer"])
    print(f"\n{METER.line()}")


if __name__ == "__main__":
    main()
