# Feature 1: requirements library and free pre-inspection check

> Building this with an AI coding agent? Start with `VIBE_CODING.md`. The agent reads its rules from `CLAUDE.md`.

The first commercial feature of the quarry compliance product, built on AWS with LangChain and RAG.

- **Requirements library**: NSW quarry requirements, each one quoted from its source with the page,
  plus the evidence that would prove it on site. Checked by you, row by row. This is the asset
  behind everything that follows: week 3's evidence-backed compliance checks site evidence against
  these rows.
- **Free pre-inspection check**: a quarry sends one checklist or procedure; you send back a report
  showing, for each requirement, whether their document covers it, the exact words relied on, a
  suggested fix, and what an inspector may ask to see. In the product it becomes customer
  onboarding; this week it's the concierge test of H1–H4.

## Architecture

```
PUBLIC GUIDANCE (shared)                       CUSTOMER DOCUMENTS (one check at a time)
guidance/*.pdf + sources.csv                   clients/<name>/  (PDF, Word, text, photos)
   │  S3 bucket (Sydney)                          │  Textract in Sydney for scans (--ocr)
   ▼                                              ▼
Bedrock Knowledge Base                          in-memory vector index (Titan V2),
(Titan V2 embeddings, S3 Vectors)               deleted when the run ends
   │  Retrieve                                    │
   ▼                                              ▼
extract_requirements.py ──► candidates.csv     pre_inspection_check.py
 Claude drafts rows; code checks each quote      for each verified requirement: find passages →
 is really in the extract and fills source       Claude judges → code checks the quote is in the
 and page itself                                 document, else "needs review"
   │                                              │
   ▼                                              ▼
review_app.py (you accept, edit, reject)        findings.csv + DRAFT report → you review every
   │                                             row → final report (HTML → PDF)
   ▼
data/requirements.csv  ◄── the source of truth, in Git
   │
   ├──► validate_library.py (CI from week 4)
   └──► ask_library.py (RAG over verified rows + Bedrock guardrail)
```

### Why this shape, and not "chat with the regulations"

| Decision | Choice | Why |
| --- | --- | --- |
| Where requirements live | A hand-checked CSV in Git, not a vector store | Every row must be exact and traceable to a page. RAG helps you **write** the library; it doesn't replace it. Competitors that only compare documents with legislation at run time (MineGuard, Mitti) can't show evidence per requirement. |
| Who fills source and page | The code, from search metadata | Models make up citations. The model only gives an extract number; the code looks up the file and page. |
| Hallucination guard | Every quote checked against its source text | A requirement or a piece of "evidence" whose quote isn't in the text is dropped or marked "needs review", never reported. This is how you keep the false "met" rate under 2% (week 4 gate). |
| Guidance search | Bedrock Knowledge Base with **S3 Vectors** | Supported in Sydney, almost no cost when idle. Avoid OpenSearch Serverless for now: it bills hourly whether you use it or not. |
| Customer documents | Kept out of the shared Knowledge Base; indexed in memory per check | No risk of one quarry's documents showing up in another's report, and an easy deletion promise. |
| Model | Claude Haiku 4.5 via the `au.` profile | Processing stays in Sydney and Melbourne. The code refuses to send customer documents to any other model. |
| Scanned forms | Amazon Textract in Sydney | Many quarry checklists are paper; a photo is often what you'll get. |
| Interface | Command line + a Streamlit review app, no web app yet | It's a concierge test: you run every check and review it. Build the self-serve version only after the week 4 go/no-go. |

**Newer option to try later:** Amazon Bedrock **Managed Knowledge Base** (generally available June
2026, offered in Sydney) runs storage, hybrid search and re-ranking for you. Standalone re-ranking
models aren't offered in Sydney, so this is the easiest way to get re-ranking in-region. Per-GB and
per-query prices weren't published when this kit was written, so check the pricing page first. In
week 4, run your evaluation set against both and keep whichever does better for the money.

**After a "go" in week 4 (production path, don't build yet):** requirements and findings in a
database (Aurora PostgreSQL Serverless or DynamoDB) with the same columns; checks run as Step
Functions jobs triggered by uploads to a per-customer S3 prefix; Cognito sign-in; API Gateway and
Lambda; one Knowledge Base for public guidance, with metadata filters by jurisdiction.

## What it costs

- Knowledge Base with S3 Vectors and 10–20 PDFs: cents to embed, near zero when idle.
- Extracting candidates for three topics: about 10–20 Claude Haiku calls, well under US$1.
- One pre-inspection check (about 15 requirements): about 16 calls, a few cents. Every run prints
  its token count and cost.
- Textract: about US$1.50 per 1,000 pages for plain text detection; check current prices.

Prices change; check the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) and update
`PRICE_IN` and `PRICE_OUT` in `config.py`.

## Step by step

