"""Pre-compute static GeoJSON overlays the scraper doesn't produce itself.

Currently: docs/data/crime.geojson — NYPD CompStat 12-mo aggregates by
precinct, joined to precinct polygons.

Other overlays (nta-noise, commute-zone, parks, subway-*) are produced by
other tools/ scripts or live as static reference data.

Cron: weekly is plenty — CompStat updates monthly.

Run:
    python tools/build_overlays.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from shapely.geometry import mapping, shape

ROOT = Path(__file__).parent.parent
OUT = ROOT / "docs" / "data" / "crime.geojson"

HEADERS = {"User-Agent": "Khoj-builder/0.1 (crime overlay fetch)"}

# NYPD Complaint Data (Historic) — 5uac-w243
NYPD_URL = "https://data.cityofnewyork.us/resource/5uac-w243.json"
# Police Precincts boundaries — y76i-bdw7 (DCP, GeoJSON export)
PRECINCTS_URL = "https://data.cityofnewyork.us/api/geospatial/y76i-bdw7?method=export&format=GeoJSON"

CATEGORIES = {"FELONY": "felonies", "MISDEMEANOR": "misd", "VIOLATION": "viol"}
SIMPLIFY_TOLERANCE = 0.0002  # ~22m at NYC latitude — same as build_neighborhood_data.py

# Flat-earth deg² → sq-mi conversion at NYC latitude (40.7°):
#   1° lat ≈ 69 mi, 1° lng ≈ 69 × cos(40.7°) ≈ 52.5 mi  →  1 deg² ≈ 3622.5 sq mi
# Same approximation the scraper mini-map uses; ~0.1% error at NYC scale.
SQMI_PER_DEG2 = 69.0 * 52.5


def fetch_complaints() -> Counter:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
    counts: Counter = Counter()
    offset = 0
    page = 0
    while True:
        page += 1
        params = {
            "$select": "addr_pct_cd,law_cat_cd",
            "$where": f"cmplnt_fr_dt > '{cutoff}'",
            "$limit": 50000,
            "$offset": offset,
        }
        print(f"  complaints page {page} (offset {offset:,}) …", end=" ", flush=True)
        r = requests.get(NYPD_URL, params=params, headers=HEADERS, timeout=120)
        r.raise_for_status()
        rows = r.json()
        print(f"{len(rows):,} rows")
        if not rows:
            break
        for row in rows:
            pct = row.get("addr_pct_cd")
            cat = (row.get("law_cat_cd") or "").upper()
            if pct and cat in CATEGORIES:
                counts[(pct, CATEGORIES[cat])] += 1
        if len(rows) < 50000:
            break
        offset += 50000
    return counts


def fetch_precincts() -> dict:
    print("  fetching precinct polygons …", end=" ", flush=True)
    r = requests.get(PRECINCTS_URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.json()
    print(f"{len(r.content) // 1024} KB, {len(data.get('features', []))} features")
    return data


def main() -> None:
    print("Fetching NYPD complaints (12 months) ...")
    counts = fetch_complaints()
    total = sum(counts.values())
    print(f"  total complaint-category rows: {total:,}")

    print("Fetching precinct polygons ...")
    geo = fetch_precincts()

    # Sanity-check the join — abort rather than write an empty file
    matched = 0
    for feat in geo["features"]:
        pct = str(feat["properties"].get("precinct") or "")
        if counts[(pct, "felonies")] or counts[(pct, "misd")] or counts[(pct, "viol")]:
            matched += 1

    if matched == 0:
        print(
            "ERROR: precinct join produced zero matches — "
            "property key mismatch or data issue. Aborting without writing output.",
            file=sys.stderr,
        )
        sys.exit(1)

    features_out = []
    for feat in geo["features"]:
        pct = str(feat["properties"].get("precinct") or "")
        fel = counts[(pct, "felonies")]
        mis = counts[(pct, "misd")]
        vio = counts[(pct, "viol")]
        raw_geom = shape(feat["geometry"])
        area_sqmi = round(raw_geom.area * SQMI_PER_DEG2, 3)
        try:
            geom = raw_geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        except Exception:
            geom = raw_geom
        features_out.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "precinct": pct,
                "felonies": fel,
                "misd": mis,
                "viol": vio,
                "total_12mo": fel + mis + vio,
                "area_sqmi": area_sqmi,
                "felonies_per_sqmi": round(fel / area_sqmi, 1) if area_sqmi else 0,
            },
        })
    geo["features"] = features_out

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(geo, separators=(",", ":")))
    size_kb = OUT.stat().st_size // 1024
    print(
        f"wrote {OUT} — {len(geo['features'])} precincts, "
        f"{total:,} complaints aggregated  ({size_kb} KB)"
    )


if __name__ == "__main__":
    main()
