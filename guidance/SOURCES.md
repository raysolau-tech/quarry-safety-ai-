# Public guidance to download

Put 10+ PDFs in this folder, add one row per file to `sources.csv`, then run
`python ingest_guidance.py --kb-metadata` and upload the folder to S3 (README step 3).

Cover the three topics: mobile plant pre-starts, conveyor guarding and isolation,
and contractor management. Good places to start:

- **NSW Resources Regulator, small mines and quarries**: guides on safety management
  systems, principal hazards, plant, contractors and emergency plans.
  https://www.resources.nsw.gov.au/resources-regulator/safety/health-and-safety-management/small-mines-and-quarries
- **Small Mines Safety Management System Kit** (what many small quarries already use):
  https://www.resources.nsw.gov.au/sites/default/files/2023-05/SMR-23-07e%20Small-Mines-Safety-Management-System-Kit.pdf
- **Safe Work Australia, model Code of Practice: Managing the risks of plant in the workplace**
  (guarding, isolation, inspection of plant):
  https://www.safeworkaustralia.gov.au/doc/model-code-practice-managing-risks-plant-workplace
- **Safe Work Australia codes of practice** (find the ones on WHS consultation and on
  construction or contractor work): https://www.safeworkaustralia.gov.au/law-and-regulation/codes-practice
- **The law itself**: search https://legislation.nsw.gov.au for the *Work Health and Safety
  (Mines and Petroleum Sites) Regulation 2022* and the *Work Health and Safety Regulation 2025*
  (it replaced the 2017 Regulation). Download the **whole** document: a 1-page PDF is only the status page.
  Use "Print/Download" to save the PDF. Regulation rows carry the most weight with buyers.

Naming: `<publisher>-<type>-<short-title>-<year>.pdf`, lowercase, hyphens, no spaces
(publishers: `nsw` legislation, `nswrr` Resources Regulator, `swa` Safe Work Australia). Files you keep
for reference but don't index go in `guidance/_reference/` (not uploaded, not in Git).

Tips

- Prefer the regulation for "must" rows and codes or guides for "should" rows and for the
  evidence examples.
- Keep file names short and meaningful (`swa-code-plant.pdf`); they appear in every report.
- Check each document's licence before you redistribute it. Australian government guidance is
  mostly published under Creative Commons, but confirm on each page. Quoting a sentence with its
  source in a report is fine; putting the PDFs in a public repo may not be (`guidance/*.pdf` is in
  `.gitignore`).
