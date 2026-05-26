# Leaflet Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Khoj's 3-tab report with a unified Leaflet explorer — Zillow-style list+map split, score-driven pins, rich enrichment overlays, slide-in detail panel.

**Architecture:** Three tiers. Data tier (Python) writes a `window.KHOJ` JS payload + static overlay GeoJSONs. Render tier (`report/` package) emits an HTML shell that loads `docs/khoj/*.js` ES modules + `docs/khoj/khoj.css`. Browser tier wires Leaflet + filter/sort/selection state, with localStorage persistence.

**Tech Stack:** Python 3.11 + requests + BeautifulSoup; ES2020 modules + Leaflet 1.9.4; pytest (newly added) for Python pure-function tests; no browser test framework — verify via `python -m report --pages-mode` + open `docs/index.html` locally.

**Spec:** `docs/superpowers/specs/2026-05-25-leaflet-explorer-design.md`

---

## Preconditions (Phase 1 — done by another agent)

Phase 1 of the spec — refactoring `report.py` (1698 lines) into the `report/` package and moving CSS/JS to `docs/khoj/khoj.css` + `docs/khoj/main.js` — is owned by a separate agent. Before starting this plan, verify Phase 1 is landed:

- [ ] **Precondition check**

Run:
```bash
ls report/__main__.py report/build.py report/payload.py report/template.py
ls docs/khoj/khoj.css docs/khoj/main.js
python -m report --pages-mode && ls docs/index.html
```
Expected: all files exist; `python -m report --pages-mode` writes `docs/index.html` byte-equivalent to today's output. If any check fails, **stop** and ask the user before continuing — Phase 1 isn't ready.

---

## Phase 2 — Browser-tier modules + list+map layout

**Outcome:** the 3-tab UI is replaced with the new top-bar + left-list + map + slide-in-panel layout. All existing functionality (star/hide/note, pin click, subway layer) preserved. No new data yet.

### Task 1: Create empty browser-tier modules

**Files:**
- Create: `docs/khoj/state.js`
- Create: `docs/khoj/map.js`
- Create: `docs/khoj/list.js`
- Create: `docs/khoj/panel.js`
- Create: `docs/khoj/filters.js`
- Create: `docs/khoj/overlays.js`

- [ ] **Step 1: Create the six module files with stub exports**

Each file is one default-exported factory that takes nothing yet and returns an empty object. This locks the import shape so later tasks can fill in bodies without touching `main.js`.

```js
// docs/khoj/state.js
export function createState() {
  return {};
}
```

```js
// docs/khoj/map.js
export function createMap(_state) {
  return {};
}
```

```js
// docs/khoj/list.js
export function createList(_state) {
  return {};
}
```

```js
// docs/khoj/panel.js
export function createPanel(_state) {
  return {};
}
```

```js
// docs/khoj/filters.js
export function createFilters(_state) {
  return {};
}
```

```js
// docs/khoj/overlays.js
export function createOverlays(_state, _map) {
  return {};
}
```

- [ ] **Step 2: Commit**

```bash
git add docs/khoj/state.js docs/khoj/map.js docs/khoj/list.js \
        docs/khoj/panel.js docs/khoj/filters.js docs/khoj/overlays.js
git commit -m "Browser tier: scaffold the six explorer modules"
```

### Task 2: Implement state.js (store + localStorage persistence)

**Files:**
- Modify: `docs/khoj/state.js`

State is a tiny pub-sub: get/set keys, subscribe to changes, persist a denylist of keys to localStorage. No framework, ~60 lines.

- [ ] **Step 1: Replace state.js with the store implementation**

```js
// docs/khoj/state.js
const LS_PREFIX = "khoj.";
const PERSISTED = new Set([
  "starred", "hidden", "notes", "filters", "layers", "sort",
]);

export function createState(initial = {}) {
  const data = { ...initial };
  const listeners = new Map();   // key -> Set<fn>

  for (const key of PERSISTED) {
    try {
      const raw = localStorage.getItem(LS_PREFIX + key);
      if (raw !== null) data[key] = JSON.parse(raw);
    } catch { /* corrupt entry — leave default */ }
  }

  function get(key) { return data[key]; }

  function set(key, value) {
    data[key] = value;
    if (PERSISTED.has(key)) {
      try { localStorage.setItem(LS_PREFIX + key, JSON.stringify(value)); }
      catch { /* quota or private mode — skip */ }
    }
    const subs = listeners.get(key);
    if (subs) for (const fn of subs) fn(value);
  }

  function subscribe(key, fn) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(fn);
    return () => listeners.get(key).delete(fn);
  }

  return { get, set, subscribe };
}
```

- [ ] **Step 2: Smoke-test in browser console**

Run: `python -m report --pages-mode` then open `docs/index.html` in a browser. Open devtools console and paste:
```js
const m = await import("./khoj/state.js");
const s = m.createState({ filters: { max_price: 1500 } });
s.subscribe("filters", v => console.log("filters changed:", v));
s.set("filters", { max_price: 1200 });
// Expected: console logs "filters changed: { max_price: 1200 }"
// And: localStorage.getItem("khoj.filters") returns the stringified object.
```

- [ ] **Step 3: Commit**

```bash
git add docs/khoj/state.js
git commit -m "Browser tier: state store with localStorage persistence"
```

### Task 3: Move existing Leaflet init out of main.js into map.js

**Files:**
- Modify: `docs/khoj/main.js`
- Modify: `docs/khoj/map.js`

Lift the `L.map(...)`, tile-layer, campus marker, subway-station layer, and per-listing marker creation out of `main.js` into `map.js`. Keep behavior identical for now — just relocate. Existing functions in `main.js` (Phase 1 output) called something like `initMap()` / `addMarker()`; move them verbatim and expose them via the factory.

- [ ] **Step 1: Implement map.js**

```js
// docs/khoj/map.js
export function createMap(state, mountId = "khoj-map") {
  const cfg = window.KHOJ;
  const campus = [cfg.campus.lat, cfg.campus.lng];

  const map = L.map(mountId, { scrollWheelZoom: false }).setView(campus, 13);
  L.tileLayer(cfg.tiles.url, { attribution: cfg.tiles.attribution }).addTo(map);

  L.marker(campus, {
    icon: L.divIcon({
      className: "khoj-campus-marker",
      html: `<span class="khoj-campus-dot"></span><span class="khoj-campus-label">${cfg.campus.label}</span>`,
    }),
  }).addTo(map);

  const markerByUrl = new Map();
  function addListing(listing) {
    const marker = L.marker([listing.lat, listing.lng], {
      icon: L.divIcon({
        className: "khoj-pin",
        html: `<span class="khoj-pin-dot" data-score="${listing.score ?? 0}"></span>`,
      }),
    });
    marker.bindPopup(
      `<b>${listing.title}</b><br>$${listing.price ?? "?"} · ${listing.beds ?? "?"}BR` +
      `<br><a href="${listing.url}" target="_blank" rel="noopener">View listing →</a>`,
    );
    marker.on("click", () => state.set("selectedId", listing.id));
    marker.addTo(map);
    markerByUrl.set(listing.id, marker);
  }

  for (const l of cfg.listings) {
    if (l.lat != null && l.lng != null) addListing(l);
  }

  return { map, markerByUrl };
}
```

- [ ] **Step 2: Slim main.js to wiring only**

Replace the body of `docs/khoj/main.js` with:

```js
// docs/khoj/main.js
import { createState } from "./state.js";
import { createMap } from "./map.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

createMap(state, "khoj-map");
```

- [ ] **Step 3: Update report/template.py to provide the right mount-point IDs**

Open `report/template.py` and locate where the `<body>` is emitted. Replace the existing 3-tab structure (`<nav>` + `<section class="view">×3`) with the new layout shell:

```html
<header id="khoj-topbar"></header>
<main id="khoj-app">
  <aside id="khoj-list"></aside>
  <div id="khoj-map"></div>
  <aside id="khoj-panel" aria-hidden="true"></aside>
</main>
```

