# Tuesday blog assistant (GitHub Pages)

Every Tuesday at 9am a scheduled Claude task drafts a build-log post about the week just finished,
following the 30-week plan, and saves it in your blog's `_drafts/` folder. **Nothing goes live until
you move it to `_posts/` and push.**

```
blog/calendar.csv  ──► which post is due (title, angle, KPIs to report)
blog/progress.md   ──► your real numbers and notes for the week   ─┐
blog_tools.py facts ─► safe counts from the repo (no names)        ├─► Claude writes the draft
blog/STYLE.md      ──► voice and hard rules                        ─┘   blog/posts/<date>-<slug>.md
                                                                        + .linkedin.txt teaser
blog_tools.py check ─► blocks "compliant", emails, phone numbers, keys, contact names
blog_tools.py draft ─► copies it into <blog site>/_drafts/   (not built, not public)
blog_tools.py publish ► moves it to _posts/; you run git push  (this is what goes live)
```

The blog is its **own small public repo**, kept in a separate folder (default
`C:\Users\ulrik\Documents\quarry-blog`) so nothing from this project, such as `clients/` or reports,
can ever end up on the public internet. Change the folder with `BLOG_SITE_DIR` in `.env`.

## One-time setup

1. Create the site folder: `python blog_tools.py site-init`
2. In that folder run `git init -b main`, create a **public** GitHub repo named
   `<your-github-username>.github.io`, then add it as the remote and push.
3. GitHub repo > Settings > Pages > Deploy from a branch > `main` / root.
4. Your blog is at `https://<your-github-username>.github.io`.

## Each week (5 minutes, before Tuesday 9am)

Add your numbers and notes for the week to `blog/progress.md`. The better the notes, the fewer
placeholders in the draft.

## Tuesday

1. Open the draft in `<blog site>/_drafts/`, check every number, fill each `[ADD: ...]`.
2. `python blog_tools.py publish "<path to the draft>"` (refuses while placeholders remain).
3. In the blog folder: `git add -A`, `git commit -m "Publish week N"`, `git push`.
4. About a minute later it is live. Post the `.linkedin.txt` teaser with the link and add the post
   to LinkedIn's Featured section.

## Commands

```
python blog_tools.py next
python blog_tools.py facts
python blog_tools.py check blog/posts/<file>.md
python blog_tools.py site-init
python blog_tools.py draft blog/posts/<file>.md [--force]
python blog_tools.py publish <blog site>/_drafts/<file>.md
```
