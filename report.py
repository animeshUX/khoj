"""Render an editorial-newspaper dashboard for browsing scraped apartments.

A single self-contained HTML page with embedded CSS/JS. Light cream-paper theme,
Fraunces/Newsreader/JetBrains Mono. No external assets except Google Fonts and
Leaflet — both via CDN.

Information architecture:
- Inbox      — all visible listings, filterable
- Shortlist  — starred listings, comparison view
- Map        — Leaflet pins, color-coded by star/hide state

Per-listing thinking aids:
- Cleaned descriptions (phone-number + TEXT-ASAP spam stripped)
- Walking-time estimate, posted-relative time, anomaly hints vs median price
- Matched-keyword chips (Student-friendly / No guarantor / Furnished / etc.)
- Star / Hide / Note actions, all persisted to localStorage per device.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import statistics
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from scraper import Listing


_PHONE = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
_URL = re.compile(r'https?://\S+')
_TEXT_SPAM = re.compile(
    r'\b(text|call|email|reply|contact)\s+(me|us|now|asap|today|immediately|fast)\b[^.\n]{0,40}',
    re.I,
)
_REPEAT_NONWORD = re.compile(r'([^\w\s])\1{2,}')
_WS = re.compile(r'\s+')


def _clean_description(text: str) -> str:
    if not text:
        return ""
    text = _PHONE.sub("", text)
    text = _URL.sub("", text)
    text = _TEXT_SPAM.sub("", text)
    text = _REPEAT_NONWORD.sub(r"\1", text)
    return _WS.sub(" ", text).strip()


def _walking_minutes(miles):
    return round(miles * 20) if miles is not None else None


def _relative_posted(date_str):
    if not date_str:
        return ""
    try:
        d = datetime.fromisoformat(date_str).date()
    except ValueError:
        return date_str
    delta = (datetime.now().date() - d).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    return f"{delta} days ago"


_KEYWORD_TAGS = [
    (re.compile(r'\b(students?\s+welcome|nyu|grad\s+student|student[- ]friendly)\b', re.I), "Student-friendly"),
    (re.compile(r'\bno\s*guarantor', re.I), "No guarantor"),
    (re.compile(r'\bfurnished\b', re.I), "Furnished"),
    (re.compile(r'\b(utilities\s+included|all\s+utilities|util\.?\s*incl)\b', re.I), "Utilities incl."),
]
_TRAIN_RX = re.compile(r'\b([FACR])\s*(train|line)\b', re.I)

def _extract_tags(title, description):
    haystack = f"{title}\n{description}"
    tags = [label for rx, label in _KEYWORD_TAGS if rx.search(haystack)]
    train = _TRAIN_RX.search(haystack)
    if train:
        tags.append(f"{train.group(1).upper()} train")
    return tags


def _external_source(url: str) -> str:
    """For non-Craigslist URLs, return the friendly hostname (e.g. 'streeteasy.com')
    so the report can show a 'From streeteasy.com' badge. Returns '' for Craigslist."""
    host = (urlparse(url).hostname or "").lower()
    if not host or "craigslist.org" in host:
        return ""
    return host.removeprefix("www.")


def _payload(listings):
    out = []
    for i, l in enumerate(listings, 1):
        cleaned = _clean_description(l.description)
        desc = cleaned[:340] + ("…" if len(cleaned) > 340 else "")
        source = _external_source(l.url)
        out.append({
            "n": i,
            "url": l.url,
            "title": l.title,
            "price": l.price,
            "bedrooms": l.bedrooms,
            "neighborhood": l.neighborhood,
            "lat": l.lat,
            "lng": l.lng,
            "posted": l.posted_date,
            "postedRel": _relative_posted(l.posted_date),
            "description": desc,
            "distance": l.distance_miles,
            "walkMin": _walking_minutes(l.distance_miles),
            "score": l.score,
            "tags": _extract_tags(l.title, l.description or ""),
            "source": source,  # empty for Craigslist, hostname for external submissions
        })
    return out


def _market_medians(listings):
    """Median price per bedroom count — used to flag anomalies."""
    by_bed = {}
    for l in listings:
        if l.price and l.bedrooms is not None:
            by_bed.setdefault(l.bedrooms, []).append(l.price)
    return {str(k): int(statistics.median(v)) for k, v in by_bed.items() if v}


def _read_curated(path: str = "manual_links.txt"):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url, _, note = line.partition("|")
        out.append((url.strip(), note.strip()))
    return out


OTHER_SOURCES = [
    ("AmberStudent", "https://amberstudent.com/places/search/new-york-university-1811221663188",
     "managed student housing (per-room, booking-style)"),
    ("StreetEasy", "https://streeteasy.com/for-rent/brooklyn/price:800-1500%7Cbeds%3C=2",
     "NYC's biggest rental marketplace"),
    ("PadMapper", "https://www.padmapper.com/apartments/brooklyn-ny?maxRent=1500",
     "aggregator with map view"),
]


CSS = r"""
:root {
  --paper: #F3ECDE;
  --paper-tint: #E8DFCC;
  --paper-warm: #EDE3CE;
  --ink: #1A1612;
  --ink-soft: #5A4E42;
  --ink-mute: #93857A;
  --rule: #B8AB97;
  --rule-soft: #D6CBB6;
  --crimson: #8C2026;
  --crimson-deep: #6B1A1F;
  --crimson-tint: rgba(140, 32, 38, 0.06);
  --gold: #7A5C1E;
  --serif-display: 'Fraunces', Georgia, serif;
  --serif-body: 'Newsreader', Georgia, serif;
  --mono: 'JetBrains Mono', 'Courier New', monospace;

  /* Type scale — base 17px, major-third (1.25) ratio for headings.
     Smaller steps near body use a custom mono/small/micro triple so
     interactive controls have a touch-target hierarchy without the
     0.62/0.65/0.7/0.74/0.78rem jumble we used to have. */
  --type-mega:  4.5rem;     /* 76.5px — masthead display ceiling */
  --type-h1:    2.75rem;    /* 46.75px — h1 / dismissed stamp */
  --type-h2:    1.875rem;   /* 31.9px — entry serial number */
  --type-h3:    1.5rem;     /* 25.5px — stat values, entry titles */
  --type-h4:    1.25rem;    /* 21.25px — prices */
  --type-lead:  1.125rem;   /* 19.1px — masthead subhead, lead text */
  --type-body:  1rem;       /* 17px — body, descriptions */
  --type-small: 0.875rem;   /* 14.9px — tabs, action buttons */
  --type-mono:  0.8125rem;  /* 13.8px — mono meta lines, chips */
  --type-micro: 0.6875rem;  /* 11.7px — eyebrows, labels */

  --leading-display: 0.95;
  --leading-tight:   1.15;
  --leading-snug:    1.25;
  --leading-normal:  1.55;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }

body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif-body);
  font-size: 17px;
  line-height: var(--leading-normal);
  font-feature-settings: "kern", "liga", "calt";
  background-image:
    radial-gradient(circle at 90% 10%, rgba(140, 32, 38, 0.02), transparent 40%),
    radial-gradient(circle at 10% 90%, rgba(122, 92, 30, 0.03), transparent 40%),
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='240' height='240' filter='url(%23n)' opacity='0.06'/></svg>");
}

.paper { max-width: none; margin: 0; padding: 3rem 2rem 6rem; }

/* ------------------------------------------------------------------ Masthead */
.masthead {
  border-top: 8px solid var(--ink);
  border-bottom: 1px solid var(--rule);
  padding: 1rem 0 1.75rem;
  margin-bottom: 2rem;
  position: relative;
}
.masthead::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: -5px;
  border-bottom: 1px solid var(--rule);
}
.masthead-strap {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-soft);
  border-bottom: 1px solid var(--rule-soft);
  padding-bottom: 0.6rem;
  margin-bottom: 1.2rem;
}
.masthead-title {
  font-family: var(--serif-display);
  font-size: clamp(2.5rem, 5.4vw, var(--type-mega));
  font-weight: 500;
  font-variation-settings: "opsz" 144, "SOFT" 0, "WONK" 1;
  letter-spacing: -0.025em;
  margin: 0;
  line-height: var(--leading-display);
}
.masthead-title em {
  font-style: italic;
  color: var(--crimson);
  font-weight: 400;
  font-variation-settings: "opsz" 96, "SOFT" 100, "WONK" 1;
}
.masthead-sub {
  font-family: var(--serif-body);
  font-style: italic;
  color: var(--ink-soft);
  font-size: var(--type-lead);
  line-height: var(--leading-snug);
  max-width: 56ch;
  margin: 1.1rem 0 0;
  font-variation-settings: "opsz" 18;
}

/* ----------------------------------------------------------------- Stats row */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--rule);
  border: 1px solid var(--rule);
  margin: 1.5rem 0 2rem;
}
.stat {
  background: var(--paper-warm);
  padding: 0.85rem 1rem 0.95rem;
}
.stat-label {
  display: block;
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-bottom: 0.35rem;
}
.stat-value {
  font-family: var(--serif-display);
  font-size: var(--type-h3);
  font-weight: 500;
  font-variation-settings: "opsz" 72;
  letter-spacing: -0.01em;
  line-height: var(--leading-tight);
}

/* ----------------------------------------------------------------------- Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--ink);
  margin-bottom: 1.25rem;
}
.tab {
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  padding: 0.7rem 1.4rem 0.7rem 1.4rem;
  font-family: var(--mono);
  font-size: var(--type-small);
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
  white-space: nowrap;
  transition: color 120ms ease, background 120ms ease;
}
.tab:first-child { padding-left: 0; }
.tab:hover { color: var(--ink); background: rgba(140, 32, 38, 0.045); }
.tab.active { color: var(--ink); border-bottom-color: var(--crimson); }
.tab:focus-visible {
  outline: 2px solid var(--crimson);
  outline-offset: 2px;
  border-radius: 1px;
}
.tab-count {
  display: inline-block;
  font-size: var(--type-micro);
  background: var(--ink);
  color: var(--paper);
  padding: 0.15rem 0.4rem;
  margin-left: 0.5rem;
  letter-spacing: 0;
  border-radius: 1px;
  vertical-align: 2px;
}
.tab.active .tab-count { background: var(--crimson); }

/* ----------------------------------------------------------- Filters + sort */
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--rule-soft);
}
.chip-group { display: flex; gap: 0.3rem; align-items: center; }
.chip-group::before {
  content: attr(data-label);
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-right: 0.5rem;
}
.chip {
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--ink-soft);
  padding: 0.35rem 0.75rem;
  font-family: var(--mono);
  font-size: var(--type-mono);
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 100ms ease;
  border-radius: 1px;
}
.chip:hover { background: var(--paper-warm); color: var(--ink); border-color: var(--ink-soft); }
.chip.active {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.chip:focus-visible {
  outline: 2px solid var(--crimson);
  outline-offset: 2px;
}
.sort-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
  font-family: var(--mono);
  font-size: var(--type-mono);
}
.sort-wrap label {
  font-size: var(--type-micro);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-mute);
}
#sort {
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 0.4rem 0.7rem;
  font-family: var(--mono);
  font-size: var(--type-mono);
  color: var(--ink);
  cursor: pointer;
  transition: border-color 120ms ease;
}
#sort:hover { border-color: var(--ink); }
#sort:focus-visible { outline: 2px solid var(--crimson); outline-offset: 2px; }

/* ----------------------------------------------------------------- Views */
.view { display: none; }
.view.active { display: block; }

/* ----------------------------------------------------------- Listings */
.listings { list-style: none; padding: 0; margin: 0; }

.entry {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 1.75rem;
  padding: 1.75rem 0;
  border-bottom: 1px solid var(--rule-soft);
  position: relative;
  animation: enter 380ms ease both;
}
.entry:nth-child(1) { animation-delay: 0ms; }
.entry:nth-child(2) { animation-delay: 40ms; }
.entry:nth-child(3) { animation-delay: 80ms; }
.entry:nth-child(4) { animation-delay: 120ms; }
.entry:nth-child(5) { animation-delay: 160ms; }
.entry:nth-child(n+6) { animation-delay: 200ms; }
.entry:hover { background: var(--crimson-tint); }

@keyframes enter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.entry-num {
  font-family: var(--serif-display);
  font-size: var(--type-h2);
  font-weight: 400;
  font-variation-settings: "opsz" 96;
  color: var(--ink-mute);
  letter-spacing: -0.04em;
  line-height: 1;
  text-align: center;
  padding-top: 0.1rem;
  user-select: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}
