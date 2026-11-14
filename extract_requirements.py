"""Draft requirement rows from the public guidance, for you to review.

    python extract_requirements.py                # all three topics
    python extract_requirements.py --topic CON    # one topic

For each topic: search the guidance -> send extracts to Claude in small
batches -> Claude proposes requirements with a verbatim quote -> the code
checks each quote really is in the extract, fills source and page itself,
flags likely duplicates -> rows land in data/candidates.csv as 'draft'.
Nothing reaches data/requirements.csv until you accept it in review_app.py.
"""

from __future__ import annotations

import argparse

import config
from grounding import is_grounded, similarity
from guidance import dedupe, get_guidance_retriever, load_sources, source_and_page
from library import load_candidates, load_evidence_types, load_library, load_topics, save_candidates
from llm import METER, get_llm, structured
from schema import CandidateList

SYSTEM = """You build a requirements library for quarry and small-mine operators in New South Wales, Australia.
From the numbered extracts of official guidance, list each specific, checkable requirement about the topic.

Rules:
- Use only the extracts. Never add requirements from your own knowledge.
- 'quote' must be copied exactly, character for character, from the extract you cite. Do not fix typos or join sentences from different places.
- Skip background, definitions, examples and anything that can't be checked on a site.
- Skip requirements that are already in the library list you are given.
- One obligation per row; split a sentence that sets two different duties.
- evidence_types must come from the allowed list, by id.
- Return an empty list if the extracts contain no requirements about the topic."""


def format_extracts(docs) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        name, page = source_and_page(d)
        parts.append(f"[{i}] ({name}, page {page or '?'})\n{d.page_content.strip()}")
    return "\n\n".join(parts)


def find_duplicate(text: str, rows: list[dict], threshold: float = 0.6) -> str:
    best_id, best = "", 0.0
    for r in rows:
        s = similarity(text, r.get("requirement", ""))
        if s > best:
            best_id, best = r.get("req_id") or "(another candidate)", s
    return best_id if best >= threshold else ""


def extract_topic(topic: dict, retriever, llm, existing: list[dict], evidence: dict, sources: dict) -> list[dict]:
    found = []
    for q in topic["queries"]:
        found.extend(retriever.invoke(q))
    docs = dedupe(found, config.MAX_EXTRACTS_PER_TOPIC)
    print(f"  {len(docs)} extracts")

    allowed = "\n".join(f"- {k}: {v['label']}" for k, v in evidence.items())
    known = [r for r in existing if r.get("topic") == topic["id"] and r.get("status") != "rejected"]
    known_text = "\n".join(f"- {r['requirement']}" for r in known) or "(none yet)"

    # Groq free tier has tight output-token limits; process one extract at a time.
    batch_size = 1 if config.LLM_BACKEND == "groq" else config.EXTRACTS_PER_CALL
    rows: list[dict] = []
    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        result: CandidateList = structured(
            llm,
            CandidateList,
            [
                ("system", SYSTEM),
                (
                    "human",
                    f"Topic: {topic['name']}: {topic['description']}\n\n"
                    f"Allowed evidence types:\n{allowed}\n\n"
                    f"Already in the library:\n{known_text}\n\n"
                    f"Extracts:\n\n{format_extracts(batch)}",
                ),
            ],
        )
        for c in result.candidates:
            if not 1 <= c.extract_n <= len(batch):
                print(f"    - dropped (cites extract {c.extract_n}, which doesn't exist): {c.requirement[:70]}")
                continue
            doc = batch[c.extract_n - 1]
            ok, score = is_grounded(c.quote, doc.page_content, config.QUOTE_MATCH)
            if not ok:
                print(f"    - dropped (quote not in extract, match {score}): {c.requirement[:70]}")
                continue
            notes = [] if score == 1.0 else [f"quote_fuzzy {score}"]
            bad_ev = [e for e in c.evidence_types if e not in evidence]
            if bad_ev:
                notes.append(f"removed unknown evidence types {bad_ev}")
            dup = find_duplicate(c.requirement, known + rows)
            if dup:
                notes.append(f"possible duplicate of {dup}")
            name, page = source_and_page(doc)  # from the search result, never from the model
            rows.append(
                {
                    "req_id": "",
                    "topic": topic["id"],
                    "requirement": c.requirement.strip(),
                    "obligation": c.obligation,
                    "quote": c.quote.strip(),
                    "source": name,
                    "page": page,
                    "url": sources.get(name, {}).get("url", ""),
                    "evidence_types": ";".join(e for e in c.evidence_types if e in evidence),
                    "evidence_example": c.evidence_example.strip(),
                    "applies_to": c.applies_to.strip(),
                    "status": "draft",
                    "notes": "; ".join(notes),
                    "extract": doc.page_content.strip(),
                }
            )
    return rows


def main(topic_filter: str | None = None, retriever=None, llm=None):
    topics = [t for t in load_topics() if not topic_filter or t["id"] == topic_filter]
    if not topics:
        raise SystemExit(f"No topic '{topic_filter}' in {config.TOPICS_JSON}")
    evidence = load_evidence_types()
    sources = load_sources()
    library = load_library()
    candidates = load_candidates()
    retriever = retriever or get_guidance_retriever()
    llm = llm or get_llm()

    added = 0
    for t in topics:
        print(f"{t['id']} {t['name']}")
        new = extract_topic(t, retriever, llm, library + candidates, evidence, sources)
        candidates.extend(new)
        added += len(new)
        print(f"  {len(new)} candidates kept")
    save_candidates(candidates)
    print(f"\n{added} new draft rows in {config.CANDIDATES_CSV}. {METER.line()}")
    print("Next: streamlit run review_app.py")
    return candidates


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="PRE, CON or CTR")
    main(ap.parse_args().topic)
