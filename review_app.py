"""Review draft requirements one at a time and accept, edit or reject them.

    REVIEWER="Your Name" streamlit run review_app.py

This step is the product's moat: every row in the library has been checked
by a person against the source page. Open the source PDF beside this app.
"""

from __future__ import annotations

import html

import streamlit as st

import config
from grounding import normalise
from library import (
    accept_candidate,
    coverage,
    load_candidates,
    load_evidence_types,
    load_library,
    load_topics,
    reject_candidate,
    save_candidates,
    save_library,
)

st.set_page_config(page_title="Requirements review", layout="wide")
topics = load_topics()
evidence = load_evidence_types()
topic_names = {t["id"]: t["name"] for t in topics}

library = load_library()
candidates = load_candidates()
drafts = [c for c in candidates if c.get("status") == "draft"]

with st.sidebar:
    st.header("Library")
    cov = coverage(library, topics)
    total = sum(cov.values())
    st.progress(min(total / 30, 1.0), text=f"{total} of 30 verified")
    for tid, n in cov.items():
        st.write(f"**{tid}** {topic_names[tid]}: {n}")
    st.write(f"Drafts waiting: {len(drafts)}")
    reviewer = st.text_input("Reviewer", value=config.REVIEWER)
    only = st.selectbox("Topic", ["All"] + list(topic_names))

queue = [c for c in drafts if only == "All" or c["topic"] == only]
if not queue:
    st.success("No drafts waiting. Run extract_requirements.py for more, or validate_library.py to check the library.")
    st.stop()

c = queue[0]
st.subheader(f"{c['topic']} · {topic_names.get(c['topic'], '')}")
if c.get("notes"):
    st.warning(c["notes"])

left, right = st.columns([1, 1])
with left:
    st.markdown(f"**Source:** {c['source']}, page {c['page'] or '?'}")
    if c.get("url"):
        st.markdown(f"[Open the source]({c['url']})")
    # show the extract with the quote highlighted
    extract = html.escape(c.get("extract", ""))
    q = html.escape(c.get("quote", ""))
    if q and q in extract:
        extract = extract.replace(q, f"<mark>{q}</mark>")
    elif normalise(c.get("quote", "")) not in normalise(c.get("extract", "")):
        st.caption("The quote matched only approximately; check the wording against the PDF.")
    st.markdown(f"<div style='white-space:pre-wrap;font-size:0.9em'>{extract}</div>", unsafe_allow_html=True)

with right:
    with st.form("review"):
        requirement = st.text_area("Requirement (plain English)", c["requirement"], height=90)
        quote = st.text_area("Quote (must match the source exactly)", c["quote"], height=90)
        col1, col2 = st.columns(2)
        obligation = col1.selectbox("Obligation", ["must", "should"], index=0 if c["obligation"] == "must" else 1)
        page = col2.text_input("Page (as printed in the PDF viewer)", c["page"])
        current = [e for e in c.get("evidence_types", "").split(";") if e in evidence]
        ev = st.multiselect(
            "Evidence that would prove it", list(evidence), default=current, format_func=lambda k: evidence[k]["label"]
        )
        evidence_example = st.text_input("What that evidence looks like on site", c["evidence_example"])
        applies_to = st.text_input("Applies to", c["applies_to"])
        url = st.text_input("Source URL", c.get("url", ""))
        notes = st.text_input("Your notes", "")
        reason = st.text_input("Reason, if rejecting", "")
        a, r, s = st.columns(3)
        accept = a.form_submit_button("Accept", type="primary")
        reject = r.form_submit_button("Reject")
        skip = s.form_submit_button("Skip for now")

    if accept:
        if not ev:
            st.error("Pick at least one evidence type.")
            st.stop()
        row = accept_candidate(
            c,
            library,
            reviewer,
            edits={
                "requirement": requirement.strip(),
                "quote": quote.strip(),
                "obligation": obligation,
                "page": page.strip(),
                "evidence_types": ";".join(ev),
                "evidence_example": evidence_example.strip(),
                "applies_to": applies_to.strip(),
                "url": url.strip(),
                "notes": "; ".join(x for x in [c.get("notes", ""), notes] if x),
            },
        )
        save_library(library)
        save_candidates(candidates)
        st.toast(f"Saved {row['req_id']}")
        st.rerun()
    if reject:
        reject_candidate(c, reason or "not a checkable requirement")
        save_candidates(candidates)
        st.rerun()
    if skip:
        candidates.remove(c)
        candidates.append(c)  # move to the back of the queue
        save_candidates(candidates)
        st.rerun()
