# How we handle your documents (free pre-inspection check)

Send this to anyone before they send you a document. Keep the promises small and keep them.

**What we collect.** Only the documents you choose to send, and your contact details so we can send
the report. If a document contains people's names or signatures, you can blank them out first; the
check doesn't need them.

**Where it's processed.** On our computer and in Amazon Web Services in Sydney. The AI model runs
through Amazon Bedrock's Australian profile, which keeps processing in Sydney and Melbourne. Scanned
documents are read with Amazon Textract in Sydney and the temporary copy is deleted straight away.
Amazon Bedrock does not use your documents to train models.

**Who sees it.** Only [your name]. We don't share or sell your documents or the report.

**How long we keep it.** Your documents and the report are deleted within 30 days of sending the
report, or sooner if you ask. We keep a note that a check was done and your feedback, not the
documents.

**What the report is.** General information to help you prepare, checked by a person. It is not legal
advice and doesn't certify compliance.

**Questions or deletion requests:** [email]

---

Your checklist for every check (not for sending):

- [ ] They have this note before sending anything
- [ ] Documents saved only in `clients/<name>/` (never in Git, never in the Knowledge Base)
- [ ] Report sent; deletion date written in the validation log
- [ ] Documents and `reports/<name>/` deleted on that date
- [ ] Follow the Australian Privacy Principles as good practice, even if the small-business exemption applies to you
