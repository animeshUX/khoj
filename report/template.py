"""HTML shell. No CSS or JS source — just the skeleton + <link>/<script> wiring."""
from __future__ import annotations

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
    date_str = datetime.now().date().isoformat()

    # Escape `</` so the JSON can't terminate the surrounding <script> tag if a
    # listing description ever contains "</script>".
    khoj_json = json.dumps(payload, default=str, separators=(',', ':')).replace('</', '<\\/')

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

<script>window.KHOJ = {khoj_json};</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script type="module" src="khoj/main.js"></script>
</body>
</html>
"""
