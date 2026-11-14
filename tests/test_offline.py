"""Offline tests: no AWS, no LangChain needed.  Run:  python -m tests.test_offline"""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

import config  # noqa: E402
from grounding import is_grounded, match_score, similarity  # noqa: E402
from library import accept_candidate, load_evidence_types, load_library, load_topics, next_id, validate  # noqa: E402
from site_docs import KeywordRetriever, chunk_pages, load_folder  # noqa: E402
from tests.fakes import FakeDoc, FakeGuidanceRetriever, FakeLLM  # noqa: E402

FIXTURE = "tests/fixtures/requirements_fixture.csv"


def test_grounding():
    src = "The operator must ensure that\nmobile plant is inspected — before use ’each shift’."
    assert match_score("mobile plant is inspected - before use 'each shift'", src) == 1.0
    ok, score = is_grounded("mobile plant is inspected before each use", src, 0.9)
    assert not ok and score < 0.9, score
    assert is_grounded("mobile plant is inspectd before use", src, 0.9)[0]  # one typo is tolerated
    assert similarity("Contractors must be inducted", "All contractors must be inducted on site") > 0.4


def test_library_validation():
    topics, evidence = load_topics(), load_evidence_types()
    rows = load_library(FIXTURE)
    errors, warnings = validate(rows, topics, evidence)
    assert not errors, errors
    assert warnings  # fixture rows have no url
    assert next_id(rows, "PRE") == "PRE-005" and next_id(rows, "XYZ") == "XYZ-001"
    broken = [dict(rows[0], evidence_types="made_up", page="")]
    errors, _ = validate(broken, topics, evidence)
    assert any("made_up" in e for e in errors) and any("'page'" in e for e in errors)


def test_accept_requires_reviewer():
    lib = load_library(FIXTURE)
    cand = dict(lib[0], req_id="", status="draft")
    try:
        accept_candidate(cand, lib, reviewer="")
        raise AssertionError("should need a reviewer")
    except ValueError:
        pass
    row = accept_candidate(cand, lib, reviewer="Ray")
    assert row["req_id"] == "PRE-005" and row["status"] == "verified" and cand["status"] == "verified"


def test_extraction_grounding():
    import extract_requirements as ex

    extract = FakeDoc(
        "Conveyors must have guards fitted to all nip points. Guards should be inspected.",
        {"location": {"s3Location": {"uri": "s3://bucket/guide-plant.pdf"}},
         "source_metadata": {"x-amz-bedrock-kb-document-page-number": 12.0}},
    )
    topic = load_topics()[1]
    evidence = load_evidence_types()
    rows = ex.extract_topic(topic, FakeGuidanceRetriever([extract]), FakeLLM(), [], evidence, {})
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "guide-plant.pdf" and r["page"] == "12"   # from metadata, not the model
    assert r["evidence_types"] == "procedure" and "not_a_type" in r["notes"]
    # a model that alters the quote gets its row flagged as fuzzy or dropped, never silently kept
    rows = ex.extract_topic(topic, FakeGuidanceRetriever([extract]), FakeLLM(lie=True), [], evidence, {})
    assert not rows or "quote_fuzzy" in rows[0]["notes"]


def test_site_docs_chunking():
    pages, warnings = load_folder("sample_site_docs")
    assert len(pages) == 3 and not warnings
    chunks = chunk_pages(pages, size=200, overlap=60)
    assert all(c.metadata["file"] and c.metadata["page"] for c in chunks)
    hits = KeywordRetriever(chunks, 2).invoke("contractor induction sign in")
    assert hits[0].metadata["file"] == "contractor_induction.txt"


def test_check_end_to_end():
    import pre_inspection_check as pic

    out_root = tempfile.mkdtemp()
    try:
        out = pic.run("Test Quarry", "sample_site_docs", llm=FakeLLM(), retriever_factory=KeywordRetriever,
                      library_path=FIXTURE, out_root=out_root)
        findings = list(csv.DictReader(open(out / "findings.csv", newline="", encoding="utf-8")))
        assert {f["topic"] for f in findings} == {"PRE", "CON", "CTR"}
        allowed = {"documented", "partly documented", "not found", "needs review"}
        assert all(f["status"] in allowed for f in findings)
        # every quote reported as evidence is really in the documents
        corpus = "\n".join(t for _, _, t in load_folder("sample_site_docs")[0])
        for f in findings:
            if f["quote"]:
                assert f["quote"] in corpus, f["quote"]
        md = (out / "report.md").read_text(encoding="utf-8")
        assert "DRAFT" in md and "Test Quarry" in md and (out / "report.html").exists()

        # a model that invents evidence: everything it claims becomes 'needs review'
        out2 = pic.run("Liar Quarry", "sample_site_docs", topics_arg="CON", llm=FakeLLM(lie=True),
                       retriever_factory=KeywordRetriever, library_path=FIXTURE, out_root=out_root)
        f2 = list(csv.DictReader(open(out2 / "findings.csv", newline="", encoding="utf-8")))
        assert all(f["status"] == "needs review" and not f["quote"] for f in f2), f2

        # reviewer pass: fill reviewer_status, re-render, DRAFT banner goes
        path = out / "findings.csv"
        rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
        for r in rows:
            r["reviewer_status"] = r["status"] if r["status"] != "needs review" else "not found"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        pic.rerender(str(path))
        assert "DRAFT" not in (out / "report.md").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(out_root)


