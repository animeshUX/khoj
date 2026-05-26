"""Parse Obsidian Web Clipper markdown files + run the full enrichment chain.

Usage: .venv/bin/python /tmp/khoj_enrich.py "*.md"
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
import time
from datetime import datetime, timedelta

import requests

CAMPUS = (40.6929, -73.9870)
JAY_LINES = {"A", "C", "F", "R"}
STATIONS_PATH = "docs/data/subway-stations.geojson"
UA = "Khoj-enrich/0.1 (personal apartment research; github.com/animeshUX/khoj)"

# ----- Address / price / bed extraction patterns ------------------------------
# Match the street portion only — Nominatim is forgiving and we always append
# ", Brooklyn, NY". Stopping at the street type avoids the lazy-match issue
# where ", Kings County, 11216" gets partially gobbled as ", K".
ADDR_RE = re.compile(
    r"(\d+,?\s+[A-Z][\w' .-]+?\s+"
    r"(?:St|Street|Ave|Avenue|Pl|Place|Rd|Road|Blvd|Boulevard|"
    r"Dr|Drive|Ct|Court|Pkwy|Parkway|Ln|Lane|Way|Plaza|Sq|Square|Hwy|Highway)\.?)"
    r"(?:\s+(?:#\w+|Apt\.?\s+\w+|Unit\s+\w+|Suite\s+\w+))?",
    re.IGNORECASE,
)
PRICE_RE = re.compile(r"\$(\d[\d,]{2,})\s*(?:/(?:mo|month|m\b))?", re.I)
BEDS_RE = re.compile(r"(\d+|studio|one|two|three)[\s-]*(?:bed(?:room)?|br)\b", re.I)


def parse_frontmatter(md_text):
    if not md_text.startswith("---\n"):
        return {}, md_text
    end = md_text.find("\n---\n", 4)
    if end < 0:
        return {}, md_text
    fm_block = md_text[4:end]
    body = md_text[end + 5:]
    fm = {}
    current_key = None
    for line in fm_block.splitlines():
        m = re.match(r"^(\w+):\s*\"?(.*?)\"?\s*$", line)
        if m and not line.startswith(" "):
            current_key = m.group(1)
            fm[current_key] = m.group(2)
    return fm, body


def extract_listing(fm, body):
    title = fm.get("title", "")
    url = fm.get("source", "")
    desc = fm.get("description", "")
    haystack = "\n".join([title, desc, body[:8000]])

    addr = ""
    am = ADDR_RE.search(haystack)
    if am:
        addr = am.group(1).strip()

    price = None
    pm = PRICE_RE.search(haystack)
    if pm:
        v = int(pm.group(1).replace(",", ""))
        if 400 <= v <= 20000:  # sanity-filter (skip referral bonuses like "$50")
            price = v

    beds = None
    bm = BEDS_RE.search(haystack)
    if bm:
        raw = bm.group(1).lower()
        beds = {"studio": 0, "one": 1, "two": 2, "three": 3}.get(raw, None)
        if beds is None and raw.isdigit():
            beds = int(raw)

    return {
        "title": title,
        "url": url,
        "address": addr,
        "price": price,
        "bedrooms": beds,
        "description": desc,
    }


def hav_miles(a, b):
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def geocode(addr):
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": addr + ", Brooklyn, NY", "format": "json", "limit": 1, "addressdetails": 1},
        headers={"User-Agent": UA}, timeout=15,
    )
    r.raise_for_status()
    hits = r.json()
    if not hits:
        return None
    return {"lat": float(hits[0]["lat"]), "lng": float(hits[0]["lon"]),
            "canonical": hits[0]["display_name"]}


def nearest_jay_station(lat, lng):
    stations = json.load(open(STATIONS_PATH))["features"]
    best = None
    for f in stations:
        s_lng, s_lat = f["geometry"]["coordinates"]
        routes = set(f["properties"].get("daytime_routes", "").split())
        if not (routes & JAY_LINES):
            continue
        d = hav_miles((lat, lng), (s_lat, s_lng))
        if best is None or d < best[0]:
            best = (d, f["properties"]["stop_name"], routes & JAY_LINES, (s_lat, s_lng))
    return best


def commute(lat, lng):
    nx = nearest_jay_station(lat, lng)
    if not nx:
        return {"feasible": False}
    walk_mi, name, lines, coord = nx
    walk_min = walk_mi * 20  # 3mph walking
    rail_mi = hav_miles(coord, CAMPUS)
    rail_min = rail_mi * 3.5 + 2
    return {
        "feasible": True,
        "station": name, "lines": sorted(lines),
        "walk_ft": int(walk_mi * 5280), "walk_min": int(walk_min),
        "rail_min": int(rail_min),
        "total_min": int(walk_min + rail_min),
    }


def noise_count(lat, lng):
    since = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    r = requests.get(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
        params={
            "$where": (f"within_circle(location, {lat}, {lng}, 250) "
                       f"AND complaint_type like '%Noise%' "
                       f"AND created_date > '{since}'"),
            "$select": "complaint_type", "$limit": "5000",
        },
        headers={"User-Agent": UA}, timeout=30,
    )
    r.raise_for_status()
    return len(r.json())


def crime_breakdown(lat, lng):
    since = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    r = requests.get(
        "https://data.cityofnewyork.us/resource/5uac-w243.json",
        params={
            "$where": (f"within_circle(lat_lon, {lat}, {lng}, 400) "
                       f"AND cmplnt_fr_dt > '{since}'"),
            "$select": "ofns_desc,law_cat_cd", "$limit": "5000",
        },
        headers={"User-Agent": UA}, timeout=30,
    )
    r.raise_for_status()
    out = {"total": 0, "Felony": 0, "Misdemeanor": 0, "Violation": 0}
    for c in r.json():
        out["total"] += 1
        cat = (c.get("law_cat_cd") or "").title()
        if cat in out:
            out[cat] += 1
    return out


def overpass(query):
    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": UA},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["elements"]


def indian_restaurants(lat, lng):
    q = f"""[out:json][timeout:25];
