# Project context for Claude Code

This file is loaded automatically into every Claude Code session opened in this repo. Read it before suggesting changes.

## What this is

Khoj is a daily-updated Craigslist apartment report for an incoming NYU Tandon **student** looking for a place near 370 Jay St, Brooklyn. The whole thing is a Python scraper + an HTML report + a GitHub Actions cron + GitHub Pages. **That's the entire architecture, and it's intentional.** It went through several rounds of "what if we also..." before settling here — see *History* below.

**Target:** apartments under **$1,500/month** within ~**30-minute commute** of campus (geodesic ~4 mi proxy). Studio / 1BR / 2BR full units, not room shares. The original constants ($1,200–$3,500, 1.5 mi) were too tight for actual student affordability — they returned listings nobody could afford.

## Architecture

| File | Purpose |
|---|---|
| `scraper.py` | Pulls Craigslist Brooklyn apartments, filters by price/distance/recency, scores by fit |
| `report.py` | Renders the editorial-dashboard HTML report |
| `submissions.csv` / Apps Script Web App | Google-Sheets-style intake (Timestamp, URL, Submitted by, Note). Read locally as CSV or via `KHOJ_SUBMISSIONS_URL` env var (the Apps Script Web App resolves rich-text hyperlinks and pre-fetches OG metadata before serving as CSV). `submissions_template.csv` is the empty header for the shared Sheet. |
| `submissions/*.md` | Obsidian Web Clipper drops (Phase 1 of the pivot, see `PLAN.md`) — gitignored by default, see `submissions/README.md`. |
| `.github/workflows/scrape.yml` | Daily cron + on-demand trigger; runs scraper, commits `docs/` back to main |
| `docs/index.html` | What GitHub Pages serves at https://animeshux.github.io/khoj/ — **live, Pages enabled** |
| `docs/apartments_YYYY-MM-DD.{html,csv}` | Daily archive |

No database. No app server. No API keys. No deployments to maintain. Pages is live and the cron has been working end-to-end.

## The report (report.py)

A single self-contained HTML page with embedded CSS + JS. Light cream-paper theme. State lives in `localStorage` per device.

**Type system** (defined as CSS variables at the top of `CSS`):
- Fonts: **Fraunces** (display, variable opsz 9–144 + WONK + SOFT axes) · **Newsreader** (body, variable opsz, includes italic) · **JetBrains Mono** (data/labels). All from Google Fonts.
- Scale anchored at **17px body**, major-third (1.25) ratio for headings:
  `--type-mega 4.5rem` · `--type-h1 2.75` · `--type-h2 1.875` · `--type-h3 1.5` · `--type-h4 1.25` · `--type-lead 1.125` · `--type-body 1` · `--type-small 0.875` · `--type-mono 0.8125` · `--type-micro 0.6875`
- Leadings: `--leading-display 0.95` · `--leading-tight 1.15` · `--leading-snug 1.25` · `--leading-normal 1.55`
- Use the tokens. Don't introduce new hardcoded rem values without a reason — there were lots of 0.62/0.65/0.7/0.74/0.78rem values before, all collapsed into the triple above.

**Color palette** (also CSS vars):
- `--paper #F3ECDE` warm cream background · `--paper-warm #EDE3CE` slightly-darker tint
- `--ink #1A1612` near-black · `--ink-soft #5A4E42` · `--ink-mute #93857A`
- `--rule #B8AB97` borders · `--rule-soft #D6CBB6` hairlines
- `--crimson #8C2026` accent (newspaper red) — used sparingly: top-pick scores, italic display text, star marker, action hovers
- `--gold #7A5C1E` reserved for notes / annotation

**Three views (tabs):** Inbox · Shortlist · Map. Toggled via JS state; only one `.view` is `.active` at a time. localStorage keys: `khoj.starred`, `khoj.hidden`, `khoj.notes`.

**Per-row mini-map** — `_mini_map_svg(lat, lng)` in `report.py` generates a 118×118 SVG per listing showing campus as a crimson dot at center, the listing as an ink dot positioned north-up east-right, with mile rings (1/2/3/4) and a dashed connecting line labeled with the distance. Math uses a flat-earth approximation valid at NYC scale: `_MILES_PER_DEG_LAT = 69`, `_MILES_PER_DEG_LNG = 52.5` (≈ 69 × cos(40.69°)). 13px per mile, listings beyond 4mi are clipped to a 54px radius. **Don't replace this with one Leaflet instance per row** — that's 60 inits on one page.

## Common operations

```bash
python scraper.py --sanity-check    # cheap check that Craigslist is reachable
python scraper.py                   # local run, outputs at repo root
python scraper.py --pages-mode      # writes to docs/ the way the cron does
python scraper.py --diagnose        # probe endpoints when --sanity-check 403s
```

**Intake path for human-submitted URLs:**

**`submissions.csv` OR a `KHOJ_SUBMISSIONS_URL` env var** — Google-Sheets-style intake (`Timestamp, URL, Submitted by, Note`). `_read_submissions_csv()` accepts either a local CSV path or an http(s) URL — typically an Apps Script Web App `doGet` endpoint serving the live sheet (`?key=<secret>` for auth). The workflow injects `KHOJ_SUBMISSIONS_URL` from a GitHub repo secret so the URL never lives in the repo. The Apps Script also resolves rich-text hyperlinks (when a cell shows a title but has a link attached) and pre-fetches OG metadata from Google's IP space — see `apps_script.gs`.

Submitted URLs bypass the price/distance/recency hard filters but still get scored. The Action picks them up on the next scheduled run or on demand from the Actions tab.

A second markdown-based intake (Obsidian Web Clipper → `submissions/*.md`) is in the pivot plan — see `PLAN.md`.

## DO NOT — privacy + scope

- **Never copy the Observatory design system into this repo.** The Observatory DS at `~/Development/observatory/field-data/` is private; this Khoj repo is public (GitHub Pages serves it). Don't vendor `dist/current/`, `tokens.css`, `patterns/`, or anything else from that directory into `docs/` or anywhere else that ships to GitHub. If a session needs styling inspiration, write fresh CSS using free Google Fonts (Fraunces, etc.) and Khoj-specific tokens — don't re-export Animesh's private DS by accident.

## DO NOT

- **Rebuild the Streamlit/SQLite/Sheets layers.** They existed and were deleted. The simplicity is the feature. If submission volume meaningfully grows, revisit by reviewing the parking-lot branches below — don't start over.
- **Delete the parking-lot branches.** On `origin`:
  - `craigslist-scraper`, `html-report-and-amber`, `debug-cl-blocking`, `pages-deploy`, `editorial-dashboard`, `map-relationship` — historical / merged work
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
