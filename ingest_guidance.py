"""Prepare the public guidance for search.

    python ingest_guidance.py --kb-metadata   # writes <file>.metadata.json next to each PDF for the Knowledge Base
    python ingest_guidance.py --faiss         # builds a local index instead of (or as well as) a Knowledge Base

The metadata files let you filter Knowledge Base searches later
(e.g. jurisdiction = NSW) and are uploaded to S3 alongside the PDFs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import config
from guidance import load_sources


def write_kb_metadata():
    sources = load_sources()
    pdfs = sorted(Path(config.GUIDANCE_DIR).glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs in {config.GUIDANCE_DIR}/ (see guidance/SOURCES.md)")
    for pdf in pdfs:
        s = sources.get(pdf.name)
        if not s:
            print(f"  ! {pdf.name} isn't in guidance/sources.csv; add a row for it")
            continue
        attrs = {k: s[k] for k in ("publisher", "jurisdiction", "doc_type", "title") if s.get(k)}
        Path(f"{pdf}.metadata.json").write_text(json.dumps({"metadataAttributes": attrs}, indent=2))
        print(f"  wrote {pdf.name}.metadata.json")


def build_faiss():
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from llm import get_embeddings

    docs = []
    for pdf in sorted(Path(config.GUIDANCE_DIR).glob("*.pdf")):
        pages = PyPDFLoader(str(pdf)).load()
        docs.extend(pages)
        print(f"  {pdf.name}: {len(pages)} pages")
    splitter = RecursiveCharacterTextSplitter(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    chunks = splitter.split_documents(docs)
    print(f"Embedding {len(chunks)} chunks with {config.EMBED_MODEL_ID} ...")
    store = FAISS.from_documents(chunks, get_embeddings())
    os.makedirs(config.INDEX_DIR, exist_ok=True)
    store.save_local(config.INDEX_DIR)
    print(f"Saved to {config.INDEX_DIR}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb-metadata", action="store_true")
    ap.add_argument("--faiss", action="store_true")
    a = ap.parse_args()
    if not (a.kb_metadata or a.faiss):
        ap.error("choose --kb-metadata, --faiss or both")
    if a.kb_metadata:
        write_kb_metadata()
    if a.faiss:
        build_faiss()
