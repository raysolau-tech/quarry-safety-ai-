---
title: I tested 3 AI models on 20 quarry safety questions: quality, speed and cost
subtitle: "One model scored [ADD: X/5 average quality] at [ADD: X cents] per answer. Here's the table."
tags: AWS, Generative AI, Edge AI, Mining, Safety
week: 1
---

> NOTE FOR OWNER: Week 1 numbers aren't in progress.md yet — every result below is a placeholder. Run the comparison script, paste results/summary.md into blog/progress.md Week 1, then ask me to fill the gaps.

I'm building an AI compliance tool for NSW quarries. Before writing a line of product code, I wanted to know which model a small business should actually use — not on a generic benchmark, but on 20 real quarry safety questions scored against the NSW Resources Regulator guidance.

This is week 1 of a 30-week build log. Every post has real numbers or says why they're missing.

## The test

Three models, 20 questions, one scoring rubric:

- **[ADD: Model 1]** — via Amazon Bedrock, Sydney region (`au.` inference profile)
- **[ADD: Model 2]** — via Amazon Bedrock, Sydney region
- **[ADD: Model 3]** — via NVIDIA NIM on build.nvidia.com

The 20 questions cover mobile plant pre-starts, conveyor guarding and contractor management — the three topics I'm building the requirements library around first. Each answer was scored against the NSW Resources Regulator's guidance, not from memory:

| Score | Meaning |
| --- | --- |
| 5 | Correct, specific, names the right source |
| 4 | Correct but vague |
| 3 | Partly correct |
| 2 | Generic or mostly wrong |
| 1 | Wrong or unsafe |

## The results

| Model | Avg quality (1–5) | Avg latency (s) | Cost per answer (US$) | Total run cost |
| --- | --- | --- | --- | --- |
| [ADD: Model 1] | [ADD] | [ADD] | [ADD] | [ADD] |
| [ADD: Model 2] | [ADD] | [ADD] | [ADD] | [ADD] |
| [ADD: Model 3] | [ADD] | [ADD] | [ADD] | [ADD] |

Total cost for 60 answers: [ADD: US$X.XX]

## What surprised me

- [ADD: surprising finding 1 — e.g. the cheapest model scored closest on factual questions]
- [ADD: surprising finding 2 — e.g. latency gap between cloud models was larger than expected]
- [ADD: surprising finding 3 — e.g. a specific question type where all models struggled]
- Keeping the data processing in Sydney (the `au.` inference profile) added no latency penalty worth measuring.

## Why this matters for a quarry

A site senior executive asking "what does the regulation say about pre-start inspections?" needs a correct answer, not a fast one. The quality column is the one that matters. Cost matters too — a small quarry running daily checks can't absorb the per-call cost of a frontier model on every routine question.

The good news: the gap between the most and least expensive models in this test was [ADD: X times], but the quality gap was [ADD: much smaller / significant]. That's the number that shapes the product's default.

## What's next

Week 2: I build the requirements library — 30+ verified requirements from public NSW guidance, each quoted from its source page. Then I run a free pre-inspection check on three sample site documents to test whether the library actually finds gaps. If you manage a quarry and want a free check, reply here or on [LinkedIn](https://www.linkedin.com/in/[ADD: your LinkedIn handle]).

The code is at [ADD: GitHub repo link].

---

*This is a build log, not legal or safety advice. Always check your obligations with the NSW Resources Regulator and your own advisers.*
