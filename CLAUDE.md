# Project context for Claude Code

This file is loaded automatically into every Claude Code session opened in this repo. Read it before suggesting changes.

## What this is

Khoj is a daily-updated Craigslist apartment report for an incoming NYU Tandon **student** looking for a place near 370 Jay St, Brooklyn. The whole thing is a Python scraper + an HTML report + a GitHub Actions cron + GitHub Pages. **That's the entire architecture, and it's intentional.** It went through several rounds of "what if we also..." before settling here — see *History* below.

**Target:** apartments under **$1,500/month** within ~**30-minute commute** of campus (geodesic ~4 mi proxy). Studio / 1BR / 2BR full units, not room shares. The original constants ($1,200–$3,500, 1.5 mi) were too tight for actual student affordability — they returned listings nobody could afford.

## Architecture

| File | Purpose |
|---|---|
| `scraper.py` | Pulls Craigslist Brooklyn apartments, filters by price/distance/recency, scores by fit |
| `report.py` | Renders the editorial-dashboard HTML report (Fraunces + Newsreader + JetBrains Mono, paper-cream theme, localStorage state for star/hide/notes, Leaflet map) |
| `manual_urls.txt` | Append-only file of URLs aunt/uncle text in; scraper merges them with scraped results |
| `.github/workflows/scrape.yml` | Daily cron + on-demand trigger; runs scraper, commits `docs/` back to main |
| `docs/index.html` | What GitHub Pages serves at `animeshux.github.io/khoj/` |
| `docs/apartments_YYYY-MM-DD.{html,csv}` | Daily archive |

No database. No app server. No API keys. No deployments to maintain.

## Common operations

```bash
python scraper.py --sanity-check    # cheap check that Craigslist is reachable
python scraper.py                   # local run, outputs at repo root
python scraper.py --pages-mode      # writes to docs/ the way the cron does
python scraper.py --diagnose        # probe endpoints when --sanity-check 403s
```

To add a manually-submitted URL: append to `manual_urls.txt` (one per line, `#` comments OK, optional ` | note` suffix). Commit and push. Action picks it up on the next scheduled run or on demand from the Actions tab.

## DO NOT — privacy + scope

- **Never copy the Observatory design system into this repo.** The Observatory DS at `~/Development/observatory/field-data/` is private; this Khoj repo is public (GitHub Pages serves it). Don't vendor `dist/current/`, `tokens.css`, `patterns/`, or anything else from that directory into `docs/` or anywhere else that ships to GitHub. If a session needs styling inspiration, write fresh CSS using free Google Fonts (Fraunces, etc.) and Khoj-specific tokens — don't re-export Animesh's private DS by accident.

## DO NOT

- **Rebuild the Streamlit/SQLite/Sheets layers.** They existed and were deleted. The simplicity is the feature. If submission volume meaningfully grows, revisit by reviewing the parking-lot branches below — don't start over.
- **Delete the parking-lot branches.** On `origin`:
  - `craigslist-scraper`, `html-report-and-amber`, `debug-cl-blocking` — historical, may have something to mine
  - `submission-app`, `scraper-db-write`, `sheets-backend` — the Streamlit + DB + Sheets work, kept in case scope expands
- **Use the Craigslist RSS endpoint.** `?format=rss` is hard-blocked everywhere (datacenter and residential IPs). Use the static SEO HTML — `<li class="cl-static-search-result">` on the search page.
- **Add retry loops, fallback chains, or "future-proof" abstractions.** Trust the cron to retry tomorrow if today fails. Trust the user to debug with `--diagnose` if something breaks.
- **Suggest pip-installing things during analysis.** The cron uses only `requirements.txt`; keep it that way.

## Selectors that break first

Craigslist updates its DOM occasionally. When a future scrape returns zero listings, these are the usual suspects:

- `<li class="cl-static-search-result">` (search results)
- `<div class="attrgroup">` for bedrooms — was `<p>` before 2024
- `<span class="postingtitletext">` trailing `<span>(Hood)</span>` for neighborhood — was `<small>` before
- Map div `data-latitude` / `data-longitude` attrs for coordinates
- `<section id="postingbody">` for description

Inspect one live detail page and re-confirm before changing parse logic.

## History (what we tried and dropped)

1. **RSS-based search** → blocked by Craigslist; switched to the HTML SEO block.
2. **Streamlit submission app** (branch: `submission-app`) → built and working, but family submits URLs a few times a week — not enough to justify a deployed web service.
3. **Auto-DB-write from scraper** (branch: `scraper-db-write`) → reasonable layer, but only useful if the Streamlit app is in play.
4. **Google Sheets backing store** (branch: `sheets-backend`) → blocked by Google Cloud's billing requirement, which the user won't supply for a personal project.
5. **AmberStudent scraping** → considered, dropped: data is a JS object literal (not JSON), and listings are mostly PBSA (per-room) which is a different product than what brother needs.
6. **StreetEasy scraping** → Cloudflare-blocked, needs paid Apify. Linked out in the report footer for manual browsing instead.

The current architecture — cron + Pages + a text file — was the answer the user landed on after evaluating the above. Don't reverse-engineer the journey on a new session and re-suggest the rejected paths.

## When you do change things

- Match the existing minimal style — no decorative comments, no defensive coding for paths that can't happen.
- Update this file if you delete a section of the architecture or add a real new piece (don't update it for one-off fixes).
- Run the scraper locally to verify before pushing if your change touches parse logic.