Times match the week 2 sessions in your plan.

### Evening 1 (about 1.5 hours): set up and build the Knowledge Base

**Step 1. Install and see it work offline (15 min)**

```bash
cd requirements-library
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows PowerShell; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # macOS/Linux: cp .env.example .env
python -m tests.test_offline          # 7 tests, no AWS needed
python pre_inspection_check.py --demo # writes reports/demo-ridgeview-quarry/report.html
```

Open the demo report to see what you'll send to quarries. A fake model wrote it, so the findings are
nonsense, but the layout and flow are real.

**Step 2. Permissions (10 min)**

In IAM, replace your `bedrock-dev` user's inline policy with this, putting your account ID and bucket
names in:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Bedrock",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Retrieve", "bedrock:ApplyGuardrail"],
      "Resource": "*"
    },
    {
      "Sid": "Textract",
      "Effect": "Allow",
      "Action": ["textract:DetectDocumentText", "textract:StartDocumentTextDetection", "textract:GetDocumentTextDetection"],
      "Resource": "*"
    },
    {
      "Sid": "Buckets",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::YOUR-GUIDANCE-BUCKET", "arn:aws:s3:::YOUR-GUIDANCE-BUCKET/*",
        "arn:aws:s3:::YOUR-OCR-BUCKET", "arn:aws:s3:::YOUR-OCR-BUCKET/*"
      ]
    }
  ]
}
```

Create the Knowledge Base itself from the console while signed in as your admin user (it needs to
create a service role); the policy above is for running the kit.

**Step 3. Guidance into a Knowledge Base (1 hour)**

1. Download 10+ PDFs into `guidance/` (see `guidance/SOURCES.md`) and add a row for each to
   `guidance/sources.csv` (file name, title, publisher, jurisdiction, doc type, URL).
2. Write the metadata files: `python ingest_guidance.py --kb-metadata`
3. Create two S3 buckets in **Asia Pacific (Sydney)**: one for guidance, one for temporary OCR files.
   On the OCR bucket, add a lifecycle rule that deletes objects after 1 day, as a safety net.
4. Upload the PDFs **and** their `.metadata.json` files to the guidance bucket:
   `aws s3 sync guidance/ s3://YOUR-GUIDANCE-BUCKET/ --exclude "*" --include "*.pdf" --include "*.metadata.json"`
5. Bedrock console → **Knowledge Bases → Create → Knowledge Base with vector store**. Data source: the
   guidance bucket. Embeddings: **Titan Text Embeddings V2**. Vector store: **Quick create → Amazon S3
   Vectors**. Leave chunking on default.
6. Create it, then **Sync** the data source. When it finishes, test in the console:
   "How should conveyor tail pulleys be guarded?" Check that answers show the right file and page.
7. Paste the Knowledge Base ID into `.env` (`KNOWLEDGE_BASE_ID=...`). `config.py` loads `.env` automatically.

No Knowledge Base yet? Set `RAG_BACKEND=faiss` in `.env` and run `python ingest_guidance.py --faiss` to work
locally, and move to the Knowledge Base later.

### Evening 2 (about 1.5 hours): guardrail and the IQA webinar

**Step 4. Attend the IQA webinar (10 Nov)** and write down 3 pains people mention. They're material
for your offer and your call script.

**Step 5. Create the guardrail (45 min)**

Bedrock console → **Guardrails → Create guardrail**:

- **Denied topic** "Off-topic": "Anything not about workplace health and safety, mining or quarry
  operations, or compliance." Add samples such as "Write me a poem" and "What's a good stock to buy?"
- **Sensitive information filters**: mask phone numbers, email addresses and names; block credit
  card numbers and Australian tax file numbers if offered.
- **Blocked messaging**: "I can only help with quarry safety and compliance questions."
- Create it, test 5 off-topic and personal-data prompts in the console's test panel, then copy the
  guardrail ID into `.env` as `GUARDRAIL_ID`. The kit applies it to `ask_library.py`.

### Weekend block (5–6 hours): build the library and run the check

**Step 6. Draft the candidates (20 min)**

```bash
python extract_requirements.py              # all three topics
```

For each topic it runs 5 searches, sends the extracts to Claude in batches of 5, and keeps only
candidates whose quote is really in the extract. Watch the "dropped" lines: they're the model
making things up and the code catching it. Output: `data/candidates.csv`.

**Step 7. Review every candidate (about 3 hours: this is the work that makes it sellable)**

```bash
streamlit run review_app.py      # set REVIEWER=Your Name in .env first
```

For each draft, open the source PDF at the page shown and check:

- The quote is word for word what the page says (fix the page number if the PDF viewer shows a different one).
- The requirement says the same as the quote, in plain English. Rewrite it if not.
- "must" only for legal duties (regulation, "must"/"is required to"); "should" for guidance.
- The evidence types and example are what you'd actually ask a quarry to show.
- Reject background text, duplicates, and anything that can't be checked on a site.

Aim for 10+ verified rows per topic (30+ in total). Run `python extract_requirements.py --topic CON`
again if a topic is short; it skips requirements already in the library.

**Step 8. Validate (5 min)**

```bash
python validate_library.py --min 30
```

Fix every error. Note the line "Rows a camera or sensor could help prove": that's where your edge AI
product earns its place.

**Step 9. Ask the library and test the guardrail (20 min)**

```bash
python ask_library.py "What do we need to check before using a loader each shift?"
python ask_library.py "What's the best recipe for scones?"          # should be blocked
python ask_library.py "Call John Smith on 0400 123 456 about the audit" # phone number masked or blocked
```

Record how many of 5 off-topic and personal-data prompts were handled (target 5 of 5), for your week 2 KPI.

**Step 10. Run the check on the sample documents (30 min)**

```bash
python pre_inspection_check.py --client "Ridgeview Quarry" --docs sample_site_docs
```

The three sample documents have planted gaps. Count how many the draft report catches:

| Document | Planted gaps |
| --- | --- |
| Loader pre-start checklist | No brakes, steering, seat belt, reversing alarm or fire suppression items; no defect tagging or taking plant out of service; nothing on operator competency |
| Contractor procedure | No induction content; no check of licences, competency or insurance; no SWMS; no supervision |
| Conveyor clean-up procedure | Stops the belt from the control room but no isolation or personal lock; guards checked only "when someone notices"; no pull-wire tests; last reviewed 2019 |

Then do the review pass you'll do for real customers: open `reports/ridgeview-quarry/findings.csv`,
fill `reviewer_status` (documented, partly documented, not found or needs review) and, where you
disagree, `reviewer_note` for every row, and re-render:

```bash
python pre_inspection_check.py --render reports/ridgeview-quarry/findings.csv
```

Open `report.html` in a browser and print it to PDF. The DRAFT banner disappears once every row has
been reviewed. Write down: planted gaps caught out of 11, rows you changed, minutes spent reviewing.
Those are your first evaluation numbers.

**Optional (NVIDIA proof point, 20 min).** Public guidance only:
`pip install langchain-nvidia-ai-endpoints`, set `LLM_BACKEND=nvidia` and `NVIDIA_API_KEY=nvapi-...` in `.env`,
copy `data/candidates.csv` aside, rerun `extract_requirements.py --topic PRE` and compare how many
candidates each model had dropped for invented quotes. That "quote grounding rate" by model is a
good metric for a post. The check script refuses this setting for customer documents, because the
hosted NVIDIA API runs outside Australia.

### Short session (about 1 hour): make the offer

**Step 11. Send the offer**

1. Fill your details into `offer/free_check_offer.md` and `offer/data_handling.md`; export both to PDF.
2. Post the LinkedIn post and send 15 messages from `offer/outreach_messages.md`.
3. Start `offer/validation_log.csv` (one row per person; columns map to H1–H4).

## When a quarry sends a document

1. Make sure they've had the data handling note.
2. Save the files in `clients/<name>/` only (it's in `.gitignore`; never upload it to the Knowledge Base).
3. Run the check. Add `--ocr` for scans or photos, and `--topics PRE` to pick the topic yourself if
   the automatic choice is wrong.
4. Review every row in `findings.csv` and re-render. Never send a DRAFT.
5. Send the PDF within 48 hours, book the 20-minute call (`offer/call_script.md`), and log it.
6. Write the deletion date in the log, and delete `clients/<name>/` and `reports/<name>/` on that date.

## Troubleshooting

- **No page numbers from the Knowledge Base.** Pages come from the PDF parser; if they're blank, add
  them during review. The validator refuses verified rows without a page.
- **`AccessDeniedException`.** Check the policy in step 2, that the region is `ap-southeast-2`, and
  that Claude Haiku 4.5 and Titan V2 work in the Bedrock console's playground.
- **Guardrail argument error.** Your `langchain-aws` version may name the setting differently; check
  `ChatBedrockConverse` in its docs and adjust `get_llm()` in `llm.py`.
- **"Model output didn't match …".** Rerun; if it repeats, lower `EXTRACTS_PER_CALL` in `config.py`.
- **Many "needs review" rows.** The model is quoting loosely. Check the passages it was given (raise
  `SITE_TOP_K`) before lowering `QUOTE_MATCH`.

## What comes next

- **Week 3:** the simulated evidence events use the same `evidence_types` ids, so the coverage agent
  can join each requirement to the evidence that proves it.
- **Week 4:** `validate_library.py` and the check's numbers go into the evaluation set and CI, with the
  false "met" gate.

---

The test library in `tests/fixtures/` and the Ridgeview documents are fictional. Not legal or safety advice.
