"""Emit the window.KHOJ payload — the Section-3 data contract."""
from __future__ import annotations

import dataclasses
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


def _listing_dict(raw: object) -> dict | None:
    # Normalize dataclass instances to plain dicts.
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        raw = dataclasses.asdict(raw)
    if not isinstance(raw, dict):
        return None
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


def build_payload(listings: list) -> dict:
    out_listings = [d for d in (_listing_dict(l) for l in listings) if d is not None]
    return {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "campus":         CAMPUS,
        "tiles":          TILES,
        "filter_defaults": FILTER_DEFAULTS,
        "listings":       out_listings,
    }
