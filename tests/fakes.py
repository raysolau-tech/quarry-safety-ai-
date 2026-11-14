"""Fake model, retriever and documents, so the kit runs offline (--demo and tests).
The fake model uses word overlap, not intelligence: its findings are not real."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from grounding import tokens
from schema import Candidate, CandidateList, DocFinding, TopicChoice

TOPIC_WORDS = {
    "PRE": {"pre", "start", "loader", "tyres", "machine", "hydraulic", "engine"},
    "CON": {"conveyor", "belt", "pulley", "spillage", "guards"},
    "CTR": {"contractor", "contractors", "induction", "visitor"},
}
STOP = {"must", "the", "and", "each", "before", "with", "for", "are", "may", "should", "only", "use"}


@dataclass
class FakeMessage:
    content: str = ""
    usage_metadata: dict = field(default_factory=lambda: {"input_tokens": 900, "output_tokens": 120})
    response_metadata: dict = field(default_factory=dict)


@dataclass
class FakeDoc:
    page_content: str
    metadata: dict = field(default_factory=dict)


def _numbered(text: str) -> dict[int, str]:
    """Split '[1] (...)\\nbody\\n\\n[2] ...' into {1: body, 2: body}."""
    parts = re.split(r"^\[(\d+)\][^\n]*\n", text, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


class _Runner:
    def __init__(self, schema, lie: bool):
        self.schema, self.lie = schema, lie

    def invoke(self, messages):
        human = messages[-1][1]
        parsed = getattr(self, f"_{self.schema.__name__}")(human)
        return {"raw": FakeMessage(), "parsed": parsed, "parsing_error": None}

    def _TopicChoice(self, human):
        doc = tokens(human.split("Document:", 1)[-1])
        chosen = [t for t, words in TOPIC_WORDS.items() if len(doc & words) >= 2]
        return TopicChoice(document_type="site document", topics=chosen)

    def _DocFinding(self, human):
        req_line = human.split("\n", 1)[0]
        req = tokens(req_line.split(":", 1)[-1]) - STOP
        best, best_n, best_score = "", 0, 0
        for n, body in _numbered(human.split("excerpts:", 1)[-1]).items():
            for line in body.splitlines():
                score = len(req & (tokens(line) - STOP))
                if score > best_score:
                    best, best_n, best_score = line.strip(), n, score
        if self.lie:  # a model that invents evidence: grounding must catch it
            return DocFinding(status="documented", excerpt_n=1, quote="Isolation locks are applied by every worker.", gap="", fix="")
        if best_score >= 2:
            return DocFinding(status="partly documented", excerpt_n=best_n, quote=best,
                              gap="Only part of the requirement is written down.", fix="Add the missing steps and who signs off.")
        return DocFinding(status="not found", excerpt_n=0, quote="",
                          gap="The document doesn't address this.", fix="Add a step covering this requirement.")

    def _CandidateList(self, human):
        out = []
        for n, body in _numbered(human.split("Extracts:", 1)[-1]).items():
            for sentence in re.split(r"(?<=\.)\s+", body):
                if " must " in f" {sentence} ":
                    quote = sentence.strip() if not self.lie else sentence.strip() + " Always."
                    out.append(Candidate(extract_n=n, quote=quote, requirement=sentence.strip(), obligation="must",
                                         evidence_types=["procedure", "not_a_type"], evidence_example="Written procedure",
                                         applies_to="all quarries"))
                    break
        return CandidateList(candidates=out)


class FakeLLM:
    def __init__(self, lie: bool = False):
        self.lie = lie

    def with_structured_output(self, schema, include_raw: bool = False, **kwargs):
        return _Runner(schema, self.lie)

    def invoke(self, messages):
        return FakeMessage(content="[PRE-001] Fake answer.")


class FakeBedrockRuntime:
    """Stands in for boto3's bedrock-runtime client: returns a Titan-style embedding."""

    def __init__(self, dims: int = 1024):
        self.dims = dims
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs):
        import io
        import json

        self.calls.append(kwargs)
        body = {"embedding": [0.0] * self.dims, "inputTextTokenCount": 2}
        return {"body": io.BytesIO(json.dumps(body).encode())}


class FakeGuidanceRetriever:
    """Returns fixed guidance extracts with Knowledge Base-style metadata."""

    def __init__(self, docs: list[FakeDoc]):
        self.docs = docs

    def invoke(self, query):
        return self.docs
