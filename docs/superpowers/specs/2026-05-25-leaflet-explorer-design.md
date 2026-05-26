# Leaflet Explorer — Design Spec

**Date:** 2026-05-25
**Status:** Approved (sections 1–5 confirmed in brainstorming)
**Successor to:** the 3-tab Inbox/Shortlist/Map UI in `report.py`
**Companion to:** `PLAN.md` (the broader Khoj pivot to a decision-support tool)

## Goal

Replace Khoj's current 3-tab report with a **unified Leaflet explorer**: one
map is the primary surface, every submission renders as a pin colored by
fit-score, with toggleable enrichment overlays (noise, crime, POIs, commute)
and a Zillow-style list rail + slide-in detail panel.

The map *is* the app. The current 3-tab structure goes away.

## Non-goals

- Real-time data. The cron-once-a-day model stays.
- Authentication / private deploys. Pages site stays public; address-level
  data is the existing trade-off.
- Replacing the SVG mini-maps in row cards — those are deliberately not
  Leaflet (see CLAUDE.md). They're gone in this design because the row
  cards themselves are gone.
- Mobile-first design. Desktop is primary; mobile is a sensible fallback.

## Section 1 — Three tiers (separation of concerns)

```
┌─────────────────────────────────────────────────────────────────┐
│  DATA TIER (Python, runs at scrape time)                        │
│  Owns: fetching, parsing, geocoding, enrichment, scoring.       │
│  Outputs: one Listing payload + static overlay GeoJSON files.   │
│  Pure functions where possible; cached on disk by key.          │
└─────────────────────────────────────────────────────────────────┘
                              │  (writes)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  RENDER TIER (Python, runs after data tier)                     │
│  Owns: emitting the HTML shell + embedding the Listing payload  │
│  as a JS const. Does NOT contain CSS or JS source — only the    │
│  <link> + <script type="module"> tags pointing at docs/.        │
│  Thin: report.py shrinks from 1698 → ~150 lines.                │
└─────────────────────────────────────────────────────────────────┘
                              │  (page load)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  BROWSER TIER (ES modules, runs in user's browser)              │
│  Owns: filter/sort state, Leaflet init, layer registry,         │
│  list/map sync, detail panel, persistence (localStorage).       │
│  One module per concern, imported by a small main entry.        │
└─────────────────────────────────────────────────────────────────┘
```

**Boundary rules:**

- Data tier never knows about HTML/CSS.
- Render tier never knows about Leaflet APIs or filter logic — it just hands
  the browser a payload.
- Browser tier never makes a network request for listing data (it's already
  inline); it *does* fetch overlay GeoJSONs lazily when a layer toggles on.

## Section 2 — File layout

**Data tier** (Python, repo root + `tools/`)

```
scraper.py                 thin orchestrator: load submissions, scrape CL,
                           call enrich, score, emit payload + CSV
submission.py              [currently untracked] Web Clipper .md → Listing
enrich.py                  [currently untracked] geocode, commute, noise,
                           crime, POIs — keyed cache on disk
score.py                   [NEW] fit-score per listing (price, commute,
                           safety, south-asian access). Pure function.
tools/build_overlays.py    [NEW] one-shot: NYPD CompStat → crime choropleth
                           GeoJSON. Cron runs this weekly. (Other overlays
                           already exist under docs/data/.)
.cache/                    [NEW, gitignored] enrichment cache (geohash-keyed)
```

**Render tier** (Python package replacing the monolithic `report.py`)

```
report/__init__.py         re-exports build_report() for back-compat
report/__main__.py         CLI entry: `python -m report`
report/build.py            orchestrator: stitch payload + template → write html
report/payload.py          Listing list + filter defaults + map config → dict
                           that becomes the JS const window.KHOJ
report/template.py         HTML shell (head, body skeleton, <link>+<script>
                           tags). No CSS, no JS source.
```

**Browser tier** (`docs/khoj/`, served by Pages)

