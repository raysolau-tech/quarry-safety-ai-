# Project rules for AI coding agents

This repo is feature 1 of a commercial quarry compliance product for NSW, Australia: a hand-checked
**requirements library** and a **free pre-inspection check** that compares a quarry's documents with
it. Read README.md for the architecture before changing anything.

## The owner

A product leader building his own edge AI company, on Windows 11 with PowerShell, learning AWS,
LangChain and RAG as he builds. Explain what you're about to do in plain English, one step at a
time, and say why. Prefer small, reviewable changes over big rewrites.

## Commands

- Activate the environment: `.venv\Scripts\Activate.ps1`
- Offline tests (no AWS): `python -m tests.test_offline`; run after every code change
- Offline demo: `python pre_inspection_check.py --demo`
- Validate the library: `python validate_library.py --min 30`
- Settings live in `.env` (loaded by `config.py`). Never print, log or commit `.env` or AWS keys.

## Rules that protect the product (never break these without asking)

1. **Customer documents** (`clients/`, `reports/<client>/`) only ever go to Claude on Amazon Bedrock
   through the `au.` inference profile in `ap-southeast-2`. Never send them to any other model or API,
   never upload them to the Knowledge Base or any S3 bucket other than the temporary Textract path,
   and never paste their contents into chat output beyond short quotes.
2. **The model never writes sources or page numbers.** They come from search metadata in code.
3. **Every quote is checked against its source text** (`grounding.py`). Don't remove or weaken a
   check, and don't lower `QUOTE_MATCH` below 0.85, without asking first.
4. **Only the owner verifies requirements**, in `review_app.py`. Never set `status=verified`,
   `verified_by` or `reviewer_status` yourself, and never edit `data/requirements.csv` rows by hand
   unless asked.
5. **The report never says "compliant".** Statuses are: documented, partly documented, not found,
   needs review. Keep the not-legal-advice note.
6. **AWS:** region `ap-southeast-2` only. Show every AWS command that creates, changes or deletes a
   resource, or costs money, and wait for a yes before running it. Never create OpenSearch
   Serverless collections. Never print secret values.
7. **Git:** never commit `.env`, `clients/`, `index/`, guidance PDFs or customer reports
   (`.gitignore` covers these; don't change it to let them in).

## Style

- Python 3.11+, type hints, small functions, LangChain and AWS imports inside functions so tests run
  offline.
- Add or update a test in `tests/test_offline.py` for any new behaviour; use the fakes in
  `tests/fakes.py`, not real AWS.
- Report text: plain English, Australian spelling, short sentences, written for a busy quarry manager.

## When something fails

Read the full error, find the cause, explain it in two sentences, propose the smallest fix, and wait
for a yes if it touches AWS, the rules above, or more than one file.