(If `report/template.py` keeps the HTML as a Python string, edit it there. If Phase 1 split it into a `.html.j2` or similar, edit that.)

- [ ] **Step 4: Run scraper + open in browser**

Run: `python -m report --pages-mode`
Open `docs/index.html` in a browser. Expected: map renders with campus pin, listing pins, and tile layer. Console shows no errors. Clicking a pin opens its popup. (No list/panel/topbar content yet — those are stubs.)

- [ ] **Step 5: Commit**

```bash
git add docs/khoj/main.js docs/khoj/map.js report/template.py
git commit -m "Browser tier: extract map module + new layout shell"
```

### Task 4: Implement list.js (left-rail rows, sort, list↔map sync)

**Files:**
- Modify: `docs/khoj/list.js`
- Modify: `docs/khoj/khoj.css` (add list styles)
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Implement list.js**

```js
// docs/khoj/list.js
const SORTS = {
  score:   (a, b) => (b.score ?? 0) - (a.score ?? 0),
  price:   (a, b) => (a.price ?? Infinity) - (b.price ?? Infinity),
  commute: (a, b) => (a.enrichment?.commute?.total_min ?? Infinity)
                   - (b.enrichment?.commute?.total_min ?? Infinity),
  posted:  (a, b) => (b.posted_at ?? "").localeCompare(a.posted_at ?? ""),
};

export function createList(state, mountId = "khoj-list", map = null) {
  const root = document.getElementById(mountId);

  function rowHtml(l) {
    const price = l.price ? `$${l.price}` : "—";
    const beds = l.beds == null ? "?" : (l.beds === 0 ? "Studio" : `${l.beds}BR`);
    const commute = l.enrichment?.commute?.total_min;
    const score = l.score == null ? "" : `<span class="khoj-row-score">${Math.round(l.score * 100)}</span>`;
    return `<article class="khoj-row" data-id="${l.id}" tabindex="0"
              aria-label="${l.title}, ${price}, ${commute ? commute + ' min commute' : ''}">
      ${score}
      <h3>${l.title}</h3>
      <p class="khoj-row-meta">${price} · ${beds}${commute ? ` · ${commute}m` : ""}</p>
      <p class="khoj-row-hood">${l.neighborhood ?? ""}</p>
    </article>`;
  }

  function render() {
    const sortKey = state.get("sort") || "score";
    const sorted = [...window.KHOJ.listings].sort(SORTS[sortKey] || SORTS.score);
    root.innerHTML = sorted.map(rowHtml).join("");
  }

  root.addEventListener("click", (e) => {
    const row = e.target.closest(".khoj-row");
    if (row) state.set("selectedId", row.dataset.id);
  });

  root.addEventListener("mouseover", (e) => {
    const row = e.target.closest(".khoj-row");
    if (!row || !map) return;
    const marker = map.markerByUrl.get(row.dataset.id);
    if (marker) marker.getElement()?.classList.add("khoj-pin--hover");
  });

  root.addEventListener("mouseout", (e) => {
    const row = e.target.closest(".khoj-row");
    if (!row || !map) return;
    const marker = map.markerByUrl.get(row.dataset.id);
    if (marker) marker.getElement()?.classList.remove("khoj-pin--hover");
  });

  state.subscribe("sort", render);
  render();
  return { render };
}
```

- [ ] **Step 2: Add list CSS to khoj.css**

Append to `docs/khoj/khoj.css`:

```css
/* List rail */
#khoj-list { overflow-y: auto; border-right: 1px solid var(--rule); padding: 0; }
.khoj-row {
  padding: 14px 16px; border-bottom: 1px solid var(--rule-soft);
  cursor: pointer; position: relative;
}
.khoj-row:hover, .khoj-row:focus { background: var(--paper-warm); outline: none; }
.khoj-row h3 {
  font-family: var(--serif-display); font-size: var(--type-lead);
  font-weight: 600; margin: 0 0 4px; line-height: var(--leading-tight);
}
.khoj-row-meta { font-family: var(--mono); font-size: var(--type-mono); margin: 0; color: var(--ink-soft); }
.khoj-row-hood { font-size: var(--type-small); color: var(--ink-mute); margin: 4px 0 0; }
.khoj-row-score {
  position: absolute; top: 14px; right: 16px;
  font-family: var(--mono); font-size: var(--type-small); color: var(--crimson);
}

/* App layout */
#khoj-app { display: grid; grid-template-columns: 400px 1fr; height: calc(100vh - 50px); }
#khoj-topbar { height: 50px; border-bottom: 1px solid var(--rule); padding: 0 16px;
               display: flex; align-items: center; gap: 12px; }

/* Pin hover */
.khoj-pin--hover .khoj-pin-dot { transform: scale(1.3); transition: transform 120ms; }
```

