# Khoj — pivot plan

**Status:** validated by dry run, not built yet. Successor to the current
"Craigslist scraper + report + cron" architecture described in CLAUDE.md.

**Date drafted:** 2026-05-25

## What changed

The original plan was to scrape multiple apartment aggregators (Craigslist,
StreetEasy, AmberStudent, PadMapper, Zillow) and render a unified UI. After
a day of trying:

- **Craigslist** scrapes fine — the only source where we have real, structured,
  current listings.
- **StreetEasy** returns Cloudflare 403 to every datacenter IP. Even Google
  Apps Script's IP space is blocked.
- **AmberStudent** returns 200 OK but strips OpenGraph metadata for datacenter
  IPs — silent degradation, harder to detect than a 403.
- **Zillow / Apartments.com** — same problem.
- **Listings turn over in ~6 hours**, so even a working daily-scrape would
  show stale inventory most of the time.

The aggregator-data plan has a structural ceiling: aggregators don't let
external code have their data, regardless of code quality. So we pivot.

## The new shape

Khoj becomes a **decision-support tool**, not an aggregator. The family
already browses StreetEasy/Zillow/Amber directly and finds candidates —
that's the easy part. The hard part is *evaluating* each candidate against
this specific brother's specific needs. Khoj does the evaluation.

- **Data the aggregators won't give us** (commute to Tandon, crime stats,
  noise complaints, Indian food access, halal/desi grocery proximity,
  neighborhood quality) is **what Khoj provides**.
- **Data the aggregators do give us** (listing photos, listing description,
  asking rent) is what they're best at — Khoj just links out.
- **Source data is all free and public**: OpenStreetMap (Nominatim, Overpass),
  NYC Open Data (311, NYPD CompStat), MTA station data (already in repo).
  Zero scraping, zero API keys, zero subscriptions.

## Intake

Three input paths, all feeding the same enrichment pipeline:

1. **Obsidian Web Clipper → `submissions/*.md`** (preferred — see
   `submissions/README.md`). Family clicks the Web Clipper button on any
   listing page, markdown file lands in vault, vault syncs to repo via
   Obsidian Git plugin or manual commit. One click, any site.
2. **Google Sheet via Apps Script** (kept for non-Obsidian users — aunt/
   uncle). The Apps Script already resolves hyperlinks and pre-fetches
   OG metadata. Continues to work as-is.

The Web Clipper path is the upgrade. Markdown is structured enough to parse
without scraping, and the Web Clipper extension already strips nav/ads.

(A prior `manual_urls.txt` text-file path was removed in this refactor —
its content was always a subset of what the Apps Script Sheet handles.)

## Enrichment (the moat)

Validated by `tools/enrich_dryrun.py` on three real Web Clipper outputs
(Bernard / Amber, Kingsland / PadMapper, Rogers Ave / StreetEasy):

| Layer | Source | Output per listing |
|---|---|---|
| Geocoding | Nominatim (OSM) | lat/long, canonical address, neighborhood |
| Commute → 370 Jay | Local `docs/data/subway-stations.geojson` + haversine + speed assumption | "3 min walk to Kingston-Throop (C) → 11 min rail ≈ 14 min total" |
| Noise | NYC 311 SODA API, 250m radius, last 12mo | "289 complaints, mostly Loud Music/Party" |
| Crime | NYPD CompStat SODA API, 400m radius, last 12mo | "236 complaints — 70 felonies, 134 misdemeanors, 32 violations" |
| Indian food | Overpass (`cuisine~indian` OR name matches `indian/tandoor/curry/biryani/masala/dosa`) | Ranked list within 1mi |
| Grocery | Overpass (`shop=supermarket/convenience/grocery` + name filter for `indian/halal/desi/patel/bangla`) | Closest 5 + south-asian flag |

**Dry-run output for the three test addresses** is captured in the next
section so a fresh agent can verify the pipeline still works without
re-running everything.

## Dry-run results (verified 2026-05-25)

### 50 MacDonough St (Bernard / Amber)
- Geocoded: Bedford-Stuyvesant, (40.68071, -73.94434)
- Commute: **14 min** total — 3 min walk to Kingston-Throop (C), 11 min rail
- Noise: 289 complaints (mostly party noise)
- Crime: 236 total (70 felonies)
- Indian food: 6 restaurants ≤1mi, closest India House at 0.32mi
- Grocery: 44 shops; **2 south-asian/halal-flagged** (Nouri Halal Meat 0.46mi)

### 99 Kingsland Ave (PadMapper / Greenpoint)
- Geocoded: Greenpoint, (40.71984, -73.94084)
- Commute: **56 min** — 39 min walk to nearest F station; dealbreaker
- Noise: 304 complaints
- Crime: 93 total (22 felonies) — best safety profile of the three
- Indian food: 4 restaurants ≤1mi, Indian Kitchen at 0.57mi
- Grocery: 28 shops; 0 south-asian flagged

### 1273 Rogers Ave #2D (StreetEasy / Flatbush)
- Geocoded: Flatbush, (40.63877, -73.95095)
- Commute: **44 min** — 28 min walk to Ditmas (F); also dealbreaker
- Noise: **449 complaints** (loudest of the three)
- Crime: 258 total (71 felonies)
- Indian food: 2 restaurants ≤1mi, closest Jalsa at 0.93mi
- Grocery: 9 shops; 0 south-asian flagged