.entry-num.score-high { color: var(--crimson); font-weight: 600; }
.entry-num.score-mid { color: var(--ink); }

.entry-num-meta {
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-mute);
  text-align: center;
  font-weight: 500;
  margin-top: -0.15rem;
}
.entry-num-meta.fresh { color: var(--crimson); }
.entry-num-meta.external {
  color: var(--gold);
  letter-spacing: 0.06em;
  text-transform: lowercase;
}
.entry.is-external .entry-num { color: var(--gold); }

.entry-body { display: flex; flex-direction: column; gap: 0.5rem; min-width: 0; }

.entry-meta {
  font-family: var(--mono);
  font-size: var(--type-mono);
  color: var(--ink-soft);
  letter-spacing: 0.03em;
  line-height: var(--leading-snug);
}
.entry-meta .price {
  font-family: var(--serif-display);
  font-size: var(--type-h4);
  font-weight: 600;
  color: var(--ink);
  font-variation-settings: "opsz" 36;
  letter-spacing: -0.01em;
  margin-right: 0.4rem;
}
.entry-meta .sep { color: var(--ink-mute); margin: 0 0.4rem; }
.entry-meta .anomaly-low {
  color: var(--crimson);
  font-weight: 600;
  white-space: nowrap;
}
.entry-meta .anomaly-high {
  color: var(--gold);
  white-space: nowrap;
}

.entry-title {
  font-family: var(--serif-display);
  font-size: var(--type-h3);
  font-weight: 500;
  font-variation-settings: "opsz" 36, "SOFT" 30, "WONK" 0;
  line-height: var(--leading-tight);
  letter-spacing: -0.012em;
  margin: 0.2rem 0 0;
  color: var(--ink);
}
.entry-title a {
  color: inherit;
  text-decoration: none;
  background-image: linear-gradient(var(--crimson), var(--crimson));
  background-size: 0 1px;
  background-repeat: no-repeat;
  background-position: 0 100%;
  transition: background-size 220ms ease;
  padding-bottom: 1px;
}
.entry-title a:hover { background-size: 100% 1px; color: var(--crimson); }

.entry-desc {
  font-family: var(--serif-body);
  color: var(--ink-soft);
  font-size: var(--type-body);
  line-height: var(--leading-normal);
  margin: 0.4rem 0 0;
  max-width: 58ch;
  font-variation-settings: "opsz" 17;
}

.entry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.5rem 0 0;
}
.tag {
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.06em;
  padding: 0.22rem 0.6rem;
  border: 1px solid var(--rule);
  color: var(--ink-soft);
  background: var(--paper-warm);
  border-radius: 1px;
}

.entry-actions {
  display: flex;
  gap: 0.45rem;
  margin-top: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}
.act {
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--ink);
  padding: 0.45rem 0.9rem;
  font-family: var(--mono);
  font-size: var(--type-small);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  text-decoration: none;
  transition: all 100ms ease;
  border-radius: 1px;
  white-space: nowrap;
}
.act:hover {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.act-primary {
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.act-primary:hover { background: var(--crimson); border-color: var(--crimson); }

.act-star.starred {
  background: var(--crimson);
  color: var(--paper);
  border-color: var(--crimson);
}
.act-star.starred:hover { background: var(--crimson-deep); border-color: var(--crimson-deep); }

/* Hidden state */
.entry.is-hidden { opacity: 0.32; }
.entry.is-hidden::after {
  content: "DISMISSED";
  position: absolute;
  top: 50%; left: 30%;
  transform: translate(-50%, -50%) rotate(-7deg);
  font-family: var(--serif-display);
  font-size: var(--type-h1);
  font-weight: 700;
  color: var(--crimson);
  opacity: 0.35;
  letter-spacing: 0.22em;
  pointer-events: none;
  border: 4px double var(--crimson);
  padding: 0.4rem 1.2rem;
}

/* Note area */
.note-area {
  display: none;
  margin-top: 0.75rem;
  max-width: 56ch;
}
.note-area.open { display: block; }
.note-area textarea {
  width: 100%;
  background: var(--paper);
  border: 1px solid var(--rule);
  font-family: var(--serif-body);
  font-style: italic;
  font-size: var(--type-body);
  padding: 0.65rem 0.85rem;
  resize: vertical;
  min-height: 72px;
  color: var(--ink);
}
.note-area-actions { display: flex; gap: 0.4rem; margin-top: 0.45rem; }

.note-display {
  font-family: var(--serif-body);
  font-style: italic;
  color: var(--ink-soft);
  background: var(--paper-warm);
  padding: 0.6rem 0.9rem 0.6rem 1rem;
  border-left: 3px solid var(--gold);
  margin-top: 0.65rem;
  font-size: var(--type-body);
  max-width: 58ch;
  line-height: var(--leading-snug);
}
.note-display::before {
  content: "Note · ";
  font-family: var(--mono);
  font-style: normal;
  font-size: var(--type-micro);
  color: var(--gold);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-right: 0.2rem;
}

/* Empty states */
.empty {
  text-align: center;
  padding: 4rem 1rem;
  color: var(--ink-soft);
  font-style: italic;
  font-family: var(--serif-body);
  font-size: var(--type-lead);
}

/* ----------------------------------------------------------------- Map */
#map {
  height: 520px;
  width: 100%;
  border: 1px solid var(--rule);
  background: var(--paper-tint);
}
.leaflet-popup-content { font-family: var(--serif-body); }
.leaflet-popup-content b { font-family: var(--serif-display); font-weight: 600; }
.leaflet-popup-content a { color: var(--crimson); }

.khoj-pin {
  background: var(--ink);
  border: 2px solid var(--paper);
  border-radius: 50%;
  width: 14px;
  height: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}
.khoj-pin.is-campus {
  background: var(--crimson);
  width: 20px; height: 20px;
  box-shadow: 0 0 0 4px var(--paper), 0 2px 6px rgba(140,32,38,0.4);
}
.khoj-pin.is-starred { background: var(--crimson); }
.khoj-pin.is-hidden { background: var(--ink-mute); opacity: 0.5; }

/* ----------------------------------------------------------- Colophon */
.colophon {
  margin-top: 4rem;
  padding-top: 2rem;
  border-top: 1px solid var(--rule);
  font-family: var(--serif-body);
  color: var(--ink-soft);
  font-size: var(--type-body);
  line-height: var(--leading-normal);
}
.colophon h3 {
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin: 1.5rem 0 0.6rem;
  font-weight: 500;
}
.colophon ul { padding-left: 1.25rem; margin: 0.25rem 0 1rem; }
.colophon li { margin: 0.35rem 0; }
.colophon a { color: var(--ink); text-decoration: underline; text-decoration-color: var(--rule); }
.colophon a:hover { text-decoration-color: var(--crimson); color: var(--crimson); }
.colophon .small {
  margin-top: 1.5rem;
  font-family: var(--mono);
  font-size: var(--type-micro);
  color: var(--ink-mute);
  letter-spacing: 0.06em;
}

/* ----------------------------------------------------------- List + Map layout */
.list-with-map { display: block; }    /* single column by default */
.list-column { min-width: 0; }
.map-panel { display: none; }          /* hidden until >=1100px viewport */

.map-panel-caption {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-mute);
  padding: 0.55rem 0.25rem 0.65rem;
  border-top: 2px solid var(--ink);
}
.map-panel-caption > .caption-text { flex: 1; min-width: 0; }

