<div align="center">

# Khoj

**A daily-refreshed Brooklyn-apartment map, layered with the data StreetEasy doesn't give you.**

Commute time to a specific campus. Neighborhood safety. Noise complaints. South-Asian groceries within a mile. Re-rendered every morning at 9 AM Eastern.

[**Open the live report &rarr;**](https://animeshux.github.io/khoj/)

[![Daily scrape](https://github.com/animeshUX/khoj/actions/workflows/scrape.yml/badge.svg)](https://github.com/animeshUX/khoj/actions/workflows/scrape.yml)
[![Secret scan](https://github.com/animeshUX/khoj/actions/workflows/secrets.yml/badge.svg)](https://github.com/animeshUX/khoj/actions/workflows/secrets.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-1A1612.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/status-early%20alpha-8C2026.svg)](#status)

<br>

<img src="docs/assets/hero.jpg" alt="Khoj report: list of candidate listings on the left, a Brooklyn map with score-colored pins, subway bullets, and a commute zone on the right" width="900">

</div>

---

## What it is

A human-factors engineer's exploration of what the right information system for apartment-hunting looks like when you can layer real city data (commute, safety, noise, food access) onto listings. Built originally for one student looking for a place near a downtown Brooklyn campus; the campus coordinates and budget bounds live in `scraper.py` &mdash; point them at your own school to fork.

The point isn't to compete with StreetEasy on photos. It's to surface the questions those sites can't answer.

> [!NOTE]
> <a id="status"></a>**Status: early alpha.** Opinionated defaults, rough edges, UX bugs in active triage. If you hit one, the [Issues tab](https://github.com/animeshUX/khoj/issues) is the place.

## What you see

One page, three panes:

- **List rail (left)** &mdash; every listing, sortable by score / price / commute / posted-date. Click a row to highlight its pin and slide in a detail panel.
- **Map (right)** &mdash; pins colored by fit-score (muted gray &rarr; crimson as score climbs), campus marked with a crimson star, F/A/C/R subway stations as MTA bullets. Toggle overlays for noise, crime, parks, the 30-minute commute zone, and subway lines. Eight free tile providers in the picker.
- **Detail panel** &mdash; commute breakdown (walk + rail minutes, nearest station + lines), 12-month safety stats, 311 noise counts, ranked Indian restaurants &le; 1 mi, halal/desi groceries.

**&starf; Star** the good ones, **&#x2298; Hide** the bad ones, type a **note** on any. Marks live in `localStorage` per device.

**Keyboard:** `j`/`k` next/previous, `s` star, `h` hide, `Esc` close panel, `/` focus price filter.

## What it's filtered to

Hard filters in `scraper.py`, applied to the Craigslist scrape only:

- **$800 &ndash; $1,500** &nbsp;&middot;&nbsp; studio / 1BR / 2BR &nbsp;&middot;&nbsp; posted within two weeks &nbsp;&middot;&nbsp; geodesic &le; 4 mi from campus (~30-min commute proxy)

Submitted URLs (see below) bypass these &mdash; if a human cared enough to send it, it surfaces.

## How a listing gets scored

A 0&ndash;1 fit-score computed in `score.py`. Missing inputs are skipped from the average rather than penalized.

| Weight | Component | What it measures |
|---:|---|---|
| 0.35 | Commute | Listing &rarr; nearest relevant subway &rarr; campus. 15 min &rarr; 1.0, 45 min &rarr; 0.0. |
| 0.25 | Safety | NYPD CompStat felonies in the precinct (12 mo). &le; 20 &rarr; 1.0, &ge; 200 &rarr; 0.0. |
| 0.20 | South-Asian access | &ge; 1 grocery + &ge; 3 close Indian restaurants &rarr; 1.0; partials &rarr; 0.7 / 0.4 / 0.0. |
| 0.20 | Price | &le; $800 &rarr; 1.0, &ge; $2,000 &rarr; 0.0. |

It's a heuristic, not gospel. Edit the constants at the top of `score.py` for different weights.

## Submitting a listing you found yourself

Three intake paths, all feeding the same enrichment pipeline:

1. **Google Sheet** &mdash; add a row to the shared sheet. Template in `submissions/template.csv`. An Apps Script web app exposes the sheet as CSV; the scraper reads it via the `KHOJ_SUBMISSIONS_URL` repo secret. The script also resolves rich-text hyperlinks and pre-fetches OpenGraph metadata so Amber / StreetEasy / PadMapper listings get titles even though they block scraping from datacenter IPs. See [`tools/apps_script.gs`](tools/apps_script.gs).
2. **Obsidian Web Clipper drops** &mdash; clip any listing page in your browser; the markdown file lands in `submissions/*.md` and the scraper picks it up on the next run. See [`submissions/README.md`](submissions/README.md).
3. **Local CSV** &mdash; `submissions.csv` at the repo root (gitignored), same columns as the template. Useful for local testing.

Trigger a fresh run without waiting for tomorrow: **Actions &rarr; "Scrape Craigslist" &rarr; Run workflow**. The live page updates ~5 minutes later.

## How it actually runs

Two GitHub Actions workflows, one Python package, a static `docs/` directory served by Pages. **No database. No API keys. No hosting bill.**

- **`scrape.yml`** &mdash; daily at ~9 AM Eastern. Scrapes Craigslist, reads sheet + Web Clipper submissions, geocodes via Nominatim, enriches with NYC Open Data (311 noise, NYPD crime) and Overpass (Indian food, halal grocery), and writes `docs/index.html` + a dated archive.
- **`overlays.yml`** &mdash; weekly (Mon 06:00 UTC). Refreshes `docs/data/crime.geojson` from NYPD CompStat.
- **`secrets.yml`** &mdash; on every push/PR. Gitleaks scan against the full history.

<details>
<summary><b>Code layout</b></summary>

```
scraper.py          orchestrator: scrape + read submissions + geocode + enrich + score
submission.py       parse Web Clipper .md frontmatter + body -> Listing dict
enrich.py           geocode + commute + 311 noise + NYPD crime + Overpass POIs (cached)
score.py            0-1 fit score from the enrichment block

report/             render tier (Python package, imported by scraper.py)
  build.py            write_html(listings, path)
  payload.py          builds window.KHOJ -- the data contract for the browser
  template.py         HTML shell
  __main__.py         `python -m report` for local re-render without re-scraping

docs/khoj/          browser tier (ES modules + CSS)
  main.js             entry -- wires the modules together
  state.js            pub-sub store with localStorage persistence
  map.js              Leaflet init, listing pins, campus star, tile picker, layers control
  list.js             left rail rows, sort, hover-sync with pins
  panel.js            slide-in detail panel
  filters.js          top-bar filter chips + applyFilters()
  overlays.js         6 toggleable overlays + commute path + POI icons on selection
  keys.js             j/k/s/h/Esc//  shortcuts
  khoj.css            all styles (cream-paper editorial theme, design tokens)

docs/data/          pre-computed static GeoJSON overlays
tools/              one-off / weekly build scripts + apps_script.gs
```

</details>

<details>
<summary><b>Run it locally</b></summary>

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scraper.py --sanity-check     # quick check Craigslist is reachable
python scraper.py                    # writes apartments_YYYY-MM-DD.{csv,html}
python scraper.py --pages-mode       # writes into docs/ the same way the Action does
python -m report                     # re-render docs/index.html from the existing payload
                                     # (useful when iterating on CSS/JS without re-scraping)
python -m pytest tests/ -v           # unit tests (score.py + payload.py)
```

If `--sanity-check` 403s, run `python scraper.py --diagnose` to see which Craigslist endpoints are blocked from your network. Usually means a VPN or corporate Wi-Fi.

</details>

<details>
<summary><b>Self-host (fresh fork)</b></summary>

1. **Settings &rarr; Pages** &rarr; Source: "Deploy from a branch" &rarr; Branch: `main`, Folder: `/docs` &rarr; Save
2. **Settings &rarr; Actions &rarr; General** &rarr; Workflow permissions &rarr; "Read and write permissions" &rarr; Save
3. **Actions tab &rarr; "Scrape Craigslist" &rarr; Run workflow** to kick off the first run
4. (Optional) **Settings &rarr; Secrets and variables &rarr; Actions** &rarr; add `KHOJ_SUBMISSIONS_URL` pointing at your Apps Script Web App

After ~5 minutes you'll have a live URL at `https://<your-github-handle>.github.io/khoj/`.

</details>

<details>
<summary><b>Things to know</b></summary>

- **Craigslist blocks the RSS endpoint** from most networks. We parse the static HTML search page instead &mdash; works fine from GitHub's runners.
- **1.5-second pause** between Craigslist requests so we don't hammer their servers. ~100 listings takes about 5 minutes.
- **Listings without coordinates** still show up in the list rail (they just don't get a map pin).
- **The cron is idempotent.** Re-running regenerates today's output; nothing accumulates.
- **Geocoding is cached on disk** (`.cache/geocode.json`, gitignored). SODA / Overpass enrichments are cached by week.

</details>

## Other places worth checking by hand

The report covers Craigslist + manual submissions. These are also linked at the bottom of every page:

- [**AmberStudent**](https://amberstudent.com/places/search/new-york-university-1811221663188) &mdash; purpose-built student housing (per-room, booking-style)
- [**StreetEasy**](https://streeteasy.com/for-rent/brooklyn/price:800-1500%7Cbeds%3C=2) &mdash; NYC's biggest rental marketplace
- [**PadMapper**](https://www.padmapper.com/apartments/brooklyn-ny?maxRent=1500) &mdash; aggregator with map view

---

<sub>**Security:** see [SECURITY.md](SECURITY.md) for the disclosure policy. &nbsp;&middot;&nbsp; **License:** [MIT](LICENSE). &nbsp;&middot;&nbsp; Built with Leaflet, OpenStreetMap, NYC Open Data, and Overpass.</sub>