(
  node["amenity"="restaurant"]["cuisine"~"indian",i](around:1609,{lat},{lng});
  node["amenity"="restaurant"]["name"~"indian|tandoor|curry|biryani|masala|dosa",i](around:1609,{lat},{lng});
);
out body;"""
    elems = overpass(q)
    seen = set()
    out = []
    for e in elems:
        name = e.get("tags", {}).get("name", "?")
        if name in seen: continue
        seen.add(name)
        out.append((hav_miles((lat, lng), (e["lat"], e["lon"])), name))
    return sorted(out)


def grocery(lat, lng):
    q = f"""[out:json][timeout:25];
(
  node["shop"~"supermarket|convenience|grocery"](around:805,{lat},{lng});
  node["shop"]["name"~"indian|halal|desi|patel|bangla|south asian",i](around:805,{lat},{lng});
);
out body;"""
    elems = overpass(q)
    out = []
    for e in elems:
        name = e.get("tags", {}).get("name", "?")
        is_south_asian = any(w in name.lower() for w in ("indian", "halal", "desi", "patel", "bangla", "south asian"))
        out.append((hav_miles((lat, lng), (e["lat"], e["lon"])), name, is_south_asian))
    return sorted(out)


def enrich_one(path):
    print(f"\n{'#' * 72}")
    print(f"# {path}")
    print(f"{'#' * 72}")
    fm, body = parse_frontmatter(open(path).read())
    listing = extract_listing(fm, body)
    print(f"\n  EXTRACTED FROM MARKDOWN")
    print(f"    title:    {listing['title'][:70]}")
    print(f"    url:      {listing['url'][:90]}")
    print(f"    address:  {listing['address'] or '(not found)'}")
    print(f"    price:    ${listing['price']}/mo" if listing["price"] else "    price:    (not found)")
    print(f"    bedrooms: {listing['bedrooms']}" if listing["bedrooms"] is not None else "    bedrooms: (not found)")

    if not listing["address"]:
        print("  ✗ no address — skipping enrichment")
        return

    geo = geocode(listing["address"])
    if not geo:
        print(f"  ✗ geocoder couldn't resolve '{listing['address']}'")
        return
    lat, lng = geo["lat"], geo["lng"]
    print(f"\n  GEOCODED")
    print(f"    {geo['canonical']}")
    print(f"    ({lat:.5f}, {lng:.5f})")

    c = commute(lat, lng)
    if c["feasible"]:
        print(f"\n  COMMUTE → 370 Jay St")
        print(f"    {c['walk_ft']} ft to {c['station']} ({'/'.join(c['lines'])} train)")
        print(f"    walk {c['walk_min']} min + rail {c['rail_min']} min ≈ {c['total_min']} min total")
    else:
        print(f"\n  COMMUTE: no direct A/C/F/R station nearby")

    print(f"\n  SAFETY (last 12 mo)")
    n = noise_count(lat, lng)
    cr = crime_breakdown(lat, lng)
    print(f"    311 noise (250m): {n} complaints")
    print(f"    NYPD (400m):      {cr['total']} (F:{cr['Felony']} M:{cr['Misdemeanor']} V:{cr['Violation']})")

    time.sleep(1)
    print(f"\n  INDIAN FOOD (1mi)")
    rests = indian_restaurants(lat, lng)
    if not rests:
        print(f"    (none)")
    for d, name in rests[:6]:
        print(f"    {d:.2f} mi  {name}")

    time.sleep(1)
    print(f"\n  GROCERY (0.5mi)")
    grs = grocery(lat, lng)
    south_asian = [(d, n) for d, n, sa in grs if sa]
    print(f"    {len(grs)} shops total, {len(south_asian)} south-asian/halal-named")
    if south_asian:
        for d, n in south_asian[:3]:
            print(f"    ★ {d:.2f} mi  {n}")
    for d, n, _ in grs[:5]:
        print(f"      {d:.2f} mi  {n}")


def main():
    paths = sorted(p for p in glob.glob("*.md") if p not in ("CLAUDE.md", "README.md", "session_handoff.md"))
    print(f"Found {len(paths)} Web Clipper markdown file(s):")
    for p in paths:
        print(f"  - {p}")
    for p in paths:
        try:
            enrich_one(p)
        except Exception as e:
            print(f"\n  ✗ enrichment failed for {p}: {e}")
        time.sleep(1.5)  # be polite to Nominatim / Overpass


if __name__ == "__main__":
    main()
