"""Checks that a quote the model gives really appears in the source text.

This is the main defence against invented requirements and invented evidence:
the model can paraphrase in the 'requirement' column, but the 'quote' must be
found in the text it came from, or the row is flagged."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_REPLACE = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ", "­": "",
}


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    text = re.sub(r"-\s*\n\s*", "", text)  # words hyphenated across PDF lines
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def match_score(quote: str, source: str) -> float:
    """1.0 = found word for word (after normalising); otherwise the best fuzzy
    match of the quote against any same-length window of the source."""
    q, s = normalise(quote), normalise(source)
    if not q:
        return 0.0
    if q in s:
        return 1.0
    n = len(q)
    if n > len(s):
        return SequenceMatcher(None, q, s).ratio()
    step = max(1, n // 6)
    best = 0.0
    for i in range(0, len(s) - n + 1, step):
        r = SequenceMatcher(None, q, s[i : i + n]).ratio()
        if r > best:
            best = r
            if best > 0.99:
                break
    return best


def is_grounded(quote: str, source: str, threshold: float) -> tuple[bool, float]:
    score = match_score(quote, source)
    return score >= threshold, round(score, 3)


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", normalise(text)) if len(w) > 2}


def similarity(a: str, b: str) -> float:
    """Word-overlap (Jaccard) similarity, used to flag likely duplicates."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
