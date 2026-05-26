"""HTML shell. No CSS or JS source — just the skeleton + <link>/<script> wiring."""
from __future__ import annotations

import html as _html
import json
from datetime import datetime


FONTS_LINK = (
    'https://fonts.googleapis.com/css2?'
    'family=Fraunces:opsz,wght@9..144,400..700&'
    'family=Newsreader:opsz,wght@6..72,400;6..72,500&'
    'family=Newsreader:opsz,ital,wght@6..72,1,400&'
    'family=JetBrains+Mono:wght@400;500;600&display=swap'
)


def render(payload: dict) -> str:
    e = _html.escape
    listings = payload["listings"]
    medians = payload["medians"]
    curated = payload["curated"]
    other_sources = payload["other_sources"]

    date_str = datetime.now().date().isoformat()
    issue_num = datetime.now().toordinal() % 1000
    closest = min((l["distance"] for l in listings if l.get("distance") is not None), default=None)
    cheapest = min((l["price"] for l in listings if l.get("price")), default=None)

    curated_block = ""
    if curated:
        items = "".join(
            f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(note or url)}</a></li>'
            for url, note in curated
        )
        curated_block = f'<h3>Hand-picked listings</h3><ul>{items}</ul>'

    other_items = "".join(
        f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(name)}</a> — {e(note)}</li>'
        for name, url, note in other_sources
    )

    # Escape `</` so the JSON can't terminate the surrounding <script> tag if a
    # listing description ever contains "</script>".
    payload_json = json.dumps(listings, separators=(',', ':')).replace('</', '<\\/')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Brooklyn Apartment Inquirer · {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS_LINK}" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<link rel="stylesheet" href="khoj/khoj.css">
</head>
<body>
<div class="paper">
  <header class="masthead">
    <div class="masthead-strap">
      <span>BROOKLYN RENTALS · NYU TANDON BEAT</span>
      <span>VOL. I · NO. {issue_num}</span>
      <span>{date_str}</span>
    </div>
    <h1 class="masthead-title">The Brooklyn <em>Apartment</em> Inquirer</h1>
    <p class="masthead-sub">A daily digest of rentals near 370 Jay Street, filtered for student budgets ($800–$1,500) and stripped of telemarketing noise.</p>
  </header>

  <section class="stats">
    <div class="stat">
      <span class="stat-label">Listings</span>
      <span class="stat-value">{len(listings)}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Cheapest</span>
      <span class="stat-value">{f"${cheapest:,}" if cheapest is not None else "—"}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Closest</span>
      <span class="stat-value">{f"{closest:.2f}" if closest is not None else "—"} <span style="font-size:0.7em;color:var(--ink-mute);">mi</span></span>
    </div>
    <div class="stat">
      <span class="stat-label">Shortlist</span>
      <span class="stat-value" id="shortlist-stat">0</span>
    </div>
  </section>

  <nav class="tabs" role="tablist">
    <button class="tab active" data-tab="inbox" role="tab">Inbox<span class="tab-count" id="inbox-count">{len(listings)}</span></button>
    <button class="tab" data-tab="shortlist" role="tab">Shortlist<span class="tab-count" id="short-count">0</span></button>
  </nav>

  <section class="controls" id="controls">
    <div class="chip-group" data-filter="bed" data-label="Beds">
      <button class="chip active" data-val="all">All</button>
      <button class="chip" data-val="0">Studio</button>
      <button class="chip" data-val="1">1 BR</button>
      <button class="chip" data-val="2">2 BR</button>
    </div>
    <div class="chip-group" data-filter="price" data-label="Price">
      <button class="chip active" data-val="all">Any</button>
      <button class="chip" data-val="under1200">&lt; $1,200</button>
      <button class="chip" data-val="1200to1500">$1,200–1,500</button>
    </div>
    <div class="sort-wrap">
      <label for="sort">Sort</label>
      <select id="sort">
        <option value="score">Best fit</option>
        <option value="price">Cheapest first</option>
        <option value="distance">Closest first</option>
        <option value="posted">Newest first</option>
      </select>
    </div>
  </section>

  <div class="list-with-map">
    <main class="list-column">
      <section class="view active" id="view-inbox">
        <ol class="listings" id="listings"></ol>
      </section>

      <section class="view" id="view-shortlist">
        <ol class="listings" id="shortlist-listings"></ol>
        <p class="empty" id="shortlist-empty" style="display:none">No starred listings yet. Star ★ entries in the Inbox to build a shortlist.</p>
      </section>

      <!-- view-map removed: map is now persistent on the right (desktop) or inline below the list (mobile) -->
      <aside class="map-inline" id="map-inline">
        <div class="map-panel-caption">
          <span class="caption-text">listings near 370 jay st</span>
          <select class="tile-select" data-tile-select aria-label="Map style"></select>
        </div>
        <div id="map-mobile"></div>
      </aside>
    </main>
    <aside class="map-panel" id="map-panel">
      <div class="map-panel-caption">
        <span class="caption-text">listings near 370 Jay St — hover an entry to highlight its pin</span>
        <select class="tile-select" data-tile-select aria-label="Map style"></select>
      </div>
      <div id="map-side"></div>
    </aside>
  </div>

  <footer class="colophon">
    {curated_block}
    <h3>Other places worth checking manually</h3>
    <ul>{other_items}</ul>
    <p class="small">Khoj · refreshed daily by GitHub Actions at 13:00 UTC · <a href="https://github.com/animeshUX/khoj" target="_blank" rel="noopener">source</a> · state persists per device in localStorage</p>
  </footer>
</div>

<script id="payload" type="application/json">{payload_json}</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
window.MEDIANS = {json.dumps(medians)};
window.CAMPUS = [40.6929, -73.9870];
</script>
<script type="module" src="khoj/main.js"></script>
</body>
</html>
"""
