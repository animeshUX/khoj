# Khoj — Brooklyn apartments near a downtown campus

A daily-refreshed Brooklyn-apartment map for a student near a Tandon-style downtown campus. The point isn't to compete with StreetEasy on photos — it's to layer on the data those sites *don't* give you: real commute time to the campus, neighborhood safety, noise, and how close the nearest South-Asian grocery is. Campus coordinates and budget bounds live in `scraper.py`; tweak them to point at your own school / target.

**Read the latest report:** https://animeshux.github.io/khoj/

No login. No app to install. Works on phones. Bookmark the link and check it whenever you want — it updates itself once a day.

> **Status: early alpha.** This is a human-factors engineer's exploration of what the right information system for apartment-hunting looks like when you can layer real city data (commute, safety, noise, food access) onto listings. Expect opinionated defaults, rough edges, and obvious UX bugs that get fixed as the build goes on. If you run into one, the [Issues tab](https://github.com/animeshUX/khoj/issues) is the place.

## What it shows

One page, one map, a sortable list of every candidate the system knows about today:

- **List rail (left)** — every listing, sortable by score / price / commute / posted-date. Click a row → its pin highlights on the map and a detail panel slides in.
- **Map (right)** — pins colored by fit-score (muted gray → crimson as the score climbs), the campus marked with a crimson star, F/A/C/R subway stations as MTA-style bullets, plus a layers control to toggle overlays for noise, crime, parks, the 30-minute commute zone, and subway lines. Eight free tile providers in the picker — Streets, Minimal, Voyager, Dark, Gray, Satellite, Transit, Humanitarian.
- **Detail panel** — full enrichment per listing: commute breakdown (walk + rail minutes, nearest station + lines), 12-month safety stats (felonies / misdemeanors / violations), 12-month 311 noise counts, ranked Indian restaurants ≤1mi, halal/desi groceries with a south-asian flag. Click the listing URL to open the source page.

You can **★ Star** ones you like, **⊘ Hide** ones that don't fit, and type a **Note** on each. Those marks stay on your device — open the page tomorrow and they'll still be there.

**Keyboard:** `j` / `k` next / previous listing, `s` star, `h` hide, `Esc` close panel, `/` focus the price-filter input.

## What it's filtered to

Hard filters live in `scraper.py` and apply to the Craigslist scrape:

- Price between **$800 and $1,500**
- Studio, 1-bedroom, or 2-bedroom
- Posted in the last two weeks
- Within roughly a 30-minute commute of the campus address pinned in `scraper.py` (geodesic ~4-mile proxy)

Submitted URLs (see below) bypass the hard filters — if someone took the time to send it, it surfaces regardless.

## Sharing a listing you found yourself

Three intake paths, all feeding the same enrichment pipeline:

1. **Google Sheet** (primary, for non-technical family members) — add a row to the shared sheet. Template in `submissions_template.csv`. An Apps Script web app exposes the sheet as CSV; the scraper reads it via the `KHOJ_SUBMISSIONS_URL` repo secret. The Apps Script resolves rich-text hyperlinks and pre-fetches OpenGraph metadata so listings on Amber / StreetEasy / PadMapper still show a title even though those sites block scraping from datacenter IPs. See `apps_script.gs`.
2. **Obsidian Web Clipper drops** (for power users) — clip any listing page in your browser; the markdown file lands in `submissions/*.md` and the scraper picks it up on the next run. Web Clipper preserves the address, description, and photos cleanly enough that the geocoder works on sites where address-via-OG fails. See `submissions/README.md`.
3. **Local CSV fallback** — `submissions.csv` at the repo root, same columns as the template. Useful for local testing without a sheet.

Trigger an immediate refresh instead of waiting for tomorrow: **Actions → "Scrape Craigslist" → Run workflow**. About five minutes later, the live page updates.

## How a listing gets scored