(If `khoj.css` uses different token names from Phase 1's CSS extraction, adapt — read the file first to match.)

- [ ] **Step 3: Wire list into main.js**

Replace `docs/khoj/main.js`:

```js
import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

const map = createMap(state, "khoj-map");
createList(state, "khoj-list", map);
```

- [ ] **Step 4: Verify in browser**

Run: `python -m report --pages-mode`
Open `docs/index.html`. Expected: list rail on the left shows sorted rows; hovering a row scales the matching pin; clicking a row sets selection (no visible effect yet — panel comes in Task 5).

- [ ] **Step 5: Commit**

```bash
git add docs/khoj/list.js docs/khoj/khoj.css docs/khoj/main.js
git commit -m "Browser tier: list rail with sort + list↔map hover sync"
```

### Task 5: Implement panel.js (slide-in detail panel)

**Files:**
- Modify: `docs/khoj/panel.js`
- Modify: `docs/khoj/khoj.css`
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Implement panel.js**

```js
// docs/khoj/panel.js
export function createPanel(state, mountId = "khoj-panel") {
  const root = document.getElementById(mountId);

  function close() { state.set("selectedId", null); }

  function render(id) {
    if (!id) {
      root.setAttribute("aria-hidden", "true");
      root.innerHTML = "";
      return;
    }
    const l = window.KHOJ.listings.find((x) => x.id === id);
    if (!l) { close(); return; }

    const starred = (state.get("starred") || []).includes(id);
    const hidden  = (state.get("hidden")  || []).includes(id);
    const note    = (state.get("notes") || {})[id] || "";

    root.innerHTML = `
      <button class="khoj-panel-close" aria-label="Close">✕</button>
      <header>
        <h2>${l.title}</h2>
        <p class="khoj-panel-meta">
          ${l.price ? "$" + l.price : "—"} · ${l.beds == null ? "?" : (l.beds === 0 ? "Studio" : l.beds + "BR")}
          · <a href="${l.url}" target="_blank" rel="noopener">source ↗</a>
        </p>
        <p class="khoj-panel-addr">${l.address ?? ""}</p>
      </header>
      <section class="khoj-panel-actions">
        <button data-action="star">${starred ? "★ Starred" : "☆ Star"}</button>
        <button data-action="hide">${hidden ? "⊘ Hidden" : "⊘ Hide"}</button>
      </section>
      <section class="khoj-panel-note">
        <label>Note<textarea data-action="note">${note}</textarea></label>
      </section>
      <section class="khoj-panel-enrichment" id="khoj-panel-enrich"></section>
    `;
    root.setAttribute("aria-hidden", "false");

    root.querySelector(".khoj-panel-close").addEventListener("click", close);
    root.querySelector("[data-action=star]").addEventListener("click", () => {
      const cur = state.get("starred") || [];
      state.set("starred", cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
      render(id);
    });
    root.querySelector("[data-action=hide]").addEventListener("click", () => {
      const cur = state.get("hidden") || [];
      state.set("hidden", cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
      render(id);
    });
    root.querySelector("[data-action=note]").addEventListener("input", (e) => {
      const cur = { ...(state.get("notes") || {}) };
      cur[id] = e.target.value;
      state.set("notes", cur);
    });
  }

  state.subscribe("selectedId", render);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  return { render };
}
```

- [ ] **Step 2: Add panel CSS**

Append to `docs/khoj/khoj.css`:

```css
#khoj-panel {
  position: absolute; top: 50px; right: 0; bottom: 0; width: 420px;
  background: var(--paper); border-left: 1px solid var(--rule);
  padding: 24px; overflow-y: auto; z-index: 500;
  transform: translateX(100%); transition: transform 200ms ease;
}
#khoj-panel[aria-hidden="false"] { transform: translateX(0); }
#khoj-panel header h2 { font-family: var(--serif-display); margin: 0; }
.khoj-panel-close {
  position: absolute; top: 12px; right: 12px;
  background: none; border: none; font-size: 1.25rem; cursor: pointer;
}
.khoj-panel-actions button { margin-right: 8px; padding: 6px 10px; }
.khoj-panel-note textarea { width: 100%; min-height: 80px; margin-top: 6px; }
```

- [ ] **Step 3: Wire panel into main.js + dim map when panel open**

Replace `docs/khoj/main.js`:

```js
import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

const map = createMap(state, "khoj-map");
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");

state.subscribe("selectedId", (id) => {
  document.getElementById("khoj-map").classList.toggle("dimmed", !!id);
});
```

Add to `khoj.css`:
```css
#khoj-map.dimmed { opacity: 0.7; transition: opacity 150ms; }
```

- [ ] **Step 4: Verify in browser**

Run: `python -m report --pages-mode`, open `docs/index.html`. Expected: clicking a pin or row slides the panel in from the right with title/price/address; star/hide/note buttons work and persist across reload; ✕ and Esc both close.

- [ ] **Step 5: Commit**

```bash
git add docs/khoj/panel.js docs/khoj/khoj.css docs/khoj/main.js
git commit -m "Browser tier: slide-in detail panel with star/hide/note"
```

### Task 6: Phase 2 smoke-test + commit checkpoint

- [ ] **Step 1: Manual smoke checklist**

Open `docs/index.html` and verify each:

1. List rail shows all listings sorted by score descending.
2. Hovering a row pulses the matching pin.
3. Clicking a row opens the panel.
4. Clicking a pin opens the panel for that listing.
5. Star a listing, reload page — still starred.
6. Hide a listing, reload — still hidden (visual treatment comes in Phase 5).
7. Type a note, reload — note preserved.
8. Esc closes the panel.
9. Subway stations + tile layer still render.
10. Console: zero errors.

- [ ] **Step 2: If any fail, fix before moving on**

Phase 3 assumes Phase 2 is solid.

---

## Phase 3 — Wire enrichment into the payload

**Outcome:** every listing has `enrichment.{commute,noise,crime,food,grocery}` and a 0–1 `score`. Panel renders the rich card. Pin color/size driven by score.

### Task 7: Add pytest + scaffold tests directory

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add pytest to requirements.txt**

Append to `requirements.txt`:
```
pytest==8.3.3
```

Install: `python -m pip install -r requirements.txt`

- [ ] **Step 2: Create tests directory**

```bash
mkdir -p tests
touch tests/__init__.py
```

Create `tests/conftest.py` with one fixture: a sample Listing-shape dict that other tests reuse.

```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_listing():
    return {
        "id": "test-1",
        "source": "submission",
        "url": "https://example.com/x",
        "title": "Test 1BR",
        "price": 1400,
        "beds": 1,
        "lat": 40.6807, "lng": -73.9443,
        "address": "50 MacDonough St, Brooklyn, NY",
        "neighborhood": "Bedford-Stuyvesant",
        "posted_at": "2026-05-24",
        "enrichment": {
            "commute": {"total_min": 14, "walk_min": 3, "rail_min": 11,
                        "station": {"name": "Kingston-Throop", "lines": ["C"],
                                    "lat": 40.68, "lng": -73.94}},
            "noise":   {"count_12mo": 289, "top_category": "Loud Music/Party"},
            "crime":   {"total_12mo": 236, "felonies": 70, "misd": 134, "viol": 32},
            "food":    [{"name": "India House", "lat": 40.68, "lng": -73.94, "dist_mi": 0.32}],
            "grocery": [{"name": "Nouri Halal Meat", "lat": 40.68, "lng": -73.94,
                         "dist_mi": 0.46, "south_asian": True}],
        },
    }
```

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/ -v`
Expected: "no tests ran" (no failures, just zero tests collected).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "Add pytest + tests/ scaffolding for the data tier"
```

### Task 8: Implement score.py (TDD)

**Files:**
- Create: `tests/test_score.py`
- Create: `score.py`

The fit-score is a weighted blend of (a) commute, (b) safety, (c) south-asian access, (d) price. Returns 0..1. Each input is bounded; missing enrichment fields skip that weight rather than penalize.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_score.py`:

```python
from score import compute_score

def test_perfect_listing_scores_near_one(sample_listing):
    # tweak sample to be near-perfect: short commute, low crime, has SA grocery, cheap
    l = {**sample_listing}
    l["enrichment"] = {**l["enrichment"]}
    l["enrichment"]["commute"] = {**l["enrichment"]["commute"], "total_min": 10}
    l["enrichment"]["crime"]   = {**l["enrichment"]["crime"], "felonies": 10, "total_12mo": 40}
    l["price"] = 1100
    assert compute_score(l) > 0.85

def test_bad_commute_drops_score(sample_listing):
    l = {**sample_listing}
    l["enrichment"] = {**l["enrichment"]}
    l["enrichment"]["commute"] = {**l["enrichment"]["commute"], "total_min": 60}
    assert compute_score(l) < compute_score(sample_listing)

def test_missing_enrichment_does_not_crash(sample_listing):
    l = {**sample_listing, "enrichment": {}}
    s = compute_score(l)
    assert 0.0 <= s <= 1.0

def test_returns_in_unit_interval(sample_listing):
    s = compute_score(sample_listing)
    assert 0.0 <= s <= 1.0
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `python -m pytest tests/test_score.py -v`
Expected: `ModuleNotFoundError: No module named 'score'`

- [ ] **Step 3: Implement score.py**

```python
# score.py
"""Fit-score per listing (0..1). Higher = better fit.

Weighted blend of commute, safety, south-asian access, price. Missing
enrichment skips that weight rather than penalizing — a listing without
crime data isn't worse than one with low crime, it's just unknown.
"""
from __future__ import annotations

W_COMMUTE = 0.35
W_SAFETY  = 0.25
W_SA      = 0.20
W_PRICE   = 0.20

PRICE_FLOOR = 800
PRICE_CEIL  = 2000


def _commute_score(c: dict | None) -> float | None:
    if not c or c.get("total_min") is None: return None
    t = c["total_min"]
    if t <= 15: return 1.0
    if t >= 45: return 0.0
    return 1.0 - (t - 15) / 30.0


def _safety_score(c: dict | None) -> float | None:
    if not c: return None
    fel = c.get("felonies")
    if fel is None: return None
    if fel <= 20:  return 1.0
    if fel >= 200: return 0.0
    return 1.0 - (fel - 20) / 180.0


def _sa_score(food: list | None, grocery: list | None) -> float | None:
    if food is None and grocery is None: return None
    sa_grocery = sum(1 for g in (grocery or []) if g.get("south_asian"))
    food_close = sum(1 for f in (food or []) if (f.get("dist_mi") or 99) <= 1.0)
    if sa_grocery >= 1 and food_close >= 3: return 1.0
    if sa_grocery >= 1 or food_close >= 3:  return 0.7
    if food_close >= 1: return 0.4
    return 0.0


def _price_score(price: int | None) -> float | None:
    if price is None: return None
    if price <= PRICE_FLOOR: return 1.0
    if price >= PRICE_CEIL:  return 0.0
    return 1.0 - (price - PRICE_FLOOR) / (PRICE_CEIL - PRICE_FLOOR)


def compute_score(listing: dict) -> float:
    enr = listing.get("enrichment") or {}
    parts = [
        (W_COMMUTE, _commute_score(enr.get("commute"))),
        (W_SAFETY,  _safety_score(enr.get("crime"))),
        (W_SA,      _sa_score(enr.get("food"), enr.get("grocery"))),
        (W_PRICE,   _price_score(listing.get("price"))),
    ]
    active = [(w, s) for w, s in parts if s is not None]
    if not active: return 0.0
    total_w = sum(w for w, _ in active)
    return sum(w * s for w, s in active) / total_w
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `python -m pytest tests/test_score.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add score.py tests/test_score.py
git commit -m "score.py: fit-score (commute/safety/SA-access/price) with unit tests"
```

### Task 9: Implement payload.py contract (TDD)

**Files:**
- Create: `tests/test_payload.py`
- Modify: `report/payload.py`

`report/payload.py` exists from Phase 1; it currently produces whatever shape Phase 1 chose. Extend it to emit the full Section-3 contract: every listing has all top-level fields and an `enrichment` block (possibly empty for Craigslist hits without enrichment).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_payload.py
from report.payload import build_payload

def test_payload_top_level_keys():
    p = build_payload([])
    for k in ("generated_at", "campus", "listings", "filter_defaults", "tiles"):
        assert k in p

def test_listing_has_required_shape(sample_listing):
    p = build_payload([sample_listing])
    l = p["listings"][0]
    for k in ("id", "source", "url", "title", "price", "beds",
              "lat", "lng", "address", "neighborhood", "posted_at",
              "score", "enrichment"):
        assert k in l, f"missing key: {k}"

def test_score_attached_when_enriched(sample_listing):
    p = build_payload([sample_listing])
    assert isinstance(p["listings"][0]["score"], float)
    assert 0.0 <= p["listings"][0]["score"] <= 1.0

def test_listing_without_coords_is_filtered_out():
    bad = {"id": "x", "lat": None, "lng": None, "title": "no coords"}
    p = build_payload([bad])
    assert p["listings"] == []

def test_filter_defaults_match_spec():
    p = build_payload([])
    assert p["filter_defaults"]["max_price"] == 1500
    assert p["filter_defaults"]["max_commute"] == 30
    assert p["filter_defaults"]["hide_hidden"] is True
    assert p["filter_defaults"]["only_starred"] is False
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `python -m pytest tests/test_payload.py -v`
Expected: tests fail on missing keys / shape mismatch (exact failure depends on current `payload.py` state).

- [ ] **Step 3: Update report/payload.py**

Read current `report/payload.py`, then rewrite `build_payload()` to emit the spec contract. Replace its body with:

```python
# report/payload.py
"""Emit the window.KHOJ payload — the Section-3 data contract."""
from __future__ import annotations

from datetime import datetime, timezone

from score import compute_score

CAMPUS = {"lat": 40.6929, "lng": -73.9870, "label": "NYU Tandon"}
TILES = {
    "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": "© OpenStreetMap contributors",
}
FILTER_DEFAULTS = {
    "max_price": 1500,
    "max_commute": 30,
    "hide_hidden": True,
    "only_starred": False,
}


def _listing_dict(raw: dict) -> dict | None:
    if raw.get("lat") is None or raw.get("lng") is None:
        return None
    out = {
        "id":           raw.get("id") or raw.get("url"),
        "source":       raw.get("source", "craigslist"),
        "url":          raw.get("url"),
        "title":        raw.get("title", ""),
        "price":        raw.get("price"),
        "beds":         raw.get("beds") if "beds" in raw else raw.get("bedrooms"),
        "lat":          raw["lat"],
        "lng":          raw["lng"],
        "address":      raw.get("address", ""),
        "neighborhood": raw.get("neighborhood", ""),
        "posted_at":    raw.get("posted_at") or raw.get("posted_date"),
        "enrichment":   raw.get("enrichment") or {},
    }
    out["score"] = compute_score(out)
    return out


def build_payload(listings: list[dict]) -> dict:
    out_listings = [d for d in (_listing_dict(l) for l in listings) if d is not None]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campus":          CAMPUS,
        "tiles":           TILES,
        "filter_defaults": FILTER_DEFAULTS,
        "listings":        out_listings,
    }
