# Blog style guide

Every Tuesday post is a build log that earns trust: a real problem from NSW quarries, what I built,
the numbers, and what I learned. The goal is to be worth sharing, and to show the value of me and the
company without hype.

## Who reads it

- Quarry managers, site senior executives and WHS coordinators (the customers).
- Engineers and hiring managers at NVIDIA, AWS and AI companies (the career audience).
- Write so the first group understands every paragraph and the second group trusts every number.

## Shape of a post (800 to 1,300 words)

1. **Hook (2 to 3 sentences):** the problem on a real site, or the surprising result. Lead with the number.
2. **What I built this week:** plain English first, then one short technical paragraph.
3. **The numbers:** a Markdown table where there are 3 or more values. Only numbers from
   `blog/progress.md` or `python blog_tools.py facts`. Missing number: write `[ADD: what is missing]`.
4. **What surprised me / what went wrong:** 3 to 5 bullets. Honest failures make posts shareable.
5. **Why it matters for a quarry:** one short paragraph in site language (inspections, evidence,
   pre-starts, isolation), not AI language.
6. **What's next:** one or two sentences on next week, from the calendar.
7. **Call to action:** one line. Rotate: try the free pre-inspection check, follow the series, star the
   repo, or reply with your own experience.
8. **Footer (always):** *This is a build log, not legal or safety advice. Always check obligations
   with the NSW Resources Regulator and your own advisers.*

## Voice

- First person, plain English, Australian spelling (organise, licence, colour, analyse, metre).
- Short sentences (under 25 words). Short paragraphs (3 sentences at most).
- Specific beats impressive: "caught 9 of 11 planted gaps" not "highly accurate".
- No emoji, no "game-changer", "revolutionise", "unlock", "delve", "in today's fast-paced world".
- Headings as plain statements, not questions.

## Hard rules (the check in `blog_tools.py` enforces most of these)

- **Never say a site or document is "compliant"**, and never promise compliance. Use: documented,
  partly documented, not found, needs review.
- **Never invent a number, quote, name or result.** Gaps become `[ADD: ...]` placeholders.
- **No customer information:** no quarry names, people, emails, phone numbers or document contents
  from free checks or pilots, unless `progress.md` says the person agreed in writing to be named.
  Use "a small quarry in the Hunter" style descriptions at most.
- **No secrets:** no keys, account IDs, Knowledge Base or guardrail IDs, bucket names.
- Name the tools honestly (Amazon Bedrock, Claude, NVIDIA NIM, Jetson). No claims of partnership or
  endorsement by NVIDIA, AWS or Anthropic.
- Link the public repo or demo when one exists for that week.

## LinkedIn teaser (separate file)

120 to 200 words: the hook, 3 short lines with the key numbers, one question to the reader, and
`[LINK]` where the blog post URL goes. Up to 3 hashtags, for example #QuarrySafety #EdgeAI #AWS.