```
docs/khoj/khoj.css         all styles (tokens + layout + map + panel + list)
docs/khoj/main.js          entry: reads window.KHOJ, wires up modules
docs/khoj/state.js         filter/sort/selection store + localStorage persist
docs/khoj/map.js           Leaflet init, tile layers, marker management
docs/khoj/overlays.js      lazy-load + toggle: noise heatmap, crime
                           choropleth, POI markers, commute path
docs/khoj/list.js          left-rail list rendering + sort + list↔map sync
docs/khoj/panel.js         right-side detail panel: open/close, content render
docs/khoj/filters.js       top-bar filter chips + threshold controls
docs/data/nta-noise.geojson         (already exists, reused)
docs/data/commute-zone.geojson      (already exists, reused)
docs/data/parks.geojson             (already exists, reused)
docs/data/subway-lines.geojson      (already exists, reused)
docs/data/subway-stations.geojson   (already exists, reused)
docs/data/crime.geojson             [NEW, produced by tools/build_overlays.py]
```

**Naming conventions:**

- One default-export per JS module (`createX()` factory), no globals;
  `main.js` is the only place state crosses modules.
- Python `snake_case`; JS files `kebab-case`/`lower-camel` to match existing
  repo conventions.

## Section 3 — Data contract (Python → browser)

**Inline payload**, embedded in HTML as `window.KHOJ` (~50–300 KB depending
on listing count):

```js
window.KHOJ = {
  generated_at: "2026-05-25T14:30:00Z",
  campus: { lat: 40.6942, lng: -73.9857, label: "NYU Tandon" },
  listings: [
    {
      id: "cl-7234567890",            // stable id (source + posting id)
      source: "craigslist" | "submission",
      url: "https://...",             // outbound link
      title: "Sunny 1BR off Nostrand",
      price: 1450,                    // null if unknown
      beds: 1,                        // null if unknown / shared
      lat: 40.6807, lng: -73.9443,
      address: "50 MacDonough St, Brooklyn, NY",
      neighborhood: "Bedford-Stuyvesant",
      posted_at: "2026-05-24",        // ISO date or null
      score: 0.82,                    // 0..1, drives pin color/size
      enrichment: {
        commute: { total_min: 14, walk_min: 3, rail_min: 11,
                   station: { name: "Kingston-Throop", lines: ["C"],
                              lat: 40.68, lng: -73.94 } },
        noise:   { count_12mo: 289, top_category: "Loud Music/Party" },
        crime:   { total_12mo: 236, felonies: 70, misd: 134, viol: 32 },
        food:    [ { name: "India House", lat: ..., lng: ..., dist_mi: 0.32 }, ... ],
        grocery: [ { name: "Nouri Halal Meat", lat: ..., lng: ...,
                     dist_mi: 0.46, south_asian: true }, ... ]
      }
    }
    // ...
  ],
  filter_defaults: { max_price: 1500, max_commute: 30,
                     hide_hidden: true, only_starred: false },
  tiles: { url: "...", attribution: "..." }   // current map config
};
```

**Static overlay files** (fetched lazily by `overlays.js` when a layer
toggles on):

| File | Type | When fetched |
|---|---|---|
| `docs/data/nta-noise.geojson` | Polygons (prop: `complaints`) | On "Noise" toggle |
| `docs/data/crime.geojson` *(new)* | Polygons per precinct (props: `felonies`, `misd`, `viol`) | On "Crime" toggle |
| `docs/data/subway-lines.geojson` | LineStrings | Always on |
| `docs/data/subway-stations.geojson` | Points | Always on |
| `docs/data/commute-zone.geojson` | ~30-min isochrone polygon | Always on, drawn faintly under listings |
| `docs/data/parks.geojson` | Polygons | On "Parks" toggle |

**Contract rules:**

- Render tier writes `window.KHOJ` exactly as shown — no client-side
  transformation.
- Browser tier never mutates `window.KHOJ.listings`; filtered views are
  derived in `state.js`.
- Per-listing POI markers (`food`/`grocery`) are embedded in the payload,
  not fetched per-click. They're shown only when a listing is selected.
- All coordinates are `[lat, lng]` to match Leaflet's convention. Python
  writes them this way; no swap client-side.

## Section 4 — UI & interaction spec

**Desktop layout (≥ 1024px):**

