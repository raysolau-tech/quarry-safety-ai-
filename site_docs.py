"""Load a customer's site documents and make them searchable for one check.

Customer documents are kept apart from the shared guidance: they are read
from the client's folder, indexed in memory for this run only, and never
uploaded to the Knowledge Base. Scanned PDFs and photos of paper checklists
go through Amazon Textract in Sydney (optional, --ocr)."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import config
from grounding import tokens

TEXT_TYPES = {".txt", ".md"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg"}


@dataclass
class Chunk:
    page_content: str
    metadata: dict = field(default_factory=dict)  # {"file":..., "page":...}


# --- Loading ------------------------------------------------------------------


def load_pdf(path: Path, ocr: bool) -> tuple[list[tuple[str, str]], list[str]]:
    from pypdf import PdfReader

    pages, warnings = [], []
    reader = PdfReader(str(path))
    blank = []
    for i, p in enumerate(reader.pages, 1):
        text = p.extract_text() or ""
        if len(text.strip()) < 30:
            blank.append(i)
        pages.append((str(i), text))
    if blank and ocr:
        ocr_pages = textract_pdf(path)
        pages = [(n, ocr_pages.get(n, t) if int(n) in blank else t) for n, t in pages]
    elif blank:
        warnings.append(f"{path.name}: pages {blank} have no text (scanned?). Rerun with --ocr.")
    return pages, warnings


def load_docx(path: Path) -> list[tuple[str, str]]:
    import docx  # python-docx

    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            parts.append(" | ".join(dict.fromkeys(c for c in cells if c)))  # merged cells repeat
    return [("1", "\n".join(parts))]  # Word files have no fixed pages


def load_folder(folder: str, ocr: bool = False) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Returns ([(file, page, text)], warnings)."""
    out, warnings = [], []
    files = sorted(p for p in Path(folder).iterdir() if p.is_file() and not p.name.startswith("."))
    for p in files:
        ext = p.suffix.lower()
        if ext in TEXT_TYPES:
            out.append((p.name, "1", p.read_text(encoding="utf-8", errors="replace")))
        elif ext == ".pdf":
            pages, w = load_pdf(p, ocr)
            out.extend((p.name, n, t) for n, t in pages)
            warnings.extend(w)
        elif ext == ".docx":
            out.extend((p.name, n, t) for n, t in load_docx(p))
        elif ext in IMAGE_TYPES:
            if ocr:
                out.append((p.name, "1", textract_image(p)))
            else:
                warnings.append(f"{p.name}: photo of a document; rerun with --ocr to read it")
        else:
            warnings.append(f"{p.name}: skipped (unsupported type {ext})")
    if not out:
        raise SystemExit(f"No readable documents in {folder}")
    return out, warnings


# --- Textract (optional) -----------------------------------------------------------


def _lines_by_page(blocks) -> dict[str, str]:
    pages: dict[str, list[str]] = {}
    for b in blocks:
        if b.get("BlockType") == "LINE":
            pages.setdefault(str(b.get("Page", 1)), []).append(b.get("Text", ""))
    return {k: "\n".join(v) for k, v in pages.items()}


def textract_image(path: Path) -> str:
    import boto3

    client = boto3.client("textract", region_name=config.REGION)
    resp = client.detect_document_text(Document={"Bytes": path.read_bytes()})
    return _lines_by_page(resp["Blocks"]).get("1", "")


def textract_pdf(path: Path) -> dict[str, str]:
    """Multi-page scanned PDF: Textract reads it from S3 (asynchronous job).
    The upload is deleted as soon as the text is back."""
    import boto3

    if not config.TEXTRACT_BUCKET:
        raise SystemExit("Set TEXTRACT_BUCKET (an S3 bucket in Sydney) to OCR scanned PDFs")
    s3 = boto3.client("s3", region_name=config.REGION)
    tx = boto3.client("textract", region_name=config.REGION)
    key = f"ocr-tmp/{uuid.uuid4()}/{path.name}"
    s3.upload_file(str(path), config.TEXTRACT_BUCKET, key)
    try:
        job = tx.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": config.TEXTRACT_BUCKET, "Name": key}}
        )["JobId"]
        while True:
            r = tx.get_document_text_detection(JobId=job)
            if r["JobStatus"] in ("SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"):
                break
            time.sleep(3)
        if r["JobStatus"] == "FAILED":
            raise RuntimeError(f"Textract failed on {path.name}")
        blocks = list(r["Blocks"])
        while r.get("NextToken"):
            r = tx.get_document_text_detection(JobId=job, NextToken=r["NextToken"])
            blocks.extend(r["Blocks"])
        return _lines_by_page(blocks)
    finally:
        s3.delete_object(Bucket=config.TEXTRACT_BUCKET, Key=key)


# --- Chunking and search ----------------------------------------------------------


def chunk_pages(pages: list[tuple[str, str, str]], size: int = 900, overlap: int = 150) -> list[Chunk]:
    """Split on blank lines and lines, keeping file and page with every chunk.
    Checklists are short lines, so this keeps related items together."""
    chunks = []
    for file, page, text in pages:
        lines = [ln.rstrip() for ln in re.split(r"\n", text) if ln.strip()]
        buf: list[str] = []
        for ln in lines:
            if sum(len(x) + 1 for x in buf) + len(ln) > size and buf:
                chunks.append(Chunk("\n".join(buf), {"file": file, "page": page}))
                # carry the last lines over for context
                keep, total = [], 0
                for x in reversed(buf):
                    total += len(x) + 1
                    if total > overlap:
                        break
                    keep.insert(0, x)
                buf = keep
            buf.append(ln)
        if buf:
            chunks.append(Chunk("\n".join(buf), {"file": file, "page": page}))
    return chunks


class KeywordRetriever:
    """Word-overlap search. Used for the offline demo and tests, and as a
    fallback; the real check uses embeddings (vector_retriever)."""

    def __init__(self, chunks: list[Chunk], k: int):
        self.chunks, self.k = chunks, k

    def invoke(self, query: str) -> list[Chunk]:
        q = tokens(query)
        scored = sorted(self.chunks, key=lambda c: len(q & tokens(c.page_content)), reverse=True)
        return scored[: self.k]


def vector_retriever(chunks: list[Chunk], k: int):
    """In-memory vector search with Titan embeddings: built for this check,
    gone when the script ends."""
    from langchain_core.documents import Document
    from langchain_core.vectorstores import InMemoryVectorStore

    from llm import get_embeddings

    store = InMemoryVectorStore(get_embeddings())
    store.add_documents([Document(page_content=c.page_content, metadata=c.metadata) for c in chunks])
    return store.as_retriever(search_kwargs={"k": k})