.tile-select {
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink);
  background-color: var(--paper);
  border: 1px solid var(--rule);
  padding: 0.32rem 1.6rem 0.32rem 0.55rem;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image:
    linear-gradient(45deg,  transparent 50%, var(--ink-soft) 50%),
    linear-gradient(135deg, var(--ink-soft) 50%, transparent 50%);
  background-position: calc(100% - 13px) 55%, calc(100% - 8px) 55%;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}
.tile-select:hover { border-color: var(--ink); }
.tile-select:focus-visible { outline: 2px solid var(--crimson); outline-offset: 2px; }

/* Mobile-only inline map (shown when right rail is hidden) */
.map-inline { display: block; margin: 2rem 0; }
#map-mobile {
  width: 100%;
  height: 420px;
  border: 1px solid var(--rule);
  background: var(--paper-tint);
}

@media (min-width: 1100px) {
  .paper { max-width: none; }       /* full viewport width */
  .list-with-map {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(440px, 44vw, 820px);
    gap: 2.5rem;
    align-items: start;
  }
  .map-panel {
    display: block;
    position: sticky;
    top: 1.25rem;
    height: calc(100vh - 2.5rem);
    min-height: 620px;
    max-height: 960px;
  }
  #map-side {
    width: 100%;
    height: calc(100% - 2.4rem);
    border: 1px solid var(--rule);
    background: var(--paper-tint);
    box-shadow: 0 2px 14px rgba(26, 22, 18, 0.08);
  }
  /* Desktop has the sticky right-rail map; hide the inline one */
  .map-inline { display: none; }
}

/* Linked entry ↔ pin selection state + clickability affordance */
.entry { cursor: pointer; transition: background 140ms ease; position: relative; }
.entry:hover { background: rgba(140, 32, 38, 0.025); }
.entry:hover .entry-title a { color: var(--crimson); }
.entry.is-active { background: rgba(140, 32, 38, 0.06); }
.entry.is-active::before {
  content: "";
  position: absolute;
  left: 0; top: 1rem; bottom: 1rem;
  width: 3px;
  background: var(--crimson);
}
.entry.is-active .entry-num,
.entry.is-active .entry-num-meta { color: var(--crimson); }

/* Action buttons — focus ring for keyboard nav, harden the affordance */
.act:focus-visible {
  outline: 2px solid var(--crimson);
  outline-offset: 2px;
}

/* ----------------------------------------------------------------- Map (Leaflet) */
#map, #map-side {
  height: 520px;
  width: 100%;
  border: 1px solid var(--rule);
  background: var(--paper-tint);
}
.leaflet-popup-content { font-family: var(--serif-body); font-size: var(--type-small); line-height: 1.4; }
.leaflet-popup-content b { font-family: var(--serif-display); font-weight: 600; }
.leaflet-popup-content a { color: var(--crimson); }

.khoj-pin {
  background: var(--ink);
  border: 2px solid var(--paper);
  border-radius: 50%;
  width: 14px;
  height: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
  transition: transform 140ms ease, box-shadow 140ms ease;
  cursor: pointer;
}
.khoj-pin.is-campus {
  background: var(--crimson);
  width: 20px; height: 20px;
  box-shadow: 0 0 0 4px var(--paper), 0 2px 6px rgba(140,32,38,0.4);
}
.khoj-pin.is-starred { background: var(--crimson); }
.khoj-pin.is-hidden { background: var(--ink-mute); opacity: 0.5; }
.khoj-pin.is-active {
  background: var(--crimson) !important;
  width: 22px !important; height: 22px !important;
  box-shadow: 0 0 0 5px rgba(140, 32, 38, 0.22),
              0 3px 10px rgba(0, 0, 0, 0.35) !important;
  transform: scale(1.15);
  z-index: 1000 !important;
}

/* Distance-ring labels and subway-station tooltip styling */
.ring-label {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--crimson);
  background: var(--paper);
  padding: 0.05rem 0.35rem;
  border: 1px solid rgba(140, 32, 38, 0.45);
  border-radius: 1px;
  text-align: center;
  white-space: nowrap;
}
.leaflet-tooltip.station-tooltip {
  font-family: var(--mono);
  font-size: var(--type-micro);
  background: var(--paper);
  border: 1px solid var(--rule);
  color: var(--ink);
  padding: 0.25rem 0.5rem;
  border-radius: 1px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
}
.leaflet-tooltip.station-tooltip b { font-family: var(--serif-display); font-weight: 600; }
.leaflet-tooltip.station-tooltip::before { display: none; }    /* hide arrow */

