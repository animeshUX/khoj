"""Address enrichment: geocode + commute/safety/POI.

Each enrichment function is independent and side-effect-free apart from the
on-disk cache. All network calls use TIMEOUT; SODA and Overpass results are
cached weekly per ~111m grid cell (3-decimal-place rounding).

Data sources (all free, no keys):
- Nominatim (OSM) for geocoding
- docs/data/subway-stations.geojson (local, MTA-derived) for commute proxy
- NYC Open Data SODA for 311 noise + NYPD CompStat
- Overpass for Indian food + grocery POIs
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Campus: 370 Jay St, Brooklyn (NYU Tandon). Mirrored from scraper.CAMPUS_COORDS
# so this module can be imported without circular dependency.
CAMPUS = (40.6929, -73.9870)
JAY_LINES = {"A", "C", "F", "R"}

_ROOT = Path(__file__).parent
STATIONS_PATH = _ROOT / "docs" / "data" / "subway-stations.geojson"
CACHE_DIR = _ROOT / ".cache"
GEOCODE_CACHE_PATH = CACHE_DIR / "geocode.json"
ENRICH_CACHE_PATH  = CACHE_DIR / "enrich.json"

UA = "Khoj-enrich/0.1 (personal apartment research; github.com/animeshUX/khoj)"
TIMEOUT = 15


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _hav_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(h))


# Nominatim's `suburb` field returns "Brooklyn" (the borough) for every NYC
# address — useless as a neighborhood. The vernacular neighborhood lives in
# `neighbourhood` or `quarter`, but for some addresses (e.g. 99 Kingsland,
# 1273 Rogers) Nominatim instead returns "Brooklyn Community District 17"
# — an administrative region nobody calls their neighborhood. Filter those
# out and fall back to the borough.
_ADMIN_REGION_RE = re.compile(r"^brooklyn community district", re.I)


def _neighborhood_from(hit: dict) -> str:
    addr = hit.get("address", {}) or {}
    for key in ("neighbourhood", "quarter"):
        v = (addr.get(key) or "").strip()
        if v and not _ADMIN_REGION_RE.match(v):
            return v
    return addr.get("suburb") or addr.get("borough") or "Brooklyn"


def geocode(address: str) -> dict | None:
    """Resolve a Brooklyn street address to coords via Nominatim.

    Returns {lat, lng, canonical, neighborhood} or None if no hit. Cached on
    disk keyed by the raw address — addresses are short and stable enough that
    a hash adds nothing. Cache survives across runs so the daily cron doesn't
    re-hit Nominatim for the same submissions.
    """
    if not address:
        return None

    cache = _load_cache(GEOCODE_CACHE_PATH)
    if address in cache:
        return cache[address]

    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": address + ", Brooklyn, NY",
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": UA},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        hits = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[geocode fail] {address!r}: {e}")
        return None

    if not hits:
        cache[address] = None
        _save_cache(GEOCODE_CACHE_PATH, cache)
        return None

    hit = hits[0]
    result = {
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
        "canonical": hit.get("display_name", ""),
        "neighborhood": _neighborhood_from(hit),
    }
    cache[address] = result
    _save_cache(GEOCODE_CACHE_PATH, cache)
    return result


# -----------------------------------------------------------------------------
# Enrichment cache helpers
# -----------------------------------------------------------------------------

def _enrich_cache_key(lat: float, lng: float, kind: str) -> str:
    """Cache key: rounded coords (~111m precision) + weekly bucket + kind."""
    week = datetime.utcnow().strftime("%Y-W%U")
    return f"{round(lat, 3)},{round(lng, 3)}|{week}|{kind}"


def _get_cached(lat: float, lng: float, kind: str):
    cache = _load_cache(ENRICH_CACHE_PATH)
    key = _enrich_cache_key(lat, lng, kind)
    sentinel = object()
    val = cache.get(key, sentinel)
    if val is sentinel:
        return None, False      # (value, hit)
    return val, True


def _set_cached(lat: float, lng: float, kind: str, value) -> None:
    cache = _load_cache(ENRICH_CACHE_PATH)
    cache[_enrich_cache_key(lat, lng, kind)] = value
    _save_cache(ENRICH_CACHE_PATH, cache)


# -----------------------------------------------------------------------------
# Commute — local computation, no network call, no cache needed
# -----------------------------------------------------------------------------

def _nearest_jay_station(lat: float, lng: float):
    stations = json.loads(STATIONS_PATH.read_text())["features"]
    best = None
    for f in stations:
        s_lng, s_lat = f["geometry"]["coordinates"]
        routes = set(f["properties"].get("daytime_routes", "").split())
        if not (routes & JAY_LINES):
            continue
        d = _hav_miles((lat, lng), (s_lat, s_lng))
        if best is None or d < best[0]:
            best = (d, f["properties"]["stop_name"], routes & JAY_LINES, (s_lat, s_lng))
    return best


def commute(lat: float, lng: float) -> dict:
    """Walk to nearest A/C/F/R station + rail proxy to 370 Jay.

    Returns {total_min, walk_min, rail_min, station:{name, lines, lat, lng}}.
    Rail time is haversine × 3.5 min/mi + 2 min for board/dwell.
    """
    nx = _nearest_jay_station(lat, lng)
    if not nx:
        return {"feasible": False}
    walk_mi, name, lines, coord = nx
    walk_min = walk_mi * 20
    rail_mi = _hav_miles(coord, CAMPUS)
    rail_min = rail_mi * 3.5 + 2
    return {
        "feasible": True,
        "total_min": int(walk_min + rail_min),
        "walk_min":  int(walk_min),
        "rail_min":  int(rail_min),
        "station": {
            "name":  name,
            "lines": sorted(lines),
            "lat":   coord[0],
            "lng":   coord[1],
        },
    }


# -----------------------------------------------------------------------------
# Noise — NYC Open Data 311 SODA API
# -----------------------------------------------------------------------------

def noise(lat: float, lng: float) -> dict:
    """311 noise complaints within 250m, last 12 months.

    Returns {count_12mo, top_category}.
    """
    cached, hit = _get_cached(lat, lng, "noise")
    if hit:
        return cached

    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    r = requests.get(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
        params={
            "$where": (
                f"within_circle(location, {lat}, {lng}, 250) "
                f"AND complaint_type like '%Noise%' "
                f"AND created_date > '{since}'"
            ),
            "$select": "complaint_type",
            "$limit": "5000",
        },
        headers={"User-Agent": UA},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json()
    counts: dict[str, int] = {}
    for row in rows:
        ct = row.get("complaint_type", "Noise")
        counts[ct] = counts.get(ct, 0) + 1
    top = max(counts, key=counts.__getitem__) if counts else None
    result = {"count_12mo": len(rows), "top_category": top}
    _set_cached(lat, lng, "noise", result)
    return result


# -----------------------------------------------------------------------------
# Crime — NYPD CompStat SODA API
# -----------------------------------------------------------------------------

def crime(lat: float, lng: float) -> dict:
    """NYPD complaints within 400m, last 12 months.

    Returns {total_12mo, felonies, misd, viol}.
    """
    cached, hit = _get_cached(lat, lng, "crime")
    if hit:
        return cached

    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    r = requests.get(
        "https://data.cityofnewyork.us/resource/5uac-w243.json",
        params={
            "$where": (
                f"within_circle(lat_lon, {lat}, {lng}, 400) "
                f"AND cmplnt_fr_dt > '{since}'"
            ),
            "$select": "ofns_desc,law_cat_cd",
            "$limit": "5000",
        },
        headers={"User-Agent": UA},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    felonies = misd = viol = 0
    for c in r.json():
        cat = (c.get("law_cat_cd") or "").strip().lower()
        if cat == "felony":
            felonies += 1
        elif cat == "misdemeanor":
            misd += 1
        elif cat == "violation":
            viol += 1
    result = {
        "total_12mo": felonies + misd + viol,
        "felonies":   felonies,
        "misd":       misd,
        "viol":       viol,
    }
    _set_cached(lat, lng, "crime", result)
    return result


# -----------------------------------------------------------------------------
# Food + grocery — Overpass
# -----------------------------------------------------------------------------

def _overpass(query: str) -> list:
    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": UA},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["elements"]


def food(lat: float, lng: float) -> list:
    """Indian-food restaurants within 1mi.

    Returns [{name, lat, lng, dist_mi}, ...] sorted by dist_mi.
    """
    cached, hit = _get_cached(lat, lng, "food")
    if hit:
        return cached

    q = f"""[out:json][timeout:25];