```

If Phase 1's `payload.py` had additional callers (e.g., from `report/build.py`), keep the same function name (`build_payload`) and signature so they keep working.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `python -m pytest tests/test_payload.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add report/payload.py tests/test_payload.py
git commit -m "payload.py: emit the Section-3 contract; score attached per listing"
```

### Task 10: Extend enrich.py with commute/noise/crime/food/grocery

**Files:**
- Modify: `enrich.py`
- Modify: `scraper.py`

`enrich.py` already has `geocode()` wired and the skeleton for the rest. The body of `tools/enrich_dryrun.py` is the proven implementation — port the relevant functions into `enrich.py`. Side-effect goal: `enrich_address(addr, lat, lng) -> dict` returns the `enrichment` block.

- [ ] **Step 1: Port enrichment functions from tools/enrich_dryrun.py into enrich.py**

Open `tools/enrich_dryrun.py` and locate the implementations of:
- nearest-station + commute calculation
- 311 noise count (SODA API)
- NYPD crime breakdown (SODA API)
- Overpass query for Indian-food restaurants
- Overpass query for grocery / halal stores

Copy each into `enrich.py` as `commute(lat, lng)`, `noise(lat, lng)`, `crime(lat, lng)`, `food(lat, lng)`, `grocery(lat, lng)` — each returning the dict shape defined in the spec's Section 3 data contract.

Add a top-level orchestrator:

```python
# end of enrich.py
def enrich_address(lat: float, lng: float) -> dict:
    """Return the full enrichment block for a (lat, lng)."""
    return {
        "commute": commute(lat, lng),
        "noise":   noise(lat, lng),
        "crime":   crime(lat, lng),
        "food":    food(lat, lng),
        "grocery": grocery(lat, lng),
    }
```

Cache pattern: each SODA / Overpass call should use the existing `_load_cache` / `_save_cache` helpers, keyed by geohash + a weekly bucket (week-of-year). See the geocode cache for the pattern.

- [ ] **Step 2: Call enrich in scraper.py**

In `scraper.py`, locate the spot where listings are assembled (around line 549 in the existing file — search for `results: list[Listing] = []`). After geocoding each listing, call `enrich.enrich_address(l.lat, l.lng)` and attach the result. Extend `Listing` dataclass with one new field:

```python
@dataclass
class Listing:
    # ... existing fields ...
    score: int = 0
    enrichment: dict | None = None   # NEW
```

After all listings are scored, transform Listings → dicts and pass to `report.build_html` (or whatever Phase 1 named the entrypoint) which itself calls `build_payload`.

- [ ] **Step 3: Smoke-test against one submission**

Run: `python scraper.py --pages-mode`
Expected: completes without errors; `docs/index.html` includes listings with `enrichment.commute`, `enrichment.noise`, etc. Verify by opening devtools console and inspecting `window.KHOJ.listings[0].enrichment`.

If a network call to Overpass/SODA fails, the function should return `None` for that subfield rather than raising — this keeps the scraper resilient. Wrap each enrichment call in a try/except that logs to stderr and returns `None` on failure.

- [ ] **Step 4: Commit**

```bash
git add enrich.py scraper.py
git commit -m "Enrichment: wire commute/noise/crime/food/grocery into scraper"
```

### Task 11: Pin color/size from score + panel renders enrichment

**Files:**
- Modify: `docs/khoj/map.js`
- Modify: `docs/khoj/panel.js`
- Modify: `docs/khoj/khoj.css`

- [ ] **Step 1: Update pin styling rules in khoj.css**

Append to `docs/khoj/khoj.css`:

```css
.khoj-pin-dot {
  display: block; border-radius: 50%; border: 2px solid var(--ink);
  background: var(--ink-mute); box-shadow: 0 1px 2px rgba(0,0,0,0.3);
  transition: transform 120ms;
}
/* Size by score */
.khoj-pin-dot[data-score-tier="low"]  { width: 10px; height: 10px; }
.khoj-pin-dot[data-score-tier="mid"]  { width: 14px; height: 14px; }
.khoj-pin-dot[data-score-tier="high"] { width: 18px; height: 18px;
                                        background: var(--crimson); border-color: var(--crimson); }
