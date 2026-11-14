"""Search over the public guidance (regulations, codes of practice, regulator
guides). This shared corpus holds public documents only: customer documents
never go into it (see site_docs.py)."""

from __future__ import annotations

import csv
import os
import re

import config


def get_guidance_retriever(k: int | None = None):
    k = k or config.TOP_K
    if config.RAG_BACKEND == "kb":
        from langchain_aws import AmazonKnowledgeBasesRetriever

        if not config.KNOWLEDGE_BASE_ID:
            raise RuntimeError("Set KNOWLEDGE_BASE_ID (step 3) or use RAG_BACKEND=faiss")
        return AmazonKnowledgeBasesRetriever(
            knowledge_base_id=config.KNOWLEDGE_BASE_ID,
            region_name=config.REGION,
            retrieval_config={
                "managedSearchConfiguration": {
                    "numberOfResults": k,
                }
            },
        )
    from langchain_community.vectorstores import FAISS

    from llm import get_embeddings

    store = FAISS.load_local(config.INDEX_DIR, get_embeddings(), allow_dangerous_deserialization=True)
    return store.as_retriever(search_kwargs={"k": k})


def source_and_page(doc) -> tuple[str, str]:
    """File name and 1-based page for both local (FAISS) and Knowledge Base results."""
    md = getattr(doc, "metadata", {}) or {}
    if md.get("source"):  # local loader: page counts from 0
        name = re.split(r"[\\/]", str(md["source"]))[-1]
        page = md.get("page")
        return name, (str(int(page) + 1) if page is not None and str(page).isdigit() else "")
    loc = md.get("location") or {}
    uri = (loc.get("s3Location") or {}).get("uri", "")
    name = uri.rsplit("/", 1)[-1] if uri else "unknown source"
    smd = md.get("source_metadata") or md
    page = smd.get("x-amz-bedrock-kb-document-page-number", "")
    try:
        page = str(int(float(page)))
    except (TypeError, ValueError):
        page = ""
    return name, page


def load_sources(path: str | None = None) -> dict[str, dict]:
    """guidance/sources.csv: one row per guidance file (file, title, publisher, url, ...)."""
    path = path or os.path.join(config.GUIDANCE_DIR, "sources.csv")
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["file"]: r for r in csv.DictReader(f) if r.get("file")}


def dedupe(docs, limit: int):
    seen, out = set(), []
    for d in docs:
        key = (source_and_page(d), d.page_content[:160])
        if key not in seen:
            seen.add(key)
            out.append(d)
        if len(out) >= limit:
            break
    return out
