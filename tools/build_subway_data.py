"""One-off build script: fetch NYC subway lines + stations, simplify them,
and compute a static "30-min commute proxy" zone polygon around 370 Jay St.

Run once (or whenever you want to refresh from upstream NYC OpenData):

    python tools/build_subway_data.py

Outputs three GeoJSON files into docs/data/ which the report consumes at
render time. Heavy network + shapely work happens here, not at scrape time.

Requirements:  shapely
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union, transform

CAMPUS = (-73.9870, 40.6929)  # lon, lat — shapely Point order
RELEVANT_ROUTES = {"F", "A", "C", "R"}  # the lines that hit Jay St-MetroTech
STATION_BUFFER_M = 800       # ~10 min walk
CAMPUS_BUFFER_M = 1500       # ~18 min walk
MAX_STATION_DISTANCE_MI = 4  # prune obviously-too-far stations from the zone

# Data sources (NYC OpenData / NYS Open Data / ArcGIS FeatureServer)
LINES_URL = (
    "https://services6.arcgis.com/yG5s3afENB5iO9fj/arcgis/rest/services/"
    "Subway_view/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson"
)
STATIONS_URL = (
    "https://data.ny.gov/api/geospatial/39hk-dx4f"
    "?method=export&format=GeoJSON"
)
OUT_DIR = Path("docs/data")
HEADERS = {"User-Agent": "Khoj-builder/0.1 (one-off subway data fetch)"}

# Rough miles ↔ degrees conversion at NYC's latitude (40.69°)
MILES_PER_DEG_LAT = 69.0
MILES_PER_DEG_LNG = 52.5


def fetch(url, label):
    print(f"  fetching {label} …", end=" ", flush=True)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    print(f"{len(r.content) // 1024} KB")
    return r.json()


def miles_between(lon1, lat1, lon2, lat2):
    """Quick flat-earth distance, good enough for NYC."""
    dx = (lon2 - lon1) * MILES_PER_DEG_LNG
    dy = (lat2 - lat1) * MILES_PER_DEG_LAT
    return (dx * dx + dy * dy) ** 0.5


def simplify_lines(geo):
    """Drop unnecessary attrs and simplify each segment ~30m so the file ships small."""
    keep_props = ("LINE", "SUBWAY_LABEL", "ROUTE", "DIVISION", "RAIL_TYPE")
    out = []
    for f in geo["features"]:
        g = shape(f["geometry"]).simplify(0.00015, preserve_topology=False)
        if g.is_empty:
            continue
        props = {k: f["properties"].get(k) for k in keep_props if f["properties"].get(k) is not None}
        out.append({"type": "Feature", "properties": props, "geometry": mapping(g)})
    return {"type": "FeatureCollection", "features": out}


def slim_stations(geo):
    """Keep only fields we render: id, stop_name, daytime_routes, structure, line."""
    keep = ("station_id", "stop_name", "daytime_routes", "line", "structure", "borough")
    out = []
    for f in geo["features"]:
        p = f["properties"]
        out.append({
            "type": "Feature",
            "properties": {k: p.get(k) for k in keep},
            "geometry": f["geometry"],
        })
    return {"type": "FeatureCollection", "features": out}


def metres_to_degrees(metres, lat):
    """Convert metres to roughly equivalent (dlat, dlon) at given latitude."""
    import math
    dlat = metres / 111000
    dlon = metres / (111000 * math.cos(math.radians(lat)))
    return dlat, dlon


def buffer_lonlat(point_lonlat, metres):
    """Return a shapely polygon approximating a `metres`-radius circle around
    a lon/lat point. We work in degrees; near NYC the error is < 2%."""
    lon, lat = point_lonlat
    dlat, dlon = metres_to_degrees(metres, lat)
    # Use the average so the buffer is roughly circular in projected display
    radius_deg = (dlat + dlon) / 2
    return Point(lon, lat).buffer(radius_deg, quad_segs=20)


def build_commute_zone(stations_geo):
    """Union buffered campus + buffered F/A/C/R stations within 4mi of campus."""
    buffers = [buffer_lonlat(CAMPUS, CAMPUS_BUFFER_M)]
    n_used = 0
    for f in stations_geo["features"]:
        routes = (f["properties"].get("daytime_routes") or "").split()
        if not any(r in RELEVANT_ROUTES for r in routes):
            continue
        lon, lat = f["geometry"]["coordinates"]
        if miles_between(CAMPUS[0], CAMPUS[1], lon, lat) > MAX_STATION_DISTANCE_MI:
            continue
        buffers.append(buffer_lonlat((lon, lat), STATION_BUFFER_M))
        n_used += 1
    print(f"  isochrone: campus + {n_used} F/A/C/R stations within {MAX_STATION_DISTANCE_MI} mi")
    zone = unary_union(buffers)
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "label": "~30-min commute zone (proxy)",
                "stations_used": n_used,
                "station_buffer_m": STATION_BUFFER_M,
                "campus_buffer_m": CAMPUS_BUFFER_M,
            },
            "geometry": mapping(zone),
        }],
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching upstream data ...")
    lines_raw = fetch(LINES_URL, "subway track segments")
    stations_raw = fetch(STATIONS_URL, "subway stations")

    print("Processing ...")
    lines_slim = simplify_lines(lines_raw)
    stations_slim = slim_stations(stations_raw)
    commute_zone = build_commute_zone(stations_raw)

    for name, data in [
        ("subway-lines.geojson", lines_slim),
        ("subway-stations.geojson", stations_slim),
        ("commute-zone.geojson", commute_zone),
    ]:
        path = OUT_DIR / name
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(f"  wrote {path}  ({path.stat().st_size // 1024} KB, {len(data['features'])} feats)")


if __name__ == "__main__":
    main()
