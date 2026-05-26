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
<header id="khoj-topbar"></header>
<main id="khoj-app">
  <aside id="khoj-list"></aside>
  <div id="khoj-map"></div>
  <aside id="khoj-panel" aria-hidden="true"></aside>
</main>

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
