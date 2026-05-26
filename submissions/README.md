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

**Everything you drop here is tracked and pushed to a public repo** — the GHA
runner needs the files at scrape time. Privacy-review each clip before
committing: strip embedded API keys (StreetEasy embeds a Google Maps key in
map-tile image URLs), broker phone numbers you don't want republished, and
anything else you wouldn't want on GitHub Pages. The scraper renders
`title` / `address` / `description` into the published HTML.

## Alternative intake paths

These are kept for non-Obsidian family members:

- `../manual_urls.txt` — one URL per line, you paste in (legacy)
- `../submissions.csv` or the Google Sheet via Apps Script — for aunt/uncle
  who add rows themselves (legacy)

All three paths feed the same enrichment pipeline.