def test_offshore_model_refused():
    import pre_inspection_check as pic

    old = config.LLM_BACKEND
    config.LLM_BACKEND = "nvidia"
    try:
        pic.run("X", "sample_site_docs", library_path=FIXTURE)
        raise AssertionError("customer documents must not go to an offshore model")
    except SystemExit as e:
        assert "Bedrock" in str(e)
    finally:
        config.LLM_BACKEND = old


def test_smoke_test_offline():
    import smoke_test
    from llm import Meter
    from tests.fakes import FakeBedrockRuntime

    meter = Meter()
    assert smoke_test.check_claude(llm=FakeLLM(), meter=meter)
    assert meter.calls == 1 and meter.input_tokens == 900
    client = FakeBedrockRuntime(dims=1024)
    assert smoke_test.check_embedding(client=client) == (1024, 2)
    assert client.calls[0]["modelId"] == config.EMBED_MODEL_ID
    # refuses any region other than Sydney, before calling AWS
    old = config.REGION
    config.REGION = "us-east-1"
    try:
        assert smoke_test.main() == 1
    finally:
        config.REGION = old


def test_kb_check_offline():
    import kb_check

    kb = {"location": {"s3Location": {"uri": "s3://bucket/code-plant.pdf"}},
          "source_metadata": {"x-amz-bedrock-kb-document-page-number": 12.0}}
    no_page = {"location": {"s3Location": {"uri": "s3://bucket/guide.pdf"}}, "source_metadata": {}}
    retriever = FakeGuidanceRetriever([FakeDoc("Guard  the\ntail pulley.", kb), FakeDoc("No page here.", no_page)])
    assert kb_check.check(retriever, ["q1"]) == ["guide.pdf (question 1)"]
    assert kb_check.snippet("a\n\n b  c", 3) == "a b"


def test_blog_calendar_and_check():
    import datetime as dt

    import blog_tools as bt

    rows = bt.load_calendar()
    assert len(rows) == 30 and all(dt.date.fromisoformat(r["publish_date"]).weekday() == 1 for r in rows)
    assert bt.next_post(dt.date(2026, 11, 10), rows)["week"] == "1"
    assert bt.next_post(dt.date(2026, 11, 11), rows)["week"] == "2"
    assert bt.next_post(dt.date(2028, 1, 1), rows) is None

    footer = "This is a build log, not legal or safety advice."
    good = f"---\ntitle: T\n---\nThe site is [ADD: number] percent documented.\n\n{footer}\n"
    errors, warnings = bt.check_post(good, {"Smith Quarries"})
    assert not errors and any("placeholder" in w for w in warnings)
    bad = "---\ntitle: T\n---\nNow compliant! Call 0412 345 678 or a@b.com. Thanks Smith Quarries. Optimized.\n"
    errors, warnings = bt.check_post(bad, {"Smith Quarries"})
    joined = " ".join(errors)
    for word in ("compliant", "footer", "email", "phone", "validation log"):
        assert word in joined, (word, errors)
    assert any("optimise" in w for w in warnings)


def test_blog_github_pages_draft_and_publish():
    import datetime as dt

    import blog_tools as bt

    tmp = Path(tempfile.mkdtemp())
    try:
        site = tmp / "site"
        assert "_config.yml" in bt.init_site(site) and bt.init_site(site) == []  # second run changes nothing
        post = tmp / "p.md"
        footer = "This is a build log, not legal or safety advice."
        post.write_text(f'---\ntitle: My "first" post\nsubtitle: One line\ntags: AWS, Edge AI\nweek: 1\n---\n'
                        f"Body [ADD: number].\n\n{footer}\n", encoding="utf-8")
        out = bt.draft_file(post, site)
        assert out.parent.name == "_drafts" and not list((site / "_posts").glob("*.md"))  # nothing live
        text = out.read_text(encoding="utf-8")
        assert text.startswith("---\nlayout: post\n") and 'title: "My \\"first\\" post"' in text
        assert 'tags: ["AWS", "Edge AI"]' in text and "week:" not in text
        try:
            bt.draft_file(post, site)
            raise AssertionError("should not overwrite a draft")
        except RuntimeError:
            pass
        bt.draft_file(post, site, force=True)
        try:
            bt.publish_file(out, site)  # placeholder still there
            raise AssertionError("should refuse while [ADD: ...] remains")
        except RuntimeError as e:
            assert "placeholder" in str(e)
        out.write_text(text.replace("[ADD: number]", "42"), encoding="utf-8")
        live = bt.publish_file(out, site, today=dt.date(2026, 11, 10))
        assert live.name == "2026-11-10-my-first-post.md" and live.parent.name == "_posts" and not out.exists()
        try:
            bt.draft_file(post, tmp / "no-site")
            raise AssertionError("needs a site folder")
        except RuntimeError as e:
            assert "site-init" in str(e)
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} passed")