.khoj-pin-dot[data-starred="true"] { box-shadow: 0 0 0 3px var(--gold); }
.khoj-pin-dot[data-hidden="true"]  { opacity: 0.3; }
```

- [ ] **Step 2: Update map.js to emit tier attribute**

In `docs/khoj/map.js`, update the `addListing()` icon HTML:

```js
const score = listing.score ?? 0;
const tier = score < 0.4 ? "low" : score < 0.7 ? "mid" : "high";
const icon = L.divIcon({
  className: "khoj-pin",
  html: `<span class="khoj-pin-dot" data-score-tier="${tier}"></span>`,
});
```

Also subscribe to `starred` and `hidden` state to update the `data-starred` / `data-hidden` attributes on existing markers without redrawing:

```js
function syncFlags() {
  const starred = new Set(state.get("starred") || []);
  const hidden  = new Set(state.get("hidden") || []);
  for (const [id, marker] of markerByUrl.entries()) {
    const el = marker.getElement()?.querySelector(".khoj-pin-dot");
    if (!el) continue;
    el.dataset.starred = starred.has(id);
    el.dataset.hidden  = hidden.has(id);
  }
}
state.subscribe("starred", syncFlags);
state.subscribe("hidden",  syncFlags);
syncFlags();
```

- [ ] **Step 3: Render enrichment in panel.js**

In `docs/khoj/panel.js`, after the existing `<section class="khoj-panel-enrichment">` placeholder, populate it. Inside `render(id)`, after setting `root.innerHTML`, add:

```js
const enr = l.enrichment || {};
const mount = root.querySelector("#khoj-panel-enrich");
const parts = [];
if (enr.commute) {
  parts.push(`<div class="enr-block"><h4>Commute</h4>
    <p>${enr.commute.total_min}m — ${enr.commute.walk_min}m walk to
    ${enr.commute.station?.name ?? "?"} (${(enr.commute.station?.lines || []).join("/")}) → ${enr.commute.rail_min}m rail</p></div>`);
}
if (enr.crime) {
  parts.push(`<div class="enr-block"><h4>Safety (12mo)</h4>
    <p>${enr.crime.total_12mo} total · ${enr.crime.felonies} felonies · ${enr.crime.misd} misd · ${enr.crime.viol} viol</p></div>`);
}
if (enr.noise) {
  parts.push(`<div class="enr-block"><h4>Noise (12mo)</h4>
    <p>${enr.noise.count_12mo} 311 complaints · top: ${enr.noise.top_category}</p></div>`);
}
if (enr.food?.length) {
  const top = enr.food.slice(0, 3).map(f => `${f.name} (${f.dist_mi.toFixed(2)}mi)`).join(", ");
  parts.push(`<div class="enr-block"><h4>Indian food</h4><p>${top}</p></div>`);
}
if (enr.grocery?.length) {
  const sa = enr.grocery.filter(g => g.south_asian).slice(0, 3);
  const top = (sa.length ? sa : enr.grocery.slice(0, 3))
    .map(g => `${g.name} (${g.dist_mi.toFixed(2)}mi)${g.south_asian ? " ★" : ""}`).join(", ");
  parts.push(`<div class="enr-block"><h4>Grocery</h4><p>${top}</p></div>`);
}
mount.innerHTML = parts.join("");
```

Add to `khoj.css`:
```css
.enr-block { margin: 14px 0; }
.enr-block h4 { font-family: var(--mono); font-size: var(--type-small);
                text-transform: uppercase; color: var(--ink-soft); margin: 0 0 4px; }
.enr-block p { margin: 0; font-size: var(--type-small); line-height: var(--leading-snug); }
```

- [ ] **Step 4: Verify in browser**

Run: `python scraper.py --pages-mode && open docs/index.html`
Expected: high-score listings show as larger crimson pins; clicking shows the full enrichment card; starring a listing adds a gold ring to its pin without page reload.

- [ ] **Step 5: Commit**

```bash
git add docs/khoj/map.js docs/khoj/panel.js docs/khoj/khoj.css
git commit -m "Pin styling by score + panel renders enrichment block"
```

---

## Phase 4 — Interactive overlays

**Outcome:** layers control toggles six overlays; selecting a pin draws its commute path and reveals its POIs.

### Task 12: Implement overlays.js core (registry + lazy-load + toggle)

**Files:**
- Modify: `docs/khoj/overlays.js`
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Implement overlays.js**

```js
// docs/khoj/overlays.js
const REGISTRY = {
  noise:   { path: "./data/nta-noise.geojson",       style: () => ({ color: "#7A5C1E", fillOpacity: 0.15, weight: 0 }) },
  crime:   { path: "./data/crime.geojson",           style: (f) => ({ color: "#8C2026",
                                                                       fillOpacity: Math.min(0.5, (f.properties?.felonies || 0) / 400),
                                                                       weight: 1 }) },
  parks:   { path: "./data/parks.geojson",           style: () => ({ color: "#3a5a40", fillOpacity: 0.3, weight: 0 }) },
  subway_lines:    { path: "./data/subway-lines.geojson",    style: () => ({ color: "#1A1612", weight: 2 }) },
  subway_stations: { path: "./data/subway-stations.geojson", style: () => ({ color: "#1A1612" }) },
  commute_zone:    { path: "./data/commute-zone.geojson",    style: () => ({ color: "#5A4E42", fillOpacity: 0.05, weight: 1, dashArray: "4 4" }) },
};

export function createOverlays(state, map) {
  const layers = {};      // name -> L.GeoJSON
  const loaded = {};      // name -> Promise<L.GeoJSON>

  async function load(name) {
    if (loaded[name]) return loaded[name];
    loaded[name] = fetch(REGISTRY[name].path)
      .then(r => r.json())
      .then(geo => {
        const layer = L.geoJSON(geo, { style: REGISTRY[name].style });
        layers[name] = layer;
        return layer;
      });
    return loaded[name];
  }

  async function show(name) {
    const layer = await load(name);
    if (!map.map.hasLayer(layer)) layer.addTo(map.map);
  }
  function hide(name) {
    if (layers[name] && map.map.hasLayer(layers[name])) map.map.removeLayer(layers[name]);
  }
  async function toggle(name, on) { on ? await show(name) : hide(name); }

  // Restore persisted layer state on init
  const initial = state.get("layers") || { subway_lines: true, subway_stations: true, commute_zone: true };
  state.set("layers", initial);
  for (const [name, on] of Object.entries(initial)) if (on) show(name);

  return { toggle, show, hide };
}
```

- [ ] **Step 2: Wire overlays into main.js**

Update `docs/khoj/main.js`:

```js
import { createState } from "./state.js";
import { createMap } from "./map.js";
import { createList } from "./list.js";
import { createPanel } from "./panel.js";
import { createOverlays } from "./overlays.js";

const state = createState({
  filters: window.KHOJ.filter_defaults,
  selectedId: null,
});

const map = createMap(state, "khoj-map");
const overlays = createOverlays(state, map);
createList(state, "khoj-list", map);
createPanel(state, "khoj-panel");

state.subscribe("selectedId", (id) => {
  document.getElementById("khoj-map").classList.toggle("dimmed", !!id);
});