(
  node["amenity"="restaurant"]["cuisine"~"indian",i](around:1609,{lat},{lng});
  node["amenity"="restaurant"]["name"~"indian|tandoor|curry|biryani|masala|dosa",i](around:1609,{lat},{lng});
);
out body;"""
    elems = _overpass(q)
    seen: set[str] = set()
    out = []
    for e in elems:
        name = (e.get("tags") or {}).get("name", "?")
        if name in seen:
            continue
        seen.add(name)
        e_lat, e_lng = e["lat"], e["lon"]
        out.append({
            "name":    name,
            "lat":     e_lat,
            "lng":     e_lng,
            "dist_mi": round(_hav_miles((lat, lng), (e_lat, e_lng)), 3),
        })
    result = sorted(out, key=lambda x: x["dist_mi"])
    _set_cached(lat, lng, "food", result)
    return result


def grocery(lat: float, lng: float) -> list:
    """Grocery / halal stores within 0.5mi (805m).

    Returns [{name, lat, lng, dist_mi, south_asian}, ...] closest 5, sorted by
    dist_mi. south_asian=True if the name matches indian/halal/desi/patel/bangla.
    """
    cached, hit = _get_cached(lat, lng, "grocery")
    if hit:
        return cached

    q = f"""[out:json][timeout:25];
(
  node["shop"~"supermarket|convenience|grocery"](around:805,{lat},{lng});
  node["shop"]["name"~"indian|halal|desi|patel|bangla|south asian",i](around:805,{lat},{lng});
);
out body;"""
    elems = _overpass(q)
    out = []
    for e in elems:
        name = (e.get("tags") or {}).get("name", "?")
        e_lat, e_lng = e["lat"], e["lon"]
        is_south_asian = any(
            w in name.lower()
            for w in ("indian", "halal", "desi", "patel", "bangla", "south asian")
        )
        out.append({
            "name":        name,
            "lat":         e_lat,
            "lng":         e_lng,
            "dist_mi":     round(_hav_miles((lat, lng), (e_lat, e_lng)), 3),
            "south_asian": is_south_asian,
        })
    result = sorted(out, key=lambda x: x["dist_mi"])[:5]
    _set_cached(lat, lng, "grocery", result)
    return result


# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------

def enrich_address(lat: float, lng: float) -> dict:
    """Return the full enrichment block for a (lat, lng).

    Each subfield is wrapped in try/except — failure returns None for that
    subfield rather than raising. The score module skips None subfields.
    """
    result: dict = {}
    for key, fn in (
        ("commute", commute),
        ("noise",   noise),
        ("crime",   crime),
        ("food",    food),
        ("grocery", grocery),
    ):
        try:
            result[key] = fn(lat, lng)
        except Exception as exc:
            print(f"[enrich:{key}] ({lat:.4f},{lng:.4f}) failed: {exc}", file=sys.stderr)
            result[key] = None
    return result
