# submissions/

Drop zone for Obsidian Web Clipper markdown files. The enrichment pipeline
(planned — see `../PLAN.md`) parses anything in here that looks like a
Web Clipper clip and renders a per-listing decision dashboard.

## What goes here

Markdown files saved by [Obsidian Web Clipper](https://obsidian.md/clipper)
when someone clips an apartment listing from StreetEasy, AmberStudent,
PadMapper, Zillow, or any other site. Frontmatter shape:

```yaml
---
title: "<listing title>"
source: "<original URL>"
created: 2026-05-25
description: "<short summary, usually has the address + first sentence>"
tags: [clippings]
---
<rest of the clipped page as markdown>
```

## What the pipeline extracts

- **URL** — from `source:` frontmatter
- **Title** — from `title:` frontmatter
- **Address** — regex over the body (`\d+ Street Name + St/Ave/Pl/...`)
- **Price** — `$N[,NNN]/mo` patterns, with sanity bounds ($400–$20,000)
- **Bedrooms** — `1 BR`, `2-bed`, `studio`, etc.

Anything not extracted is replaced by a fallback. The enrichment runs
regardless — the moat is the per-address briefing, not the parser.

## What gets committed

By default, **nothing in this directory is tracked** except this README and
`.gitkeep` (see the root `.gitignore`). The .md clips are personal data
(which apartments your family is considering) and stay local. If you want
to publish a particular clip — say, the place you ultimately picked —
explicitly `git add -f submissions/that-one.md`.

## Alternative intake paths

These are kept for non-Obsidian family members:

- `../manual_urls.txt` — one URL per line, you paste in (legacy)
- `../submissions.csv` or the Google Sheet via Apps Script — for aunt/uncle
  who add rows themselves (legacy)

All three paths feed the same enrichment pipeline.
