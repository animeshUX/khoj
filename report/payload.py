"""Build the dict that becomes the inline window.KHOJ payload.

Phase 1 keeps the legacy shape: a flat list under `listings`, plus market
`medians` (used by the JS to flag price anomalies). Later phases enrich this
toward the contract in docs/superpowers/specs/2026-05-25-leaflet-explorer-design.md §3.
"""
from __future__ import annotations

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
    host = (urlparse(url).hostname or "").lower()
    if not host or "craigslist.org" in host:
        return ""
    return host.removeprefix("www.")


def listings_payload(listings):
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
            "source": source,
        })
    return out


def market_medians(listings):
    by_bed = {}
    for l in listings:
        if l.price and l.bedrooms is not None:
            by_bed.setdefault(l.bedrooms, []).append(l.price)
    return {str(k): int(statistics.median(v)) for k, v in by_bed.items() if v}


def read_curated(path: str = "manual_links.txt"):
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


def build_payload(listings):
    """Return the data the template embeds: listings + per-bedroom medians + meta."""
    return {
        "listings": listings_payload(listings),
        "medians": market_medians(listings),
        "curated": read_curated(),
        "other_sources": OTHER_SOURCES,
    }
