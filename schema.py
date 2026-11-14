"""Data shapes. The LLM fills Candidate, TopicChoice and DocFinding through
structured output; the code fills everything that must be exact (sources,
pages, IDs, review stamps)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Columns of data/requirements.csv and data/candidates.csv, in order.
LIBRARY_COLUMNS = [
    "req_id",            # PRE-001; given when you accept a candidate
    "topic",             # PRE, CON or CTR (data/topics.json)
    "requirement",       # one plain-English sentence: who must do what
    "obligation",        # must | should
    "quote",             # verbatim words from the source that create the obligation
    "source",            # file name of the guidance (filled by code, never by the model)
    "page",              # page number in that file (filled by code)
    "url",               # where to download the source (you add it during review)
    "evidence_types",    # ids from data/evidence_types.json, separated by ';'
    "evidence_example",  # what proof looks like on the day, e.g. 'signed pre-start each shift for FEL-02'
    "applies_to",        # e.g. 'all NSW quarries', 'sites with conveyors'
    "status",            # draft | verified | rejected
    "verified_by",
    "verified_on",
    "notes",             # grounding flags, duplicate warnings, your comments
]
CANDIDATE_EXTRA = ["extract"]  # the source text shown to you in the review app


# --- Requirement extraction (step 7) -----------------------------------------


class Candidate(BaseModel):
    extract_n: int = Field(description="The [n] number of the extract this requirement comes from")
    quote: str = Field(
        description="The exact words from that extract that create the obligation, copied character for "
        "character, 1-2 sentences, under 350 characters"
    )
    requirement: str = Field(
        description="One plain-English sentence for a quarry manager: who must do what, e.g. "
        "'The operator must check each item of mobile plant before use each shift.'"
    )
    obligation: Literal["must", "should"] = Field(
        description="'must' if the extract states a legal duty (must, is required to, shall); "
        "'should' if it is guidance or a recommendation"
    )
    evidence_types: list[str] = Field(description="1-3 evidence type ids from the allowed list that would prove it")
    evidence_example: str = Field(description="What that proof looks like on a real site, in under 20 words")
    applies_to: str = Field(description="Which sites or activities it applies to, e.g. 'sites with conveyors'")


class CandidateList(BaseModel):
    candidates: list[Candidate] = Field(
        description="Specific, checkable requirements found in the extracts; empty if there are none"
    )


# --- Free pre-inspection check (step 9) ---------------------------------------


class TopicChoice(BaseModel):
    document_type: str = Field(description="What the document is, e.g. 'daily pre-start checklist for a loader'")
    topics: list[str] = Field(description="Ids of the topics this document is meant to cover")


class DocFinding(BaseModel):
    status: Literal["documented", "partly documented", "not found", "unclear"] = Field(
        description="'documented' only if the document clearly provides for the whole requirement; "
        "'partly documented' if it covers some of it; 'not found' if the excerpts don't address it; "
        "'unclear' if you can't tell"
    )
    excerpt_n: int = Field(description="The [n] of the site-document excerpt you quote, or 0 if none")
    quote: str = Field(description="Exact words copied from that excerpt that support the status, or '' if none")
    gap: str = Field(description="What is missing, in under 25 words, or '' if documented")
    fix: str = Field(description="One specific change to the document, in under 25 words, or '' if documented")