**Verdict the enrichment produces** that StreetEasy / Amber / PadMapper
cannot: Bernard is the only viable candidate of the three. Rogers Ave and
Kingsland are eliminated on commute, before the family even looks at
listing photos.

## Output

Two views:

1. **Per-listing detail card** — one rich card per submitted address, with
   sections matching the table above (header, commute panel, safety panel,
   lifestyle panel, map). The map shows: listing pin, Tandon, nearest
   relevant subway, 311 noise heatmap, Indian-food and grocery POIs.
2. **Compare view** — sortable head-to-head table across all submitted
   places. Family argues over this. Sortable by: commute, price, crime,
   noise, Indian food proximity, halal grocery proximity.

Craigslist scrape continues to run; its hits become one input among many,
not the spine.

## Phased build plan

Each phase ships independently with visible value.

### Phase 1 — submissions/ + extraction + geocoding (1 evening)
- Move `tools/enrich_dryrun.py` logic into a new `enrich.py` module
- `submission.py` module: parse Web Clipper `.md` frontmatter + body → Listing record
- `scraper.py` main loop: read `submissions/*.md` alongside existing CSV/text intake
- Geocode each via Nominatim, cache by (address-hash → lat/lng) on disk
- Existing report shows submitted places with at least: title, URL, address, lat/lng on the map

### Phase 2 — commute, noise, crime (1 evening)
- Add MTA-based commute estimate (currently haversine + speed; OK for v1)
- Add 311 + NYPD enrichment, cache by (geohash, week) — re-fetch weekly, not per-run
- Per-listing card grows the safety + commute panels

### Phase 3 — POI / lifestyle (½ evening)
- Add Overpass queries for Indian food + grocery + others (parks, gyms, laundromats)
- Cache Overpass by (geohash, query-hash) for 30 days
- Per-listing card grows the lifestyle panel

### Phase 4 — report restructure (1 evening)
- Per-listing detail card layout (replaces the current "row in a list")
- Compare-view: sortable table across all submissions

### Phase 5 — polish (½ evening)
- Walk Score API (or skip; OSMnx for true street-network walking) — optional
- OpenTripPlanner for real subway routing — optional, biggest commute-quality upgrade
- Map: 311 heatmap overlay, POI markers per listing

## What dies

- The `_fetch_external_listing` live-fetch path becomes mostly unused. URLs
  from submissions now have markdown bodies; we don't need to re-fetch the
  page to get a title.
- The slug-fallback (`_title_from_slug`) becomes dead code once intake is
  markdown-based. Keep for the Apps Script CSV path (still need a fallback
  for URLs without OG enrichment).
- The "stub card" UX (price unknown, beds unknown, no description) goes
  away — every submission has parsed metadata + enrichment.

## What stays

- The Craigslist scraper (it works, and family does find occasional good
  Craigslist hits)
- The daily cron — same workflow, same Pages output
- The editorial-newspaper visual design (Fraunces / Newsreader / JetBrains
  Mono, cream-paper theme, crimson accent)
- The localStorage star/hide/note state
- The Apps Script + sheet intake (alternative path)

## What's at risk / open questions

1. **Subway commute estimate is approximate.** Straight-line distance ×
   3.5 min/mi for rail time. Off by transfers, frequency, dwell. Good enough
   for "is this commutable?" — bad for "exactly how long". Upgrading to
   OpenTripPlanner is the right path if v1 numbers feel wrong.
2. **Overpass POI data is community-tagged**, so coverage varies. A halal
   grocery that exists IRL might not be tagged that way in OSM. Yelp Fusion
   API would fill gaps but introduces a key + rate limit.
3. **Personal data publicness.** `submissions/*.md` is gitignored by default.
   But the resulting `docs/index.html` (rendered report) IS public on Pages
   and contains addresses + family decisions. If that's a concern, the
   alternative is making the Pages site auth-gated (overkill for personal
   use, complicates the architecture).
4. **Apps Script execution-time limit.** `doGet` is capped at 30 seconds.
   With OG pre-fetch per URL, a sheet with 20+ pending entries would time
   out on first run. Mitigation: process in batches or move pre-fetch to a
   separate `doPost`/scheduled trigger. Not a problem at current scale.

## References

- `tools/enrich_dryrun.py` — proof-of-concept that generated the dry-run
  results above. Run with `.venv/bin/python tools/enrich_dryrun.py`. Looks
  in repo root for `*.md` Web Clipper outputs.
- `submissions/README.md` — intake-side docs (drop a clip → what happens)
- `tools/apps_script.gs` — current Apps Script (hyperlink resolution + OG
  pre-fetch). Needs no further changes for the pivot.
- `CLAUDE.md` — describes the *current* shipped architecture. Will be
  rewritten after Phase 4 ships.
- Active branch `external-fallback-and-og-enrich` carries the slug fallback
  + OG enrichment work; merge it before starting Phase 1 (it's strictly
  additive and the Apps Script side is already deployed).
