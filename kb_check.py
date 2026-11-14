"""Check the guidance Knowledge Base returns sensible files and page numbers (VIBE_CODING step 5).

Asks one question per topic and prints, for each result, the file, page and the first
120 characters. Public guidance only: no customer documents are involved.
Run:  python kb_check.py
"""

from __future__ import annotations

import re
import sys

import config
from guidance import get_guidance_retriever, source_and_page

QUESTIONS = [
    "What must be checked on mobile plant such as loaders before each shift?",
    "How should conveyor tail pulleys be guarded?",
    "What must a quarry operator do before a contractor starts work on site?",
]


def snippet(text: str, n: int = 120) -> str:
    """First n characters on one line."""
    return re.sub(r"\s+", " ", text).strip()[:n]


def check(retriever=None, questions: list[str] = QUESTIONS) -> list[str]:
    """Print the results for each question. Returns 'file (question n)' for each result with no page."""
    retriever = retriever or get_guidance_retriever()
    missing = []
    for i, q in enumerate(questions, 1):
        docs = retriever.invoke(q)
        print(f"\n{i}. {q}  ({len(docs)} results)")
        for doc in docs:
            name, page = source_and_page(doc)
            print(f"   {name}  p.{page or '??'}  | {snippet(doc.page_content)}")
            if not page:
                missing.append(f"{name} (question {i})")
    return missing


def main() -> int:
    if config.REGION != "ap-southeast-2":
        print(f"Refusing to run: AWS_REGION is {config.REGION}, but this project uses ap-southeast-2 only.")
        return 1
    print(f"Searching {'Knowledge Base' if config.RAG_BACKEND == 'kb' else 'local index'} in {config.REGION}")
    try:
        missing = check()
    except Exception as err:  # noqa: BLE001  show any failure in plain English
        from smoke_test import explain

        print(f"FAILED. {explain(err)}")
        return 1
    if missing:
        print(f"\n{len(missing)} results have no page number: " + ", ".join(missing))
        print("Add pages during review (README 'Troubleshooting'); the validator refuses verified rows without one.")
        return 1
    print("\nEvery result has a page number.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