The displayed score is a **0–1 fit-score** computed in `score.py` from the enrichment data. Each component returns `None` when its data is missing — missing inputs are skipped from the average rather than penalized (so a Craigslist listing with no enrichment doesn't score zero just because it has no commute number; it just gets scored on price alone).

| Weight | Component | What it measures |
|---|---|---|
| 0.35 | Commute | Listing → nearest relevant subway → campus. 15 min → 1.0, 45 min → 0.0, linear in between. |
| 0.25 | Safety | NYPD CompStat felonies in the precinct (12 mo). ≤20 → 1.0, ≥200 → 0.0, linear. |
| 0.20 | South-Asian access | ≥1 south-asian grocery + ≥3 close Indian restaurants → 1.0, partials → 0.7 / 0.4 / 0.0. |
| 0.20 | Price | ≤$800 → 1.0, ≥$2,000 → 0.0, linear inside the band. |

It's a heuristic, not gospel. If you want different weights, edit the constants at the top of `score.py`.

## How it actually runs

Two GitHub Actions workflows, one Python package, a static `docs/` directory served by Pages.

- **`scrape.yml`** — fires once a day around 9 AM Eastern. Runs `python scraper.py --pages-mode`, which: scrapes Craigslist, reads sheet submissions, reads Web Clipper drops, geocodes every listing via Nominatim, enriches with NYC Open Data (311 noise, NYPD crime) and Overpass (Indian food, halal grocery), and writes `docs/index.html` + `docs/apartments_YYYY-MM-DD.{html,csv}`.
- **`overlays.yml`** — fires once a week (Mon 06:00 UTC). Runs `python tools/build_overlays.py` to refresh `docs/data/crime.geojson` from NYPD CompStat. CompStat updates monthly so weekly is plenty.

**Code layout:**

```
scraper.py          orchestrator: scrape + read submissions + geocode + enrich + score
submission.py       parse Web Clipper .md frontmatter + body → Listing dict
enrich.py           geocode + commute + 311 noise + NYPD crime + Overpass POIs (with on-disk cache)
score.py            0–1 fit score from the enrichment block

report/             render tier (Python package, used by scraper.py)
  build.py            write_html(listings, path)
  payload.py          builds window.KHOJ — the data contract for the browser
  template.py         HTML shell
  __main__.py         `python -m report` for local re-render without re-scraping

docs/khoj/          browser tier (ES modules + CSS)
  main.js             entry — wires the modules together
  state.js            pub-sub store with localStorage persistence
  map.js              Leaflet init, listing pins, campus star, tile picker, layers control
  list.js             left rail rows, sort, hover-sync with pins
  panel.js            slide-in detail panel
  filters.js          top-bar filter chips + applyFilters()
  overlays.js         6 toggleable overlays + commute path + POI icons on selection
  keys.js             j/k/s/h/Esc//  shortcuts
  khoj.css            all styles (cream-paper editorial theme, design tokens)

docs/data/          pre-computed static GeoJSON overlays
tools/              one-off / weekly build scripts (build_overlays.py, etc.)
```

No database, no API keys, no hosting bill.

## One-time setup (for a fresh clone of this repo)

1. **Settings → Pages** → Source: "Deploy from a branch" → Branch: `main`, Folder: `/docs` → Save
2. **Settings → Actions → General** → Workflow permissions → "Read and write permissions" → Save
3. **Actions tab → "Scrape Craigslist" → Run workflow** to kick off the first run
4. (Optional) **Settings → Secrets and variables → Actions** → add `KHOJ_SUBMISSIONS_URL` pointing at your Apps Script Web App

After about five minutes you'll have a live URL at `https://<your-github-handle>.github.io/khoj/`.

## Running it on your own machine (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scraper.py --sanity-check     # quick check that Craigslist is reachable
python scraper.py                    # writes apartments_YYYY-MM-DD.{csv,html}
python scraper.py --pages-mode       # writes into docs/ the same way the Action does
python -m report                     # re-render docs/index.html from the existing payload
                                     # (useful when you're iterating on CSS/JS without re-scraping)
python -m pytest tests/ -v           # 9 unit tests (score.py + payload.py)
```

If the sanity check fails with a 403, run `python scraper.py --diagnose` to see which Craigslist endpoints are blocked from your network. Usually means you're on a VPN or corporate Wi-Fi.

## Things to know

- **Craigslist blocks the RSS endpoint** from most networks. We parse the static HTML search page instead — works fine from GitHub's runners.
- **There's a 1.5-second pause** between Craigslist requests so we don't hammer their servers. ~100 listings takes about 5 minutes.
- **Listings without coordinates still show up** in the list rail (they just don't get a map pin). Pre-pivot we dropped them; now you see them so you can decide.
- **The cron is idempotent.** Re-running just regenerates today's output; nothing accumulates.
- **Geocoding is cached on disk** (`.cache/geocode.json`, gitignored) so repeat runs don't hammer Nominatim. The SODA / Overpass enrichments are cached by week.

## Other places worth checking by hand

The report covers Craigslist scraping + manual submissions. These are also listed at the bottom of every page:

- **[AmberStudent](https://amberstudent.com/places/search/new-york-university-1811221663188)** — purpose-built student housing (per-room, booking-style)
- **[StreetEasy](https://streeteasy.com/for-rent/brooklyn/price:800-1500%7Cbeds%3C=2)** — NYC's biggest rental marketplace
- **[PadMapper](https://www.padmapper.com/apartments/brooklyn-ny?maxRent=1500)** — aggregator with map view
