# Building feature 1 with an AI coding agent

You steer and check; the agent writes code and runs commands. The agent reads its rules from
`CLAUDE.md` (keep customer data in Australia, never weaken the quote checks, only you verify rows,
ask before any AWS change). Paste the prompts below one at a time and check the "done when" line
before moving on.

## 0. One-off setup on your Windows PC (about 45 min, you)

Open **PowerShell** (not as Administrator) and run:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install Amazon.AWSCLI
winget install Microsoft.VisualStudioCode      # optional, to read the code
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   # lets the Python environment activate
```

Close and reopen PowerShell, then:

```powershell
python --version        # 3.12.x
git --version
aws --version
aws configure           # paste the bedrock-dev access key and secret from week 1; region ap-southeast-2; output json
aws sts get-caller-identity   # shows your account and the bedrock-dev user
```

Type your keys into `aws configure` yourself. Never paste keys into a chat with any AI.

**Pick your agent:**

- **Easiest: the Claude desktop app's Code tab.** You already have the app. Open **Code**, choose
  this folder as the project, and paste the prompts there.
- **Terminal: Claude Code.** In PowerShell: `irm https://claude.ai/install.ps1 | iex`, open a new
  window, `cd` to this folder and run `claude`. Needs a Pro, Max, Team or Enterprise plan.
- Cursor or Amazon's Kiro also work: point them at `CLAUDE.md` as the project rules.

Keep the agent asking before it runs commands (the default). Approve file edits freely; read every
AWS command before you approve it.

## 1. Orient (5 min)

> Read CLAUDE.md, README.md and VIBE_CODING.md. In 5 bullets, tell me what this project does and how
> the pieces fit. Then list everything you will need from me for README steps 1–3. Don't change any
> files yet.

**Done when:** the summary matches the README's architecture diagram and the list includes the
Knowledge Base ID and bucket names.

## 2. Local environment and offline tests (15 min)

> Set up the project on this Windows machine: create a .venv with Python 3.12, install
> requirements.txt, copy .env.example to .env (leave the values for me), run the offline tests and
> the demo, and open reports/demo-ridgeview-quarry/report.html in my browser. If anything fails,
> explain why before fixing it.

**Done when:** "7 passed", and the demo report opens with a DRAFT banner.

## 3. Prove AWS works (15 min)

> Write `smoke_test.py` that, using my default AWS profile in ap-southeast-2: (1) calls Claude Haiku
> 4.5 through the inference profile in config.py with "Reply with OK", (2) embeds the word "quarry"
> with Titan V2 and prints the vector length, (3) prints the total tokens used. Don't print any
> credentials. Run it.

**Done when:** you see "OK" and a vector length (1024 by default). If it says `AccessDenied` or that
the model isn't available, that's a **you** step: in the Bedrock console (Sydney), open Claude Haiku
4.5 in the playground once; if it asks for Anthropic's first-time use case form, submit it, then
rerun. Also check the IAM policy from README step 2.

## 4. Guidance into S3 (30 min, together)

You: download 10+ PDFs into `guidance\` (see `guidance\SOURCES.md`). Then:

> For every PDF in guidance\, add a row to guidance\sources.csv (fill title, publisher, jurisdiction
> and doc_type from the first page; leave url for me where you can't tell). Run
> `python ingest_guidance.py --kb-metadata`. Then propose the AWS CLI commands to create two
> buckets in ap-southeast-2 (`<my-initials>-quarry-guidance` and `<my-initials>-quarry-ocr`), block
> public access on both, add a 1-day expiry lifecycle rule to the OCR bucket, and sync the PDFs and
> metadata files to the guidance bucket. Show me the commands and wait for my yes.

**Done when:** `aws s3 ls s3://<bucket>/` lists each PDF with its `.metadata.json`.

## 5. Knowledge Base and guardrail (45 min, you in the AWS console)

Do README step 3.5–3.6 (create the Knowledge Base with S3 Vectors, then sync) and step 5 (guardrail).
Paste the Knowledge Base ID, guardrail ID and OCR bucket name into `.env`. Then:

> Write `kb_check.py` that runs 3 questions through get_guidance_retriever() and prints, for each
> result, the file, page and the first 120 characters. Run it and tell me if any pages are missing.

**Done when:** results show sensible files and page numbers.

## 6. Draft the library (20 min)

> Run extract_requirements.py for all topics. Then give me a table per topic: candidates kept,
> dropped for bad quotes, flagged as duplicates. Don't accept or edit any rows.

## 7. Review (about 3 hours, you)

`streamlit run review_app.py` with the source PDFs open beside it. This is your part: the agent must
not do it (CLAUDE.md rule 4). If a topic comes up short:

> Run extract_requirements.py --topic CON again and summarise what's new.

Then:

> Run validate_library.py --min 30 and explain each error in plain English, with the row to fix.
> Don't fix requirement rows yourself.

## 8. Ask the library and test the guardrail (20 min)

> Run ask_library.py with these 6 questions and show the answers in a table with a "blocked?"
> column: [2 real quarry questions], [3 off-topic questions], [1 question containing a phone
> number]. Tell me if the guardrail didn't trigger where it should.

## 9. Run the free check and score it (45 min)

> Run the pre-inspection check on sample_site_docs for client "Ridgeview Quarry". Then compare the
> findings with the 11 planted gaps in README step 10 and write reports\week2_eval.md: a table of
> each planted gap, caught or missed, and the finding that caught it. Don't fill reviewer_status.

You: review every row in `findings.csv`, then:

> Re-render reports\ridgeview-quarry\findings.csv and open the report.

**Done when:** the report has no DRAFT banner, and you've written down gaps caught, rows changed and
minutes spent.

## 10. Save it to GitHub (15 min)

> Initialise git, check that .gitignore excludes .env, clients, index, guidance PDFs and customer
> reports, show me `git status`, then commit with a clear message. Create a **private** GitHub repo
> called quarry-compliance and push (use the GitHub CLI if installed; otherwise tell me the clicks).

## When something breaks

> Here's the error: [paste]. Find the cause, explain it in two sentences, propose the smallest fix,
> and wait for my yes if it touches AWS, CLAUDE.md rules or more than one file.

## Good habits

- One prompt, one outcome. If the agent wanders, say "stop, undo that, and do only X".
- Ask "how would we know this works?" before accepting new code; make it add a test.
- Read every AWS command. Anything with `delete`, `put-bucket-policy` or `create` gets a second look.
- Commit after each step that works, so you can roll back.
