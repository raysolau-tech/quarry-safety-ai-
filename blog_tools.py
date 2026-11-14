"""Helpers for the Tuesday blog assistant (see blog/README.md).

    python blog_tools.py next              # this Tuesday's post from blog/calendar.csv
    python blog_tools.py facts             # safe, aggregate numbers from the repo (no names)
    python blog_tools.py check <post.md>   # lint a draft against blog/STYLE.md hard rules
    python blog_tools.py site-init         # one-off: create the blog site folder (GitHub Pages / Jekyll)
    python blog_tools.py draft <post.md>   # check it, then save it in the site's _drafts/ (nothing goes live)
    python blog_tools.py publish <draft>   # move a reviewed draft to _posts/; you then git push

The assistant never reads customer documents. Facts come only from aggregate counts and from
blog/progress.md, which the owner writes.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOG = ROOT / "blog"
CALENDAR = BLOG / "calendar.csv"
POSTS = BLOG / "posts"
VALIDATION_LOG = ROOT / "offer" / "validation_log.csv"


# --- calendar -------------------------------------------------------------------

def load_calendar(path: Path = CALENDAR) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def next_post(today: dt.date, rows: list[dict[str, str]]) -> dict[str, str] | None:
    """The post due today, else the next one coming up."""
    upcoming = [r for r in rows if dt.date.fromisoformat(r["publish_date"]) >= today]
    return min(upcoming, key=lambda r: r["publish_date"]) if upcoming else None


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug if len(slug) <= 60 else slug[:61].rsplit("-", 1)[0]


def post_path(row: dict[str, str]) -> Path:
    return POSTS / f"{row['publish_date']}-{slugify(row['title'])}.md"


# --- facts ----------------------------------------------------------------------

def library_facts(path: Path) -> dict:
    if not path.exists():
        return {"verified_requirements": 0, "draft_or_other": 0, "verified_by_topic": {}}
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    verified = [r for r in rows if r.get("status") == "verified"]
    by_topic: dict[str, int] = {}
    for r in verified:
        by_topic[r.get("topic", "")] = by_topic.get(r.get("topic", ""), 0) + 1
    return {"verified_requirements": len(verified), "draft_or_other": len(rows) - len(verified),
            "verified_by_topic": by_topic}


def validation_facts(path: Path) -> dict:
    """Counts only. Names, companies and notes never leave this function."""
    if not path.exists():
        return {"conversations_logged": 0, "free_checks_sent": 0}
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
    sent = sum(1 for r in rows if (r.get("check_sent") or "").strip().lower() in {"yes", "y", "true", "1"})
    return {"conversations_logged": len(rows), "free_checks_sent": sent}


def gather_facts(root: Path = ROOT) -> dict:
    import config

    return {
        "as_of": dt.date.today().isoformat(),
        "library": library_facts(root / config.LIBRARY_CSV),
        "validation": validation_facts(root / "offer" / "validation_log.csv"),
        "progress_notes": "blog/progress.md",
    }


# --- draft check ----------------------------------------------------------------

US_SPELLINGS = {"optimize": "optimise", "organize": "organise", "analyze": "analyse",
                "color": "colour", "behavior": "behaviour", "center": "centre", "modeling": "modelling",
                "labeled": "labelled", "favorite": "favourite", "summarize": "summarise"}
HYPE = ("game-changer", "game changer", "revolutionise", "revolutionize", "unlock", "delve",
        "fast-paced world", "cutting-edge")


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2)


def private_names(path: Path = VALIDATION_LOG) -> set[str]:
    """Contact names and companies from the validation log, to make sure none appear in a post."""
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {(r.get(c) or "").strip() for r in rows for c in ("name", "company")
            if len((r.get(c) or "").strip()) >= 3}


def check_post(text: str, names: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors must be fixed before a draft is sent."""
    errors: list[str] = []
    warnings: list[str] = []
    meta, body = split_front_matter(text)
    low = body.lower()
    if not meta.get("title"):
        errors.append("front matter needs a title")
    if re.search(r"\bcompliant\b|\bguarantee", low):
        errors.append("says 'compliant' or 'guarantee': use documented / partly documented / not found / needs review")
    if "not legal or safety advice" not in low:
        errors.append("missing the footer: 'This is a build log, not legal or safety advice...'")
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", body):
        errors.append("contains an email address")
    if re.search(r"(\+?61|\b0)[2-478](?:[ -]?\d){8}\b", body):
        errors.append("contains what looks like a phone number")
    if re.search(r"AKIA[0-9A-Z]{16}|nvapi-|BEGIN [A-Z ]*PRIVATE KEY", body):
        errors.append("contains what looks like a secret key")
    if any(p in low for p in ("clients/", "reports/")):
        errors.append("mentions a customer data folder")
    for n in names or set():
        if re.search(rf"\b{re.escape(n.lower())}\b", low):
            errors.append("mentions a contact or company from the validation log: remove it unless they agreed to be named")
            break
    placeholders = re.findall(r"\[ADD:[^\]]*\]", body)
    if placeholders:
        warnings.append(f"{len(placeholders)} [ADD: ...] placeholder(s) to fill before publishing")
    words = len(re.findall(r"\b\w+\b", body))
    if not 600 <= words <= 1500:
        warnings.append(f"{words} words (aim for 800 to 1,300)")
    for us, au in US_SPELLINGS.items():
        if re.search(rf"\b{us}\w*", low):
            warnings.append(f"US spelling '{us}': use '{au}'")
    for h in HYPE:
        if h in low:
            warnings.append(f"hype word '{h}'")
    return errors, warnings


