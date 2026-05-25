"""One-off build: fetch NTA polygons + 311 noise data + parks from NYC OpenData,
spatial-join the noise to NTAs, simplify everything, and write static GeoJSON
into docs/data/ so the map renders without runtime API calls.

Re-run any time to refresh:
    python tools/build_neighborhood_data.py

Outputs:
- docs/data/nta-noise.geojson — Neighborhood polygons + 90-day noise counts
- docs/data/parks.geojson      — Simplified park boundary polygons

Requirements: shapely
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import requests
from shapely.geometry import shape, mapping, Point
from shapely.strtree import STRtree

OUT_DIR = Path("docs/data")
HEADERS = {"User-Agent": "Khoj-builder/0.1 (neighborhood data fetch)"}
SIMPLIFY_TOLERANCE = 0.0002  # ~22m at NYC latitude

# Anything outside these boroughs is dropped (no signal for a Brooklyn rental decision)
KEEP_BOROUGHS = {"Brooklyn", "Manhattan", "Queens", "Bronx"}

NTA_URL = "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON"
PARKS_URL = "https://data.cityofnewyork.us/api/geospatial/enfh-gkve?method=export&format=GeoJSON"


def noise_url(since_date: str, limit: int = 50000) -> str:
    where = f"complaint_type like '%Noise%' AND created_date > '{since_date}'"
    return (
        "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
        f"?$where={requests.utils.quote(where)}"
        f"&$select=latitude,longitude,complaint_type"
        f"&$limit={limit}"
    )


def fetch_json(url, label):
    print(f"  fetching {label} …", end=" ", flush=True)
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    print(f"{len(r.content) // 1024} KB")
    return r.json()


def build_nta_with_noise(nta_raw, noise_rows):
    polys = []
    for f in nta_raw["features"]:
        p = f["properties"]
        if p.get("boroname") not in KEEP_BOROUGHS:
            continue
        g = shape(f["geometry"]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        if g.is_empty:
            continue
        polys.append({
            "name": p.get("ntaname") or "",
            "borough": p.get("boroname") or "",
            "nta_id": p.get("nta2020") or "",
            "shape_area_sqm": float(p.get("shape_area") or 0),
            "geom": g,
        })
    print(f"  NTAs kept (close-in boroughs): {len(polys)}")

    tree = STRtree([p["geom"] for p in polys])
    counts = [0] * len(polys)

    skipped = 0
    for row in noise_rows:
        lat = row.get("latitude"); lng = row.get("longitude")
        if not lat or not lng:
            skipped += 1; continue
        try:
            pt = Point(float(lng), float(lat))
        except (TypeError, ValueError):
            skipped += 1; continue
        for idx in tree.query(pt):
            if polys[idx]["geom"].contains(pt):
                counts[idx] += 1
                break
        else:
            skipped += 1
    print(f"  noise points assigned: {sum(counts)} / {len(noise_rows)}  (skipped {skipped})")

    out = []
    for p, n in zip(polys, counts):
        area_sqmi = p["shape_area_sqm"] / 2_589_988
        density = (n / area_sqmi) if area_sqmi > 0 else 0
        out.append({
            "type": "Feature",
            "geometry": mapping(p["geom"]),
            "properties": {
                "name": p["name"],
                "borough": p["borough"],
                "nta_id": p["nta_id"],
                "noise_90d": n,
                "noise_per_sqmi": round(density, 1),
            },
        })
    return {"type": "FeatureCollection", "features": out}


def build_parks(parks_raw):
    out = []
    for f in parks_raw["features"]:
        try:
            g = shape(f["geometry"]).simplify(SIMPLIFY_TOLERANCE * 1.5, preserve_topology=True)
        except Exception:
            continue
        if g.is_empty:
            continue
        acres = float(f["properties"].get("acres") or 0)
        if acres < 0.25:
            continue
        out.append({
            "type": "Feature",
            "geometry": mapping(g),
            "properties": {
                "name": f["properties"].get("signname") or f["properties"].get("location") or "",
                "acres": acres,
            },
        })
    print(f"  parks kept (≥ 0.25 acres): {len(out)}")
    return {"type": "FeatureCollection", "features": out}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    since = (_dt.datetime.utcnow() - _dt.timedelta(days=90)).strftime("%Y-%m-%dT00:00:00.000")
    print("Fetching upstream data ...")
    nta = fetch_json(NTA_URL, "NTAs")
    parks = fetch_json(PARKS_URL, "parks")
    noise = fetch_json(noise_url(since), "311 noise (90d, capped 50k)")

    print("Processing ...")
    nta_out = build_nta_with_noise(nta, noise)
    parks_out = build_parks(parks)

    for name, data in [
        ("nta-noise.geojson", nta_out),
        ("parks.geojson", parks_out),
    ]:
        path = OUT_DIR / name
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"  wrote {path}  ({path.stat().st_size // 1024} KB, {len(data['features'])} feats)")


if __name__ == "__main__":
    main()