```
┌──────────────────────────────────────────────────────────────────────┐
│  TOP BAR (50px)                                                      │
│  Khoj • generated 2026-05-25 • [chips: Price ≤$1500] [Commute ≤30m] │
│  [South-Asian food ≤1mi] [☆ Starred only] [⊘ Hide rejected]  [sort▾] │
├──────────────┬───────────────────────────────────────────────────────┤
│              │                                                       │
│  LIST RAIL   │                        MAP                            │
│  (400px)     │                  (fills rest)                         │
│              │                                                       │
│  ┌────────┐  │           [+/-] zoom            [layers ▾]            │
│  │ row    │  │                                                       │
│  │ row*   │  │              ● ● ● ●  (listing pins)                  │
│  │ row    │  │                                                       │
│  │ ...    │  │              ★ Tandon                                 │
│  └────────┘  │                                                       │
│   (scroll)   │                                                       │
└──────────────┴───────────────────────────────────────────────────────┘
```

When a pin or row is clicked, a **right detail panel** (420 px wide) slides
in over the map. Map dims to 70 % opacity beneath it. Close = ✕ or Esc.

**Mobile layout (< 768px):** list rail collapses into a bottom drawer with a
handle; map fills the viewport; detail panel becomes a full-screen overlay.
The existing mobile fallback in `report.py:771` is replaced.

**Interaction flows (five concrete behaviors):**

1. **Filter chip clicked** → `state.js` updates `filters`; `list.js`
   re-renders rows; `map.js` updates pin visibility (excluded pins get
   `.hidden-pin` class with low opacity rather than being removed — keeps
   mental model stable). Persisted to `localStorage` under `khoj.filters`.
2. **List row hovered** → matching pin pulses + zooms slightly. No map
   recenter (annoying when scanning).
3. **List row clicked OR pin clicked** → `state.js` sets `selectedId`.
   `panel.js` slides in. `overlays.js` draws the commute path
   (listing → station → Tandon) + reveals POI markers within 1 mi for that
   listing. Map gently pans (not zooms) so the selected pin sits in the
   visible-map area not under the panel.
4. **Layer toggle** → `overlays.js` either reveals an already-fetched layer
   or `fetch()`s its GeoJSON the first time, then adds it to the map. State
   persisted under `khoj.layers`. On page load, any layer that was persisted
   `on` is fetched eagerly before first paint so the map doesn't flash
   without it.
5. **Star / hide / note (in detail panel)** → `state.js` writes to
   `khoj.starred` / `khoj.hidden` / `khoj.notes` (existing keys, preserved
   for back-compat). Pin re-styles immediately; list row re-renders.

**Pin styling rules** (score encoded without legend-hunting):

- Color ramp: muted ink → crimson as `score` climbs 0 → 1.
- Size: 10 px (score < 0.4), 14 px (0.4–0.7), 18 px (≥ 0.7).
- ☆ Starred: gold outline ring.
- ⊘ Hidden (when `hide_hidden=false`): 30 % opacity, no outline.

**Keyboard:** `j`/`k` next/prev listing in current sort, `s` star, `h`
hide, `Esc` close panel, `/` focus filter bar.

**Empty states:** if filters exclude all listings, list rail shows "0 of 47
match — [Reset filters]". Map keeps all pins faded.

**Accessibility:** every pin is also a row; every row has `aria-label` with
title + price + commute. Detail panel is `role="dialog"` with focus trap +
Esc close.

## Section 5 — Build sequence

Each phase ends with `python -m report` producing a working `docs/index.html`
that opens correctly on Pages — no half-broken intermediate states.

### Phase 1 — Refactor the render tier (no UX change) — *delegated to a separate agent*

**Goal:** invisible to users; sets up the file layout.

- Split `report.py` (1698 lines) into the `report/` package: `template.py`
  (HTML shell), `payload.py` (`window.KHOJ` dict), `build.py` (orchestrator),
  `__main__.py` (CLI).
- Move embedded CSS string → `docs/khoj/khoj.css`. Reference via `<link>`.
- Move embedded JS → `docs/khoj/main.js` as a single module for now (split
  happens in Phase 2). Reference via `<script type="module">`.
- Keep current UI behavior identical (3-tab Inbox / Shortlist / Map still
  works).
- **Done when:** local + Pages render byte-equivalent output to today, but
  from the new file layout.

> Phase 1 is owned by a separate agent and is in flight. Phases 2–5 below
> are this plan's scope and assume Phase 1's file layout exists.