# --- GitHub Pages (Jekyll) -------------------------------------------------------
# The blog is its own small PUBLIC repo, kept outside this project so customer folders can never
# end up in it. A post in _drafts/ is never built by GitHub Pages. Moving it to _posts/ and
# pushing is what publishes it, and only the owner does that.

DEFAULT_SITE_DIR = ROOT.parent / "quarry-blog"

CONFIG_YML = """title: Building AI for NSW quarries
description: A 30-week build log: requirements, evidence and edge AI for quarry safety.
theme: minima
markdown: kramdown
plugins:
  - jekyll-feed
  - jekyll-seo-tag
"""
INDEX_MD = """---
layout: home
---
"""
ABOUT_MD = """---
layout: page
title: About
permalink: /about/
---
A build log from a product leader building edge AI for NSW quarries, with the work done in public:
what I tried, the numbers, and what went wrong.

This blog is a build log, not legal or safety advice.
"""
SITE_GITIGNORE = "_site/\n.jekyll-cache/\nGemfile.lock\n.env\n"


def site_dir() -> Path:
    return Path(os.getenv("BLOG_SITE_DIR", "") or DEFAULT_SITE_DIR)


def init_site(target: Path) -> list[str]:
    """Create a minimal Jekyll site that GitHub Pages builds. Never overwrites an existing file."""
    created = []
    files = {"_config.yml": CONFIG_YML, "index.md": INDEX_MD, "about.md": ABOUT_MD,
             ".gitignore": SITE_GITIGNORE, "_drafts/.gitkeep": "", "_posts/.gitkeep": ""}
    for name, content in files.items():
        p = target / name
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        created.append(name)
    return created


def jekyll_post(meta: dict[str, str], body: str) -> str:
    """Our front matter -> Jekyll front matter. Only fields Jekyll understands are kept."""
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    lines = ["---", "layout: post", f"title: {json.dumps(meta['title'], ensure_ascii=False)}"]
    if meta.get("subtitle"):
        lines.append(f"description: {json.dumps(meta['subtitle'], ensure_ascii=False)}")
    if tags:
        lines.append("tags: [" + ", ".join(json.dumps(t) for t in tags) + "]")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def draft_file(source: Path, target: Path, force: bool = False) -> Path:
    """Check a post, then save it in the site's _drafts/ folder. Nothing goes live."""
    text = source.read_text(encoding="utf-8")
    meta, body = split_front_matter(text)
    errors, _ = check_post(text, private_names())
    if errors:
        raise RuntimeError("fix these first: " + "; ".join(errors))
    if not (target / "_config.yml").exists():
        raise RuntimeError(f"no blog site at {target}: run  python blog_tools.py site-init")
    out = target / "_drafts" / f"{slugify(meta['title'])}.md"
    if out.exists() and not force:
        raise RuntimeError(f"{out.name} is already in _drafts (use --force to replace it)")
    out.write_text(jekyll_post(meta, body), encoding="utf-8")
    return out


def publish_file(draft: Path, target: Path, today: dt.date | None = None) -> Path:
    """Move a reviewed draft from _drafts/ to _posts/ with today's date. The owner then pushes."""
    text = draft.read_text(encoding="utf-8")
    left = re.findall(r"\[ADD:[^\]]*\]", text)
    if left:
        raise RuntimeError(f"{len(left)} [ADD: ...] placeholder(s) still in the post: fill them first")
    errors, _ = check_post(text.replace("---\n", "---\n", 1), private_names())
    if errors:
        raise RuntimeError("fix these first: " + "; ".join(errors))
    date = (today or dt.date.today()).isoformat()
    out = target / "_posts" / f"{date}-{draft.stem}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    draft.replace(out)
    return out


# --- command line ---------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"next", "facts", "check", "draft", "publish", "site-init"}:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "next":
        row = next_post(dt.date.today(), load_calendar())
        if not row:
            print("No posts left in blog/calendar.csv")
            return 1
        out = dict(row, post_file=str(post_path(row).relative_to(ROOT)).replace("\\", "/"),
                   already_written=post_path(row).exists())
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif cmd == "facts":
        print(json.dumps(gather_facts(), indent=2))
    elif cmd == "check":
        errors, warnings = check_post(Path(argv[1]).read_text(encoding="utf-8"), private_names())
        for e in errors:
            print("ERROR  ", e)
        for w in warnings:
            print("warning", w)
        print("OK to save as a draft" if not errors else f"{len(errors)} error(s) to fix")
        return 1 if errors else 0
    elif cmd == "site-init":
        import config  # noqa: F401  (loads .env)

        target = site_dir()
        created = init_site(target)
        print(f"Blog site folder: {target}")
        print("Created: " + (", ".join(created) if created else "nothing (already set up)"))
        print("Next: cd into it, run  git init -b main , create a PUBLIC GitHub repo (name it "
              "<your-github-username>.github.io), push, then Settings > Pages > Deploy from branch main.")
    elif cmd == "draft":
        import config  # noqa: F401  (loads .env)

        out = draft_file(Path(argv[1]), site_dir(), force="--force" in argv)
        print(f"Saved draft: {out}\nNothing is live. Review it, then:  python blog_tools.py publish \"{out}\"")
    elif cmd == "publish":
        import config  # noqa: F401  (loads .env)

        target = site_dir()
        out = publish_file(Path(argv[1]), target)
        print(f"Moved to {out}\nIt goes live when you push:\n  cd \"{target}\"\n  git add -A\n"
              f"  git commit -m \"Publish: {out.stem}\"\n  git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