/* Layer control — overlay toggles, top-right of the map */
.leaflet-control-layers {
  background: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  border-radius: 1px !important;
  box-shadow: 3px 3px 0 var(--paper-tint), 3px 3px 0 1px var(--ink) !important;
  font-family: var(--mono);
  font-size: var(--type-micro);
  color: var(--ink);
}
.leaflet-control-layers-toggle {
  background-color: var(--paper) !important;
  background-image: none !important;
  width: 32px; height: 32px;
}
.leaflet-control-layers-toggle::before {
  content: "LAYERS";
  display: block;
  font-family: var(--mono);
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--ink);
  line-height: 32px;
  text-align: center;
}
.leaflet-control-layers-expanded {
  padding: 0.65rem 0.85rem 0.7rem !important;
  min-width: 180px;
}
.leaflet-control-layers-expanded::before {
  content: "OVERLAYS";
  display: block;
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-bottom: 0.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--rule-soft);
}
.leaflet-control-layers-overlays {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.leaflet-control-layers-overlays label {
  cursor: pointer;
  font-family: var(--mono);
  font-size: var(--type-micro);
  letter-spacing: 0.05em;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.leaflet-control-layers-overlays label:hover { color: var(--crimson); }
.leaflet-control-layers-overlays input[type="checkbox"] {
  accent-color: var(--crimson);
}
.leaflet-control-layers-separator {
  border-top: 1px solid var(--rule-soft) !important;
  margin: 0.4rem 0 !important;
}

/* ----------------------------------------------------------- Responsive */
@media (max-width: 720px) {
  .paper { padding: 1.5rem 1rem 3rem; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .entry { grid-template-columns: 60px 1fr; gap: 1rem; padding: 1.25rem 0; }
  .entry-num { font-size: var(--type-h3); }
  .controls { flex-direction: column; align-items: stretch; }
  .sort-wrap { margin-left: 0; justify-content: space-between; }
  .chip-group { flex-wrap: wrap; }
  .masthead-title { font-size: 2.5rem; }
}
"""


JS = r"""
(function () {
  const PAYLOAD = JSON.parse(document.getElementById('payload').textContent);
  const PREFIX = 'khoj.';
  const state = {
    starred: new Set(JSON.parse(localStorage.getItem(PREFIX + 'starred') || '[]')),
    hidden:  new Set(JSON.parse(localStorage.getItem(PREFIX + 'hidden')  || '[]')),
    notes:   JSON.parse(localStorage.getItem(PREFIX + 'notes') || '{}'),
    tab: 'inbox',
    bed: 'all',
    price: 'all',
    sort: 'score',
  };

  function persist() {
    localStorage.setItem(PREFIX + 'starred', JSON.stringify([...state.starred]));
    localStorage.setItem(PREFIX + 'hidden',  JSON.stringify([...state.hidden]));
    localStorage.setItem(PREFIX + 'notes',   JSON.stringify(state.notes));
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function pad(n) { return String(n).padStart(3, '0'); }

  function applyFilters(list) {
    return list.filter(l => {
      if (state.bed !== 'all' && String(l.bedrooms) !== state.bed) return false;
      if (state.price === 'under1200' && (!l.price || l.price >= 1200)) return false;
      if (state.price === '1200to1500' && (!l.price || l.price < 1200 || l.price > 1500)) return false;
      return true;
    });
  }

  const SORTERS = {
    score:    (a, b) => (b.score || 0) - (a.score || 0),
    price:    (a, b) => (a.price || 9e9) - (b.price || 9e9),
    distance: (a, b) => (a.distance || 9e9) - (b.distance || 9e9),
    posted:   (a, b) => (b.posted || '0').localeCompare(a.posted || '0'),
  };

  function freshnessFor(posted) {
    if (!posted) return null;
    const [y, m, day] = posted.split('-').map(Number);
    const d = new Date(y, m - 1, day);
    const ageDays = (Date.now() - d.getTime()) / 86400000;
    if (ageDays < 1.2) return 'fresh';
    return null;
  }

  function priceAnomaly(price, bedrooms) {
    const median = MEDIANS[String(bedrooms)];
    if (!median || !price) return '';
    const ratio = price / median;
    if (ratio < 0.88) return `<span class="anomaly-low">↓ ${Math.round((1 - ratio) * 100)}% under median</span>`;
    if (ratio > 1.12) return `<span class="anomaly-high">↑ ${Math.round((ratio - 1) * 100)}% over median</span>`;
    return '';
  }

  function entryHTML(l) {
    const starred = state.starred.has(l.url);
    const hidden = state.hidden.has(l.url);
    const note = state.notes[l.url];
    const isExternal = !!l.source;       // non-Craigslist submissions
    const bedLabel = l.bedrooms === 0 ? 'Studio' : (l.bedrooms != null ? l.bedrooms + ' BR' : '?');
    const walking = l.walkMin ? `${l.walkMin} min walk` : '';
    const distance = l.distance != null ? `${l.distance.toFixed(2)} mi` : '?';
    const fresh = freshnessFor(l.posted);
    const numClass = 'entry-num ' + (l.score >= 40 ? 'score-high' : l.score >= 20 ? 'score-mid' : '');
    // Eyebrow label under the serial number: source domain for external,
    // Fresh/Score for Craigslist scrapes.
    const numMetaLabel = isExternal ? l.source : (fresh ? 'Fresh' : 'Score ' + l.score);
    const tags = (l.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('');
    const anomaly = priceAnomaly(l.price, l.bedrooms);
    const ctaLabel = isExternal ? `View on ${esc(l.source)} →` : 'View on Craigslist →';
    const datePrefix = isExternal ? 'submitted ' : 'posted ';

    return `
      <li class="entry${hidden ? ' is-hidden' : ''}${starred ? ' is-starred' : ''}${isExternal ? ' is-external' : ''}" data-url="${esc(l.url)}">
        <div class="${numClass}">
          ${pad(l.n)}
          <div class="entry-num-meta${fresh && !isExternal ? ' fresh' : ''}${isExternal ? ' external' : ''}">${esc(numMetaLabel)}</div>
        </div>
        <div class="entry-body">
          <div class="entry-meta">
            <span class="price">${l.price != null ? '$' + l.price.toLocaleString() : '$?'}</span>
            ${esc(bedLabel)}
            <span class="sep">·</span>${esc(distance)}${walking ? ' (' + esc(walking) + ')' : ''}
            <span class="sep">·</span>${esc(l.neighborhood || 'Brooklyn')}
            <span class="sep">·</span>${datePrefix}${esc(l.postedRel || '?')}
            ${anomaly ? '<span class="sep">·</span>' + anomaly : ''}
          </div>
          <h2 class="entry-title"><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a></h2>
          ${l.description ? `<p class="entry-desc">${esc(l.description)}</p>` : ''}
          ${tags ? `<div class="entry-tags">${tags}</div>` : ''}
          ${note ? `<div class="note-display">${esc(note)}</div>` : ''}
          <div class="entry-actions">
            <a class="act act-primary" href="${esc(l.url)}" target="_blank" rel="noopener">${ctaLabel}</a>
            <button class="act act-star${starred ? ' starred' : ''}" data-act="star">★ ${starred ? 'Starred' : 'Star'}</button>
            <button class="act" data-act="hide">${hidden ? 'Restore' : 'Hide'}</button>
            <button class="act" data-act="note">${note ? '✎ Edit Note' : '✎ Note'}</button>
          </div>
          <div class="note-area">
            <textarea placeholder="What stood out about this listing?">${esc(note || '')}</textarea>
            <div class="note-area-actions">
              <button class="act act-primary" data-act="save-note">Save</button>
              <button class="act" data-act="cancel-note">Cancel</button>
              ${note ? '<button class="act" data-act="delete-note">Delete</button>' : ''}
            </div>
          </div>
        </div>
      </li>
    `;
  }

  function render() {
    // Tab state
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === state.tab));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + state.tab));

    // Header counts
    const visible = PAYLOAD.filter(l => !state.hidden.has(l.url)).length;
    document.getElementById('inbox-count').textContent = visible;
    document.getElementById('short-count').textContent = state.starred.size;
    document.getElementById('shortlist-stat').textContent = state.starred.size;

    if (state.tab === 'inbox') {
      const list = applyFilters(PAYLOAD.filter(l => !state.hidden.has(l.url)));
      list.sort(SORTERS[state.sort] || SORTERS.score);
      document.getElementById('listings').innerHTML =
        list.length ? list.map(entryHTML).join('')
                    : '<p class="empty">No listings match the current filters.</p>';
    } else if (state.tab === 'shortlist') {
      const list = applyFilters(PAYLOAD.filter(l => state.starred.has(l.url)));
      list.sort(SORTERS[state.sort] || SORTERS.score);
      const el = document.getElementById('shortlist-listings');
      const empty = document.getElementById('shortlist-empty');
      if (list.length === 0) {
        el.innerHTML = '';
        empty.style.display = 'block';
      } else {
        el.innerHTML = list.map(entryHTML).join('');
        empty.style.display = 'none';
      }
    }
    // Keep the live map's markers in sync with star/hide state on every render
    refreshMapMarkers();
  }

  // ------- Map -----------------------------------------------------------
  // Two possible mount points:
  //   #map-side : persistent right-rail panel, mounted on page load (desktop only)
  //   #map      : full-width view under the Map tab (mobile/back-compat)
  // We mount whichever element is in the DOM and visible. markerByUrl is shared
  // so hover/click highlighting Just Works regardless of which mount is live.
  let mapInstance = null;
  let mountedAt = null;            // 'map-side' | 'map'
  const markerByUrl = new Map();   // url → Leaflet marker

  // Tile providers — all free, no API key. Picked for utility navigating NYC:
  // Streets for orientation, Minimal so pins pop, Satellite for what the block
  // actually looks like, Transit because the train is how you'll actually get
  // to campus. Selection persists in localStorage so it survives refreshes.
  const TILE_PROVIDERS = {
    streets: {
      label: 'Streets',
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    },
    minimal: {
      label: 'Minimal',
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      maxZoom: 20,
      subdomains: 'abcd',
    },
    satellite: {
      label: 'Satellite',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: 'Tiles &copy; Esri',
      maxZoom: 19,
    },
    transit: {
      label: 'Transit',
      url: 'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap, &copy; memomaps.de',
      maxZoom: 18,
    },
  };
  const TILE_DEFAULT = 'streets';
  const TILE_KEY = 'khoj.tile';
  let currentTileLayer = null;

  function getTileChoice() {
    try { return localStorage.getItem(TILE_KEY) || TILE_DEFAULT; } catch { return TILE_DEFAULT; }
  }
  function applyTile(key) {
    if (!mapInstance) return;
    const cfg = TILE_PROVIDERS[key] || TILE_PROVIDERS[TILE_DEFAULT];
    if (currentTileLayer) currentTileLayer.remove();
    const opts = { attribution: cfg.attribution, maxZoom: cfg.maxZoom };
    if (cfg.subdomains) opts.subdomains = cfg.subdomains;
    currentTileLayer = L.tileLayer(cfg.url, opts).addTo(mapInstance);
  }

  function setupTileSelects() {
    const choice = getTileChoice();
    document.querySelectorAll('[data-tile-select]').forEach(sel => {
      sel.innerHTML = Object.entries(TILE_PROVIDERS).map(([k, p]) =>
        `<option value="${k}"${k === choice ? ' selected' : ''}>${p.label}</option>`).join('');
      sel.addEventListener('change', () => {
        try { localStorage.setItem(TILE_KEY, sel.value); } catch {}
        applyTile(sel.value);
        document.querySelectorAll('[data-tile-select]').forEach(s => {
          if (s !== sel) s.value = sel.value;
        });
      });
    });
  }

  function mountMap(targetId) {
    if (mapInstance && mountedAt === targetId) { refreshMapMarkers(); return; }
    if (mapInstance) { mapInstance.remove(); markerByUrl.clear(); currentTileLayer = null; }
    const el = document.getElementById(targetId);
    if (!el) return;
    mountedAt = targetId;
    mapInstance = L.map(targetId, { scrollWheelZoom: false }).setView(CAMPUS, 13);
    applyTile(getTileChoice());

    drawDistanceRings();
    loadStaticLayers();  // commute zone + subway lines + stations (async, non-blocking)

    L.marker(CAMPUS, {
      icon: L.divIcon({ className: 'khoj-pin is-campus', iconSize: [20, 20] }),
      zIndexOffset: 1000,
      interactive: false,
    }).addTo(mapInstance).bindPopup('<b>NYU Tandon</b><br>370 Jay St');
    refreshMapMarkers();
    const coords = PAYLOAD.filter(l => l.lat != null && l.lng != null).map(l => [l.lat, l.lng]);
    coords.push(CAMPUS);
    if (coords.length > 1) mapInstance.fitBounds(coords, { padding: [40, 40] });
  }

  // ------- Static layers: rings, commute zone, subway lines + stations --
  const METERS_PER_MILE = 1609.344;
  const RING_MILES = [1, 2, 3, 4];
  // MTA service colors. We only color the lines that hit Jay St-MetroTech.
  const ROUTE_COLOR = {
    F: '#FF6319', A: '#2850AD', C: '#2850AD', R: '#FCCC0A',
  };

  function drawDistanceRings() {
    RING_MILES.forEach(mi => {
      L.circle(CAMPUS, {
        radius: mi * METERS_PER_MILE,
        color: '#8C2026', weight: 1, opacity: 0.32,
        dashArray: '4 6', fill: false, interactive: false,
      }).addTo(mapInstance);
      // Label at 12 o'clock (north) on the ring
      const dlat = (mi * METERS_PER_MILE) / 111000;
      L.marker([CAMPUS[0] + dlat, CAMPUS[1]], {
        icon: L.divIcon({
          className: 'ring-label',
          html: `${mi} mi`,
          iconSize: [40, 14],
          iconAnchor: [20, 7],
        }),
        interactive: false,
        zIndexOffset: -500,
      }).addTo(mapInstance);
    });
  }

  function loadStaticLayers() {
    // Order matters: zone first (bottom), then lines, then stations.
    // After all layers add, bring listing markers to front.
    fetch('data/commute-zone.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        style: {
          color: '#8C2026', weight: 1.2, opacity: 0.6, dashArray: '6 4',
          fillColor: '#8C2026', fillOpacity: 0.055,
        },
        interactive: false,
      }).addTo(mapInstance).bringToBack();
    }).catch(() => {});

    fetch('data/subway-lines.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        style: { color: '#1A1612', weight: 1.4, opacity: 0.22 },
        interactive: false,
      }).addTo(mapInstance);
      if (markerLayer) markerLayer.bringToFront();
    }).catch(() => {});

    fetch('data/subway-stations.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      L.geoJSON(geo, {
        pointToLayer: (feat, latlng) => {
          const routes = (feat.properties.daytime_routes || '').split(' ').filter(Boolean);
          // Find first colored route this station serves; otherwise muted gray
          const color = routes.map(r => ROUTE_COLOR[r]).find(Boolean);
          const isRelevant = !!color;
          return L.circleMarker(latlng, {
            radius: isRelevant ? 3.5 : 2,
            color: '#fff', weight: 0.7,
            fillColor: color || '#93857A',
            fillOpacity: isRelevant ? 0.92 : 0.5,
            interactive: isRelevant,
          });
        },
        onEachFeature: (feat, layer) => {
          if (layer.bindTooltip) {
            layer.bindTooltip(
              `<b>${esc(feat.properties.stop_name || '')}</b><br>${esc(feat.properties.daytime_routes || '—')}`,
              { direction: 'top', className: 'station-tooltip' }
            );
          }
        },
      }).addTo(mapInstance);
      if (markerLayer) markerLayer.bringToFront();
    }).catch(() => {});

    loadToggleableOverlays();
  }

  // Layers the user can flip on/off via L.control.layers — they're NOT added to
  // the map by default; the control just registers them so the brother can pick.
  function loadToggleableOverlays() {
    // Create control upfront so async layers can register as they arrive
    const control = L.control.layers(null, {}, {
      collapsed: true, position: 'topright', sortLayers: false,
    }).addTo(mapInstance);

    // --- Neighborhoods + 90-day 311 noise complaints ---
    fetch('data/nta-noise.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;

      // Compute the upper bound of noise density for color scaling. We use
      // 90th percentile (not max) so a few outliers don't blow out the gradient.
      const dens = geo.features.map(f => f.properties.noise_per_sqmi).sort((a, b) => a - b);
      const p90 = dens[Math.floor(dens.length * 0.9)] || 1;

      const ntaOutlines = L.geoJSON(geo, {
        style: { color: '#1A1612', weight: 0.7, opacity: 0.35, fillOpacity: 0 },
        onEachFeature: (feat, layer) => {
          layer.bindTooltip(esc(feat.properties.name), {
            sticky: true, className: 'station-tooltip', direction: 'top',
          });
        },
      });

      const noiseLayer = L.geoJSON(geo, {
        style: (feat) => {
          const d = feat.properties.noise_per_sqmi || 0;
          const ratio = Math.min(d / p90, 1);
          return {
            color: '#8C2026', weight: 0.4, opacity: 0.35,
            fillColor: '#8C2026', fillOpacity: 0.04 + ratio * 0.42,
          };
        },
        onEachFeature: (feat, layer) => {
          const p = feat.properties;
          layer.bindTooltip(
            `<b>${esc(p.name)}</b><br>${esc(p.borough)}<br>` +
            `${(p.noise_90d || 0).toLocaleString()} noise complaints / 90d<br>` +
            `${(p.noise_per_sqmi || 0).toLocaleString()} per sq mi`,
            { sticky: true, className: 'station-tooltip', direction: 'top' }
          );
        },
      });

      control.addOverlay(ntaOutlines, '🏘 Neighborhood borders');
      control.addOverlay(noiseLayer, '🔊 311 noise (last 90 days)');
    }).catch(() => {});

    // --- Parks ---
    fetch('data/parks.geojson').then(r => r.ok && r.json()).then(geo => {
      if (!geo || !mapInstance) return;
      const parksLayer = L.geoJSON(geo, {
        style: {
          color: '#3F5F3F', weight: 0.4, opacity: 0.55,
          fillColor: '#7BAA7B', fillOpacity: 0.42,
        },
        onEachFeature: (feat, layer) => {
          const p = feat.properties;
          if (p.name) {
            layer.bindTooltip(
              `<b>${esc(p.name)}</b><br>${(p.acres || 0).toFixed(1)} acres`,
              { sticky: true, className: 'station-tooltip', direction: 'top' }
            );
          }
        },
      });
      control.addOverlay(parksLayer, '🌳 Parks');
    }).catch(() => {});
  }

  let markerLayer = null;
  function refreshMapMarkers() {
    if (!mapInstance) return;
    if (markerLayer) markerLayer.remove();
    markerLayer = L.layerGroup().addTo(mapInstance);
    markerByUrl.clear();
    PAYLOAD.forEach(l => {
      if (l.lat == null || l.lng == null) return;
      const cls = state.hidden.has(l.url) ? 'is-hidden'
                : state.starred.has(l.url) ? 'is-starred'
                : '';
      const marker = L.marker([l.lat, l.lng], {
        icon: L.divIcon({ className: 'khoj-pin ' + cls, iconSize: [14, 14] }),
      });
      const bedTxt = l.bedrooms === 0 ? 'Studio'
                  : (l.bedrooms != null ? l.bedrooms + 'BR' : '?');
      const distTxt = l.distance != null ? l.distance.toFixed(2) + ' mi' : '? mi';
      marker.bindPopup(
        `<b>#${pad(l.n)} ${esc(l.title)}</b><br>` +
        `${l.price != null ? '$' + l.price.toLocaleString() : '$?'} · ${esc(bedTxt)} · ${esc(distTxt)}<br>` +
        `<a href="${esc(l.url)}" target="_blank" rel="noopener">View →</a>`
      );
      marker.on('click', () => focusEntry(l.url, { scroll: true }));
      marker.addTo(markerLayer);
      markerByUrl.set(l.url, marker);
    });
  }

  // ------- Linked entry ↔ pin highlight ---------------------------------
  let activeUrl = null;
  function setActive(url, opts) {
    opts = opts || {};
    if (activeUrl === url) return;
    // clear previous
    if (activeUrl) {
      document.querySelectorAll('.entry.is-active').forEach(e => e.classList.remove('is-active'));
      const prev = markerByUrl.get(activeUrl);
      if (prev) {
        const cls = prev.getElement && prev.getElement();
        if (cls) cls.classList.remove('is-active');
      }
    }
    activeUrl = url;
    if (!url) return;
    document.querySelectorAll(`.entry[data-url="${cssEscape(url)}"]`).forEach(e => e.classList.add('is-active'));
    const m = markerByUrl.get(url);
    if (m) {
      const el = m.getElement && m.getElement();
      if (el) el.classList.add('is-active');
      if (opts.pan && mapInstance) mapInstance.panTo(m.getLatLng(), { animate: true });
      if (opts.openPopup) m.openPopup();
    }
  }

  function focusEntry(url, opts) {
    opts = opts || {};
    setActive(url, { pan: true, openPopup: true });
    if (opts.scroll) {
      const el = document.querySelector(`.entry[data-url="${cssEscape(url)}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function cssEscape(s) {
    return String(s).replace(/(["\\])/g, '\\$1');
  }

  // ------- Event wiring --------------------------------------------------
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => { state.tab = tab.dataset.tab; render(); });
  });

  document.querySelectorAll('.chip-group').forEach(group => {
    const filterName = group.dataset.filter;
    group.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state[filterName] = chip.dataset.val;
        render();
      });
    });
  });

  document.getElementById('sort').addEventListener('change', e => {
    state.sort = e.target.value;
    render();
  });

  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-act]');
    if (btn) {
      const entry = btn.closest('.entry');
      if (!entry) return;
      const url = entry.dataset.url;
      const act = btn.dataset.act;
      const toggle = (set) => set.has(url) ? set.delete(url) : set.add(url);
      if (act === 'star') {
        toggle(state.starred); persist(); render();
      } else if (act === 'hide') {
        toggle(state.hidden); persist(); render();
      } else if (act === 'note') {
        entry.querySelector('.note-area').classList.toggle('open');
      } else if (act === 'save-note') {
        const txt = entry.querySelector('textarea').value.trim();
        if (txt) state.notes[url] = txt; else delete state.notes[url];
        persist(); render();
      } else if (act === 'cancel-note') {
        entry.querySelector('.note-area').classList.remove('open');
      } else if (act === 'delete-note') {
        delete state.notes[url];
        persist(); render();
      }
      return;
    }
    // Click anywhere else inside an entry: highlight + pan the map to that listing.
    // (Clicks on action buttons are handled above and return early so this won't fire.)
    const entry = e.target.closest('.entry');
    if (entry && entry.dataset.url) {
      setActive(entry.dataset.url, { pan: true });
    }
  });

  // Hover an entry → highlight its pin (no pan, no popup — that's reserved for click).
  document.addEventListener('mouseover', e => {
    const entry = e.target.closest('.entry');
    if (entry && entry.dataset.url) setActive(entry.dataset.url);
  });

  // ------- Initial paint + map mount ------------------------------------
  render();
  // Desktop: sticky right-rail map (#map-side). Mobile: inline map below the
  // list (#map-mobile). Whichever is visible wins; the other is display:none.
  const sidePanel = document.getElementById('map-panel');
  if (sidePanel && getComputedStyle(sidePanel).display !== 'none') {
    mountMap('map-side');
  } else if (document.getElementById('map-mobile')) {
    mountMap('map-mobile');
  }
  setupTileSelects();
})();
"""


def write_html(path: str, listings: "list[Listing]") -> None:
    """Write a self-contained dashboard HTML. State persists in localStorage."""
    e = _html.escape
    date_str = datetime.now().date().isoformat()
    issue_num = datetime.now().toordinal() % 1000  # arbitrary running counter
    payload = _payload(listings)
    medians = _market_medians(listings)
    closest = min((l.distance_miles for l in listings if l.distance_miles is not None), default=None)
    cheapest = min((l.price for l in listings if l.price), default=None)
    curated = _read_curated()
    curated_block = ""
    if curated:
        items = "".join(
            f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(note or url)}</a></li>'
            for url, note in curated
        )
        curated_block = f'<h3>Hand-picked listings</h3><ul>{items}</ul>'

    other_items = "".join(
        f'<li><a href="{e(url)}" target="_blank" rel="noopener">{e(name)}</a> — {e(note)}</li>'
        for name, url, note in OTHER_SOURCES
    )

    fonts_link = (
        'https://fonts.googleapis.com/css2?'
        'family=Fraunces:opsz,wght@9..144,400..700&'
        'family=Newsreader:opsz,wght@6..72,400;6..72,500&'
        'family=Newsreader:opsz,ital,wght@6..72,1,400&'
        'family=JetBrains+Mono:wght@400;500;600&display=swap'
    )

    # Hoisted out of the f-string below because Python <3.12 rejects backslashes
    # inside f-string expressions. Escape `</` so the payload JSON can't terminate
    # the surrounding <script> tag if a listing description ever contains "</script>".
    payload_json = json.dumps(payload, separators=(',', ':')).replace('</', '<\\/')

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Brooklyn Apartment Inquirer · {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts_link}" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>{CSS}</style>
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
      <span class="stat-value">{len(payload)}</span>
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
    <button class="tab active" data-tab="inbox" role="tab">Inbox<span class="tab-count" id="inbox-count">{len(payload)}</span></button>
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
const MEDIANS = {json.dumps(medians)};
const CAMPUS = [40.6929, -73.9870];
{JS}
</script>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