### Phase 2 — Split browser tier into modules + adopt list+map layout

**Goal:** new Zillow-style split appears; functionality preserved.

- Split `main.js` → `state.js`, `map.js`, `list.js`, `panel.js`,
  `filters.js`. `main.js` becomes the wiring entry.
- Replace 3-tab structure with the new top-bar + left-list + map layout
  (Section 4 layout diagram).
- `state.js` owns filters, sort, selection; `localStorage` keys
  `khoj.starred`/`hidden`/`notes` preserved.
- Existing pins + subway layer still work; detail panel is the existing
  Leaflet popup content reformatted into a side panel.
- **Done when:** every interaction the 3-tab version supported still works,
  plus list↔map hover/click sync.

### Phase 3 — Wire enrichment into the payload

**Goal:** detail panel gets rich.

- Land `submission.py` (already untracked) — Web Clipper `.md` → Listing.
- Land `enrich.py` (already untracked) + new `score.py` — every Listing
  gets `enrichment.{commute,noise,crime,food,grocery}` and a `score`.
- Update `payload.py` to emit the full contract from Section 3.
- `panel.js` renders the rich detail card (commute breakdown, safety stats,
  POI lists).
- Pin color/size driven by `score` (Section 4 pin styling).
- **Done when:** clicking a submission pin shows the full enriched card;
  Craigslist listings show enrichment too where available.

### Phase 4 — Interactive overlays

**Goal:** all toggleable map layers light up.

- `overlays.js` — lazy-loads GeoJSONs on toggle, manages layer registry,
  persists state under `khoj.layers`.
- Wire existing files (`nta-noise.geojson`, `commute-zone.geojson`,
  `parks.geojson`, `subway-lines.geojson`) into the layers control.
- New `tools/build_overlays.py` produces the missing
  `docs/data/crime.geojson` from NYPD CompStat SODA API (same pattern as
  existing `tools/build_*.py`).
- Add commute-path drawing + per-listing POI reveal on pin click.
- **Done when:** layers control toggles all six overlays; selecting a pin
  draws its commute path and reveals its POIs.

### Phase 5 — Filter chips + polish

**Goal:** ship-ready.

- `filters.js` — chips for Price (≤$N), Commute (≤N min), South-Asian food
  (≥1 grocery OR ≥1 restaurant within 1 mi), Starred-only, Hide-rejected;
  sort dropdown.
- Keyboard shortcuts (`j`/`k`/`s`/`h`/`Esc`/`/`).
- Empty states ("0 of 47 match — Reset filters").
- Accessibility pass: pin `aria-label`s, panel focus trap, dialog roles.
- Mobile bottom-drawer + full-screen detail-panel layout.
- **Done when:** the spec's full interaction model (Section 4) is live and
  tested in Chrome + Safari mobile.

### Cron change (one line in `.github/workflows/scrape.yml`)

- Add weekly trigger to run `python tools/build_overlays.py` (refreshes
  `docs/data/crime.geojson`). Daily cron stays the same; it just runs
  `python -m report`.

## Open questions / risks

1. **Payload size.** Embedding per-listing POI lists inflates `window.KHOJ`.
   At ~50 listings × ~10 POIs each, still well under 500 KB. If it grows
   past ~1 MB we should switch POIs to a per-listing fetch.
2. **`crime.geojson` data quality.** NYPD CompStat's SODA API returns
   precinct-level aggregates that update monthly. Weekly cron is overkill
   but cheap; can drop to monthly if rate-limited.
3. **Mobile detail panel.** Full-screen overlay vs. bottom sheet — Section 4
   says full-screen; revisit if it feels heavy in Phase 5 testing.
4. **Score weights.** `score.py` is not specified — weights for price /
   commute / safety / food access are a design decision deferred to Phase 3.
   Pick defaults that match the family's stated priorities, then tune.

## References

- `PLAN.md` — broader pivot rationale and intake architecture
- `CLAUDE.md` — project conventions (typography, color tokens, "what not
  to do" list, mini-map rationale)
- `tools/enrich_dryrun.py` — proof-of-concept for the enrichment pipeline
- Recent commits: `ef8b034` (Web Clipper drop zone), `ed737fb` (map polish)