window.KHOJ_overlays = overlays;   // exposed for filter-bar Task 16
```

- [ ] **Step 3: Verify**

Run: `python -m report --pages-mode && open docs/index.html`. Expected: subway lines, stations, and commute zone render by default. Console: `window.KHOJ_overlays.show("noise")` reveals the noise polygons; `hide("noise")` removes them.

- [ ] **Step 4: Commit**

```bash
git add docs/khoj/overlays.js docs/khoj/main.js
git commit -m "Overlays: lazy-load registry + show/hide/toggle"
```

### Task 13: Build crime.geojson via tools/build_overlays.py

**Files:**
- Create: `tools/build_overlays.py`
- Create: `docs/data/crime.geojson` (output)

NYPD CompStat publishes precinct-level complaint counts via NYC Open Data SODA endpoint. We aggregate the last 12 months per precinct and join to the precinct polygon GeoJSON (also NYC Open Data).

- [ ] **Step 1: Write the builder**

```python
# tools/build_overlays.py
"""Pre-compute static GeoJSON overlays the scraper doesn't produce itself.

Currently: docs/data/crime.geojson — NYPD CompStat 12-mo aggregates by
precinct, joined to precinct polygons.

Other overlays (nta-noise, commute-zone, parks, subway-*) are produced by
other tools/ scripts or live as static reference data.

Cron: weekly is plenty — CompStat updates monthly.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
OUT = ROOT / "docs" / "data" / "crime.geojson"

# NYPD Complaint Data (Historic) — last N records by date, 12mo window
NYPD_URL = "https://data.cityofnewyork.us/resource/5uac-w243.json"
PRECINCTS_URL = "https://data.cityofnewyork.us/resource/wt4d-p43d.geojson"  # Police Precincts

CATEGORIES = {"FELONY": "felonies", "MISDEMEANOR": "misd", "VIOLATION": "viol"}


def fetch_complaints():
    cutoff = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    counts = Counter()
    offset = 0
    while True:
        params = {
            "$select": "addr_pct_cd,law_cat_cd",
            "$where":  f"cmplnt_fr_dt > '{cutoff}'",
            "$limit": 50000,
            "$offset": offset,
        }
        r = requests.get(NYPD_URL, params=params, timeout=60)
        r.raise_for_status()
        rows = r.json()
        if not rows: break
        for row in rows:
            pct = row.get("addr_pct_cd")
            cat = (row.get("law_cat_cd") or "").upper()
            if pct and cat in CATEGORIES:
                counts[(pct, CATEGORIES[cat])] += 1
        if len(rows) < 50000: break
        offset += 50000
    return counts


def fetch_precincts():
    r = requests.get(PRECINCTS_URL, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    counts = fetch_complaints()
    geo = fetch_precincts()
    for feat in geo["features"]:
        pct = str(feat["properties"].get("precinct"))
        fel = counts[(pct, "felonies")]
        mis = counts[(pct, "misd")]
        vio = counts[(pct, "viol")]
        feat["properties"] = {
            "precinct": pct, "felonies": fel, "misd": mis, "viol": vio,
            "total_12mo": fel + mis + vio,
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(geo))
    print(f"wrote {OUT} — {len(geo['features'])} precincts, "
          f"{sum(counts.values()):,} complaints aggregated")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the builder**

Run: `python tools/build_overlays.py`
Expected: prints "wrote docs/data/crime.geojson — 77 precincts, NNN complaints aggregated".

If the call rate-limits or fails, the script is safe to re-run — it overwrites the file from scratch.

- [ ] **Step 3: Commit (data file + script)**

```bash
git add tools/build_overlays.py docs/data/crime.geojson
git commit -m "tools/build_overlays.py: produce docs/data/crime.geojson from NYPD CompStat"
```

### Task 14: Commute-path + scoped POIs on selection

**Files:**
- Modify: `docs/khoj/overlays.js`
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Add path + POI rendering to overlays.js**

Append to `docs/khoj/overlays.js`:

```js
export function createSelectionOverlays(state, map) {
  let pathLayer = null;
  let pathLabel = null;
  let poiLayer = null;

  function clear() {
    if (pathLayer) { map.map.removeLayer(pathLayer); pathLayer = null; }
    if (pathLabel) { map.map.removeLayer(pathLabel); pathLabel = null; }
    if (poiLayer)  { map.map.removeLayer(poiLayer);  poiLayer  = null; }
  }

  function show(id) {
    clear();
    if (!id) return;
    const l = window.KHOJ.listings.find(x => x.id === id);
    if (!l) return;
    const enr = l.enrichment || {};

    // Commute path: listing -> station -> Tandon
    const st = enr.commute?.station;
    if (st) {
      const pts = [[l.lat, l.lng], [st.lat, st.lng],
                   [window.KHOJ.campus.lat, window.KHOJ.campus.lng]];
      pathLayer = L.polyline(pts, { color: "#8C2026", weight: 2, dashArray: "6 4", opacity: 0.7 }).addTo(map.map);
      pathLabel = L.tooltip({ permanent: true, direction: "center", className: "khoj-path-label" })
        .setLatLng([(l.lat + st.lat) / 2, (l.lng + st.lng) / 2])
        .setContent(`${enr.commute.walk_min}m walk`)
        .addTo(map.map);
    }

    // POI markers
    const pois = [
      ...(enr.food    || []).map(p => ({ ...p, kind: "food"    })),
      ...(enr.grocery || []).map(p => ({ ...p, kind: "grocery" })),
    ];
    poiLayer = L.layerGroup(
      pois.filter(p => p.lat != null).map(p =>
        L.circleMarker([p.lat, p.lng], {
          radius: 5, color: p.kind === "food" ? "#7A5C1E" : "#3a5a40",
          fillColor: p.kind === "food" ? "#7A5C1E" : "#3a5a40", fillOpacity: 0.8,
        }).bindTooltip(`${p.name} (${p.dist_mi?.toFixed(2)}mi)`)),
    ).addTo(map.map);
  }

  state.subscribe("selectedId", show);
  return { clear };
}
```

- [ ] **Step 2: Wire createSelectionOverlays into main.js**

In `docs/khoj/main.js`, after the existing `createOverlays(...)` call:

```js
import { createOverlays, createSelectionOverlays } from "./overlays.js";
// ...
createSelectionOverlays(state, map);
```

(Update the existing import line to add `createSelectionOverlays`.)

- [ ] **Step 3: Verify**

Run: `python scraper.py --pages-mode && open docs/index.html`. Expected: clicking a pin draws a dashed crimson line listing → station → Tandon, plus small dots at each POI; clicking another pin redraws; closing the panel clears them.

- [ ] **Step 4: Commit**

```bash
git add docs/khoj/overlays.js docs/khoj/main.js
git commit -m "Selection overlays: commute path + scoped POIs on pin click"
```

### Task 15: Layers control UI (top-right of map)

**Files:**
- Modify: `docs/khoj/map.js`
- Modify: `docs/khoj/khoj.css`

Native Leaflet `L.control.layers` doesn't quite fit — we want toggles even for layers not yet fetched. Build a small custom control.

- [ ] **Step 1: Add a custom layers control to map.js**

In `docs/khoj/map.js`, after the marker setup, append before `return`:

```js
const LAYER_LABELS = {
  noise:           "Noise",
  crime:           "Crime",
  parks:           "Parks",
  subway_lines:    "Subway lines",
  subway_stations: "Stations",
  commute_zone:    "Commute zone",
};

function mountLayersControl(state, overlaysApi) {
  const ctrl = L.control({ position: "topright" });
  ctrl.onAdd = () => {
    const div = L.DomUtil.create("div", "khoj-layers-control");
    const layers = state.get("layers") || {};
    div.innerHTML = "<h4>Layers</h4>" + Object.entries(LAYER_LABELS).map(([key, label]) =>
      `<label><input type="checkbox" data-layer="${key}" ${layers[key] ? "checked" : ""}> ${label}</label>`
    ).join("");
    L.DomEvent.disableClickPropagation(div);
    div.addEventListener("change", (e) => {
      if (e.target.matches("[data-layer]")) {
        const key = e.target.dataset.layer;
        const on = e.target.checked;
        const cur = { ...(state.get("layers") || {}) };
        cur[key] = on;
        state.set("layers", cur);
        overlaysApi.toggle(key, on);
      }
    });
    return div;
  };
  return ctrl;
}

// Expose so main.js can mount it after overlays are created
return { map, markerByUrl, mountLayersControl };
```

In `docs/khoj/main.js`, after creating overlays:

```js
map.mountLayersControl(state, overlays).addTo(map.map);
```

- [ ] **Step 2: Style the control**

Append to `docs/khoj/khoj.css`:

```css
.khoj-layers-control {
  background: var(--paper); border: 1px solid var(--rule); padding: 10px 12px;
  font-family: var(--mono); font-size: var(--type-small);
}
.khoj-layers-control h4 { margin: 0 0 6px; font-family: var(--serif-display);
                          font-size: var(--type-small); }
.khoj-layers-control label { display: block; padding: 2px 0; cursor: pointer; }
.khoj-layers-control input { margin-right: 6px; }
```

- [ ] **Step 3: Verify**

Run: `python -m report --pages-mode && open docs/index.html`. Expected: top-right shows a "Layers" control with six checkboxes; toggling each reveals/hides its overlay; state survives reload.

- [ ] **Step 4: Commit**

```bash
git add docs/khoj/map.js docs/khoj/khoj.css docs/khoj/main.js
git commit -m "Layers control: six toggleable overlays with persisted state"
```

---

## Phase 5 — Filter chips + polish

**Outcome:** spec's full interaction model is live and tested.

### Task 16: Implement filter chips (filters.js)

**Files:**
- Modify: `docs/khoj/filters.js`
- Modify: `docs/khoj/list.js`
- Modify: `docs/khoj/map.js`
- Modify: `docs/khoj/khoj.css`
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Implement filters.js**

```js
// docs/khoj/filters.js
export function createFilters(state, mountId = "khoj-topbar") {
  const root = document.getElementById(mountId);
  const f = state.get("filters") || {};

  root.innerHTML = `
    <span class="khoj-brand">Khoj</span>
    <label class="khoj-chip">Price ≤ $<input data-f="max_price" type="number" value="${f.max_price ?? 1500}" min="500" max="5000" step="50"></label>
    <label class="khoj-chip">Commute ≤ <input data-f="max_commute" type="number" value="${f.max_commute ?? 30}" min="5" max="90" step="5">m</label>
    <label class="khoj-chip"><input data-f="south_asian" type="checkbox" ${f.south_asian ? "checked" : ""}> SA food ≤1mi</label>
    <label class="khoj-chip"><input data-f="only_starred" type="checkbox" ${f.only_starred ? "checked" : ""}> ☆ only</label>
    <label class="khoj-chip"><input data-f="hide_hidden"  type="checkbox" ${f.hide_hidden  ? "checked" : ""}> Hide rejected</label>
    <select data-f="sort" class="khoj-sort">
      <option value="score">Sort: score</option>
      <option value="price">Sort: price</option>
      <option value="commute">Sort: commute</option>
      <option value="posted">Sort: posted</option>
    </select>
    <span class="khoj-count" id="khoj-count"></span>
  `;

  const sortSel = root.querySelector('[data-f="sort"]');
  sortSel.value = state.get("sort") || "score";
  sortSel.addEventListener("change", () => state.set("sort", sortSel.value));

  root.addEventListener("change", (e) => {
    const t = e.target;
    if (!t.dataset.f || t.dataset.f === "sort") return;
    const cur = { ...(state.get("filters") || {}) };
    cur[t.dataset.f] = t.type === "checkbox" ? t.checked : Number(t.value);
    state.set("filters", cur);
  });
}

export function applyFilters(listings, state) {
  const f = state.get("filters") || {};
  const starred = new Set(state.get("starred") || []);
  const hidden  = new Set(state.get("hidden")  || []);
  return listings.filter(l => {
    if (f.hide_hidden  && hidden.has(l.id)) return false;
    if (f.only_starred && !starred.has(l.id)) return false;
    if (f.max_price && l.price != null && l.price > f.max_price) return false;
    if (f.max_commute) {
      const c = l.enrichment?.commute?.total_min;
      if (c != null && c > f.max_commute) return false;
    }
    if (f.south_asian) {
      const sa = (l.enrichment?.grocery || []).some(g => g.south_asian);
      const food = (l.enrichment?.food || []).some(g => (g.dist_mi ?? 99) <= 1.0);
      if (!sa && !food) return false;
    }
    return true;
  });
}
```

- [ ] **Step 2: Update list.js to use applyFilters**

In `docs/khoj/list.js`, change `render()`:

```js
import { applyFilters } from "./filters.js";
// ...
function render() {
  const sortKey = state.get("sort") || "score";
  const visible = applyFilters(window.KHOJ.listings, state);
  const sorted = visible.sort(SORTS[sortKey] || SORTS.score);
  root.innerHTML = sorted.map(rowHtml).join("");
  document.getElementById("khoj-count").textContent =
    `${sorted.length} of ${window.KHOJ.listings.length}`;
}

state.subscribe("filters", render);
state.subscribe("starred", render);
state.subscribe("hidden",  render);
```

- [ ] **Step 3: Update map.js to fade filtered-out pins**

In `docs/khoj/map.js`, add a `syncFilters()` function alongside `syncFlags()`:

```js
import { applyFilters } from "./filters.js";
// ...
function syncFilters() {
  const visibleIds = new Set(applyFilters(window.KHOJ.listings, state).map(l => l.id));
  for (const [id, marker] of markerByUrl.entries()) {
    const el = marker.getElement();
    if (!el) continue;
    el.classList.toggle("khoj-pin--filtered-out", !visibleIds.has(id));
  }
}
state.subscribe("filters", syncFilters);
state.subscribe("starred", syncFilters);
state.subscribe("hidden",  syncFilters);
syncFilters();
```

Append to `docs/khoj/khoj.css`:
```css
.khoj-pin--filtered-out .khoj-pin-dot { opacity: 0.15; }
.khoj-chip { display: inline-flex; align-items: center; gap: 4px;
             font-family: var(--mono); font-size: var(--type-small);
             padding: 4px 10px; border: 1px solid var(--rule); border-radius: 4px; }
.khoj-chip input[type="number"] { width: 48px; font-family: inherit; font-size: inherit;
                                    border: none; background: transparent; }
.khoj-sort { font-family: var(--mono); font-size: var(--type-small);
             padding: 4px 8px; border: 1px solid var(--rule); }
.khoj-brand { font-family: var(--serif-display); font-weight: 600; font-size: var(--type-h4); margin-right: 8px; }
.khoj-count { margin-left: auto; font-family: var(--mono); font-size: var(--type-small); color: var(--ink-mute); }
```

- [ ] **Step 4: Wire filters into main.js**

Add to `docs/khoj/main.js`:

```js
import { createFilters } from "./filters.js";
// ...
createFilters(state, "khoj-topbar");
```

- [ ] **Step 5: Verify**

Run: `python -m report --pages-mode && open docs/index.html`. Expected: chips at top filter the list and fade pins; sort dropdown re-orders the list; count badge updates; reload preserves filter values.

- [ ] **Step 6: Commit**

```bash
git add docs/khoj/filters.js docs/khoj/list.js docs/khoj/map.js docs/khoj/khoj.css docs/khoj/main.js
git commit -m "Filter chips: price/commute/SA-food/starred/hide + sort"
```

### Task 17: Keyboard shortcuts + empty state + accessibility pass

**Files:**
- Create: `docs/khoj/keys.js`
- Modify: `docs/khoj/list.js`
- Modify: `docs/khoj/panel.js`
- Modify: `docs/khoj/main.js`

- [ ] **Step 1: Create keys.js**

```js
// docs/khoj/keys.js
import { applyFilters } from "./filters.js";

export function createKeys(state) {
  function visibleIds() {
    const sorted = applyFilters(window.KHOJ.listings, state)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    return sorted.map(l => l.id);
  }

  function move(delta) {
    const ids = visibleIds();
    if (!ids.length) return;
    const cur = state.get("selectedId");
    const i = ids.indexOf(cur);
    const next = i < 0 ? ids[0] : ids[(i + delta + ids.length) % ids.length];
    state.set("selectedId", next);
  }

  function toggleSet(key, id) {
    const cur = state.get(key) || [];
    state.set(key, cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    if (e.key === "j") { move(1); e.preventDefault(); }
    else if (e.key === "k") { move(-1); e.preventDefault(); }
    else if (e.key === "s") {
      const id = state.get("selectedId");
      if (id) toggleSet("starred", id);
    }
    else if (e.key === "h") {
      const id = state.get("selectedId");
      if (id) toggleSet("hidden", id);
    }
    else if (e.key === "/") {
      const inp = document.querySelector('#khoj-topbar input[type="number"]');
      if (inp) { inp.focus(); inp.select(); e.preventDefault(); }
    }
  });
}
```

- [ ] **Step 2: Empty state in list.js**

In `docs/khoj/list.js`, change the `render()` body so when `sorted.length === 0`, it sets innerHTML to:

```js
if (sorted.length === 0) {
  root.innerHTML = `<div class="khoj-empty">
    <p>0 of ${window.KHOJ.listings.length} match</p>
    <button id="khoj-reset">Reset filters</button>
  </div>`;
  root.querySelector("#khoj-reset").addEventListener("click", () => {
    state.set("filters", window.KHOJ.filter_defaults);
  });
  document.getElementById("khoj-count").textContent = `0 of ${window.KHOJ.listings.length}`;
  return;
}
```

Append to `docs/khoj/khoj.css`:
```css
.khoj-empty { padding: 32px 16px; text-align: center; color: var(--ink-mute); }
.khoj-empty button { margin-top: 12px; padding: 6px 12px; cursor: pointer; }
```

- [ ] **Step 3: Panel focus trap + dialog role**

In `docs/khoj/panel.js`, in `render(id)`:
- Add `root.setAttribute("role", "dialog")` and `root.setAttribute("aria-modal", "false")` in the open branch (after `aria-hidden="false"`).
- After setting innerHTML, focus the close button: `root.querySelector(".khoj-panel-close").focus();`

- [ ] **Step 4: Wire keys.js into main.js**

```js
import { createKeys } from "./keys.js";
// ...
createKeys(state);
```

- [ ] **Step 5: Verify**

Run: `python -m report --pages-mode && open docs/index.html`. Expected: pressing `j`/`k` cycles selection; `s` toggles star on current selection; `/` focuses the price input; filters that produce zero rows show the empty state with a reset button.

- [ ] **Step 6: Commit**

```bash
git add docs/khoj/keys.js docs/khoj/list.js docs/khoj/panel.js docs/khoj/khoj.css docs/khoj/main.js
git commit -m "Keyboard shortcuts (j/k/s/h//) + empty state + dialog roles"
```

### Task 18: Mobile layout (bottom-drawer list + full-screen panel)

**Files:**
- Modify: `docs/khoj/khoj.css`

Pure CSS — no JS changes. The list rail becomes a bottom drawer and the panel becomes a full-screen overlay below 768 px.

- [ ] **Step 1: Append mobile breakpoint to khoj.css**

```css
@media (max-width: 768px) {
  #khoj-app { grid-template-columns: 1fr; grid-template-rows: 1fr auto; }
  #khoj-list {
    order: 2; max-height: 40vh; border-right: none;
    border-top: 1px solid var(--rule);
  }
  #khoj-list::before {
    content: ""; display: block; width: 40px; height: 4px;
    background: var(--rule); border-radius: 2px;
    margin: 8px auto;
  }
  #khoj-panel {
    top: 0; width: 100vw; height: 100vh; z-index: 1000;
    padding: 56px 20px 20px;
  }
  .khoj-panel-close { top: 16px; right: 16px; font-size: 1.5rem; }
  #khoj-topbar { flex-wrap: wrap; height: auto; padding: 8px; gap: 6px; }
  .khoj-layers-control { font-size: var(--type-micro); padding: 6px 8px; }
}
```

- [ ] **Step 2: Verify**

Open `docs/index.html` in browser, open devtools, toggle the device toolbar to a phone preset. Expected: list collapses below map; panel is full-screen when opened; topbar wraps gracefully.

- [ ] **Step 3: Commit**

```bash
git add docs/khoj/khoj.css
git commit -m "Mobile: bottom-drawer list + full-screen detail panel"
```

### Task 19: Update GitHub Actions cron to run build_overlays.py weekly

**Files:**
- Modify: `.github/workflows/scrape.yml`

- [ ] **Step 1: Read the current workflow**

Run: `cat .github/workflows/scrape.yml`

- [ ] **Step 2: Add a separate weekly workflow**

Create or extend the file to include a second job. The cleanest path is a new file:

Create `.github/workflows/overlays.yml`:

```yaml
name: Refresh map overlays

on:
  schedule:
    - cron: "0 6 * * 1"   # 06:00 UTC Monday
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python tools/build_overlays.py
      - name: Commit if changed
        run: |
          git config user.name "khoj-bot"
          git config user.email "khoj-bot@users.noreply.github.com"
          git add docs/data/crime.geojson
          git diff --cached --quiet || git commit -m "Refresh crime overlay"
          git push
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/overlays.yml
git commit -m "Workflow: weekly refresh of docs/data/crime.geojson"
```

### Task 20: Final smoke test + spec verification

- [ ] **Step 1: Full pipeline run**

Run:
```bash
python scraper.py --pages-mode
python -m pytest tests/ -v
```

Expected: scraper completes, all tests pass, `docs/index.html` updated.

- [ ] **Step 2: Spec walkthrough**

Open `docs/index.html` and check each item from the spec's Section 4:

- [ ] Layout matches the desktop diagram (top bar, left list, map, slide-in panel)
- [ ] Filter chip clicked updates list + fades pins + persists
- [ ] List row hover highlights matching pin
- [ ] Pin or row click opens panel + draws commute path + reveals POIs
- [ ] Layer toggle reveals overlay; state survives reload
- [ ] Star/hide/note persist; pin styles update without reload
- [ ] Pin color/size matches score tier rules
- [ ] Keyboard: `j`/`k`/`s`/`h`/`Esc`/`/` all work
- [ ] Empty state shows on over-filter
- [ ] Mobile breakpoint produces drawer + full-screen panel
- [ ] All 6 overlays toggle correctly

- [ ] **Step 3: Commit if anything else changed**

```bash
git status
# If clean, you're done. Otherwise: review diff and commit.
```

- [ ] **Step 4: Open a PR**

```bash
git push -u origin <current-branch>
gh pr create --title "Leaflet explorer: unified map UI" --body "$(cat <<'EOF'
## Summary
- Replaces 3-tab Inbox/Shortlist/Map with a Zillow-style list+map explorer
- Pin color/size driven by 0..1 fit-score (commute + safety + SA access + price)
- Six toggleable overlays (noise, crime, parks, subway lines/stations, commute zone)
- Slide-in detail panel with full enrichment block, star/hide/note persisted to localStorage

## Test plan
- [ ] `python -m pytest tests/` passes
- [ ] `python scraper.py --pages-mode` completes
- [ ] All Section-4 interactions verified per Task 20 checklist
- [ ] Mobile drawer + full-screen panel layout works in devtools device mode

Spec: docs/superpowers/specs/2026-05-25-leaflet-explorer-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review of this plan

After the final task, the implementer should have:

- ✅ Six browser-tier modules (`state`, `map`, `list`, `panel`, `filters`, `overlays`, plus `keys`)
- ✅ Three new data-tier files (`score.py`, `tools/build_overlays.py`, plus extended `enrich.py` and `payload.py`)
- ✅ Test coverage for the pure-function pieces (`score.py`, `payload.py`)
- ✅ Every Section-4 interaction (filter / hover / click / toggle / star-hide-note / keyboard / empty state / mobile)
- ✅ All six overlays from Section 3's data-contract table
- ✅ New weekly cron for `crime.geojson`
- ✅ A PR with the full diff
