#!/usr/bin/env python3
"""Scrape Craigslist Brooklyn apartments and score them for an NYU Tandon student.

Run: `python scraper.py`  (see README for options)
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic

import enrich
from report import write_html
from submission import parse_clip

# 370 Jay St, Brooklyn, NY 11201 — NYU Tandon
CAMPUS_COORDS = (40.6929, -73.9870)
# Pre-filter on CL side: 5-mile radius from 370 Jay St (zip 11201) — covers most
# 30-min-commute neighborhoods accessible from the F/A/C/R lines that converge at
# Jay St-MetroTech. The 4-mile geodesic filter in passes_hard_filters() trims
# further, while still being permissive enough for student-budget options in
# further-out Brooklyn (Sunset Park, deeper Bushwick, parts of Crown Heights).
SEARCH_URL = (
    "https://newyork.craigslist.org/search/brk/apa"
    "?postal=11201&search_distance=5"
)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
REQUEST_DELAY_SEC = 1.5
HTTP_TIMEOUT = 25
SUBMISSIONS_TIMEOUT = 60   # Apps Script doGet has 30s cap; allow headroom + retry

MIN_PRICE = 800
MAX_PRICE = 1500
MAX_DISTANCE_MILES = 4.0   # rough proxy for ~30-min commute via F/A/C/R + walk
MAX_AGE_DAYS = 14
ALLOWED_BEDROOMS = {0, 1, 2}  # studio == 0
TARGET_LISTINGS = 200          # wider radius → more candidates to filter

# Scoring keyword groups: (compiled regex, points awarded once if matched)
KEYWORD_RULES = [
    (re.compile(r"\b(students?\s+welcome|nyu|student[- ]friendly|grad\s+student)\b", re.I), 15),
    (re.compile(r"\b(no\s*guarantor(\s+needed|\s+required)?|guarantor\s+(not\s+required|optional|flexible)|flexible\s+(lease|terms))\b", re.I), 10),
    (re.compile(r"\bfurnished\b", re.I), 5),
    (re.compile(r"\b(utilities\s+included|all\s+utilities|util\.?\s*incl)\b", re.I), 5),
    (re.compile(r"\b[FACR](?:\s*[/&,]\s*[FACR])*\s*(?:train|line|subway)\b", re.I), 5),
]
STRICT_NO_PETS = re.compile(r"strict[^.\n]{0,40}no\s*pets|no\s*pets[^.\n]{0,40}strict", re.I)

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
})


@dataclass
class Listing:
    url: str
    title: str
    price: int | None
    bedrooms: int | None
    neighborhood: str
    address: str
    lat: float | None
    lng: float | None
    posted_date: str   # ISO date, YYYY-MM-DD
    description: str
    distance_miles: float | None
    score: int = 0
    enrichment: dict | None = None
    source: str = "craigslist"


def fetch(url: str) -> str:
    """GET url with the configured delay and headers; raise on non-2xx."""
    time.sleep(REQUEST_DELAY_SEC)
    resp = session.get(url, timeout=HTTP_TIMEOUT)
    if resp.status_code == 403:
        raise RuntimeError(
            f"Craigslist returned 403 for {url}. They may be blocking this IP — try a different network."
        )
    resp.raise_for_status()
    return resp.text


def iter_search_items(max_listings: int):
    """Yield search-result summary dicts by parsing Craigslist's static SEO HTML list.

    Craigslist serves a `<li class="cl-static-search-result">` block on the search page
    that contains all results in static HTML. One fetch typically returns ~300 listings,
    so we rarely need pagination. The RSS endpoint is hard-blocked; this is the
    replacement.
    """
    start = 0
    yielded = 0
    sep = "&" if "?" in SEARCH_URL else "?"
    while yielded < max_listings:
        url = f"{SEARCH_URL}{sep}{urlencode({'s': start})}" if start else SEARCH_URL
        try:
            html = fetch(url)
        except (requests.RequestException, RuntimeError) as e:
            print(f"[warn] search page s={start} failed: {e}", file=sys.stderr)
            return
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all("li", class_="cl-static-search-result")
        if not items:
            return
        for item in items:
            yield item
            yielded += 1
            if yielded >= max_listings:
                return
        start += len(items)


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_summary(item) -> dict | None:
    """Extract url, title, and raw price from one static search-result <li>."""
    link = item.find("a", href=True)
    if not link:
        return None
    url = link["href"]
    title = _text(item.find("div", class_="title")) or item.get("title", "").strip()
    if not url or not title:
        return None
    price = None
    price_el = item.find("div", class_="price")
    if price_el:
        m = re.search(r"\$([\d,]+)", price_el.text)
        if m:
            price = int(m.group(1).replace(",", ""))
    return {"url": url, "title": title, "price": price, "posted": None}


def parse_detail(html: str, summary: dict) -> Listing | None:
    """Parse a Craigslist posting page into a Listing. Returns None if essential fields missing."""
    soup = BeautifulSoup(html, "html.parser")

    title = _text(soup.find("span", id="titletextonly")) or summary["title"]

    price = summary["price"]
    if price is None:
        price_el = soup.find("span", class_="price")
        if price_el:
            m = re.search(r"\$([\d,]+)", price_el.text)
            if m:
                price = int(m.group(1).replace(",", ""))

    # Craigslist switched <p class="attrgroup"> to <div class="attrgroup"> in 2024.
    attrs_text = " ".join(_text(b) for b in soup.find_all("div", class_="attrgroup")).lower()
    m = re.search(r"(\d+)\s*br", attrs_text)
    if m:
        bedrooms = int(m.group(1))
    elif "studio" in attrs_text or re.search(r"\bstudio\b", title, re.I):
        bedrooms = 0
    else:
        bedrooms = None

    # Neighborhood lives in the last child span of <span class="postingtitletext">, formatted "(Hood)"
    neighborhood = ""
    title_wrap = soup.find("span", class_="postingtitletext")
    if title_wrap:
        for sp in title_wrap.find_all("span", recursive=False):
            txt = sp.get_text(" ", strip=True)
            if txt.startswith("(") and txt.endswith(")"):
                neighborhood = txt.strip(" ()")
                break
    address = _text(soup.find("div", class_="mapaddress"))

    lat = lng = None
    mapbox = soup.find("div", id="map") or soup.find("div", class_="mapbox")
    if mapbox:
        try:
            lat = float(mapbox.get("data-latitude"))
            lng = float(mapbox.get("data-longitude"))
        except (TypeError, ValueError):
            pass

    posted = summary["posted"]
    if posted is None:
        t_el = soup.find("time")
        if t_el and t_el.get("datetime"):
            try:
                posted = datetime.fromisoformat(t_el["datetime"].replace("Z", "+00:00"))
            except ValueError:
                pass
    posted_date = posted.date().isoformat() if posted else ""

    description = ""
    body_el = soup.find("section", id="postingbody")
    if body_el:
        for noise in body_el.find_all("div", class_="print-information"):
            noise.decompose()
        description = re.sub(r"\s+", " ", body_el.get_text(" ", strip=True)).strip()
        description = re.sub(r"^QR Code Link to This Post\s*", "", description)

    distance = geodesic(CAMPUS_COORDS, (lat, lng)).miles if lat is not None and lng is not None else None

    return Listing(
        url=summary["url"], title=title, price=price, bedrooms=bedrooms,
        neighborhood=neighborhood, address=address, lat=lat, lng=lng,
        posted_date=posted_date, description=description, distance_miles=distance,
    )


def passes_hard_filters(l: Listing) -> bool:
    """Hard filters: price band, bedroom type, recency, distance."""
    if l.price is None or not (MIN_PRICE <= l.price <= MAX_PRICE):
        return False
    if l.bedrooms is None or l.bedrooms not in ALLOWED_BEDROOMS:
        return False
    if not l.posted_date:
        return False
    age_days = (datetime.now(timezone.utc).date() - datetime.fromisoformat(l.posted_date).date()).days
    if age_days > MAX_AGE_DAYS:
        return False
    if l.distance_miles is None or l.distance_miles > MAX_DISTANCE_MILES:
        return False
    return True


def score(l: Listing) -> int:
    """0–100 score; higher = better fit. See README for breakdown."""
    pts = 0
    # Distance: 40 pts at 0 mi, 0 at MAX_DISTANCE_MILES, linear in between
    pts += round(40 * max(0.0, 1 - (l.distance_miles or MAX_DISTANCE_MILES) / MAX_DISTANCE_MILES))
    # Price: 20 pts at MIN_PRICE, 0 at MAX_PRICE, linear
    if l.price is not None:
        pts += round(20 * max(0.0, 1 - (l.price - MIN_PRICE) / (MAX_PRICE - MIN_PRICE)))
    # Keyword bonuses (title + description)
    haystack = f"{l.title}\n{l.description}"
    for pattern, bonus in KEYWORD_RULES:
        if pattern.search(haystack):
            pts += bonus
    # Penalty: only if "no pets" appears alongside "strict"
    if STRICT_NO_PETS.search(haystack):
        pts -= 5
    return max(0, min(100, pts))


CSV_COLUMNS = ["score", "price", "bedrooms", "neighborhood", "distance_miles",
               "posted_date", "title", "url", "description"]


def write_csv(path: str, listings: list[Listing]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for l in listings:
            row = asdict(l)
            row["distance_miles"] = f"{l.distance_miles:.2f}" if l.distance_miles is not None else ""
            row["description"] = (l.description or "")[:200]
            w.writerow({k: row.get(k, "") for k in CSV_COLUMNS})


def diagnose() -> None:
    """Probe several Craigslist endpoints with different headers; print what works."""
    probes = [
        ("homepage", "https://newyork.craigslist.org/"),
        ("search HTML", "https://newyork.craigslist.org/search/brk/apa"),
        ("search RSS", "https://newyork.craigslist.org/search/brk/apa?format=rss&s=0"),
        ("about page", "https://www.craigslist.org/about/sites"),
    ]
    print("Probing Craigslist endpoints from this network ...\n")
    for label, url in probes:
        time.sleep(1.0)
        try:
            r = session.get(url, timeout=15, allow_redirects=False)
            note = ""
            if r.status_code == 403 and "blocked" in r.text.lower():
                note = "  (CL block page)"
            elif r.status_code in (301, 302):
                note = f"  → {r.headers.get('Location','?')[:60]}"
            print(f"  HTTP {r.status_code}  {label:<14}  {url}{note}")
        except Exception as e:
            print(f"  ERROR        {label:<14}  {url}  ({e})")
    print(
        "\nInterpretation:\n"
        "  - All 200: transient block earlier — re-run `python scraper.py --sanity-check`.\n"
        "  - Homepage 200 but search 403: Craigslist is blocking the search/RSS endpoints from your IP.\n"
        "  - Everything 403: your network is on a Craigslist blocklist (VPN, corporate Wi-Fi, CGNAT ISP).\n"
        "    → Try turning off any VPN, switch to mobile hotspot, or run from a different network."
    )


def _walk_jsonld(soup):
    """Yield every dict found inside any <script type='application/ld+json'> on the
    page — including those nested inside @graph or arrays. Real-estate sites
    (StreetEasy, AmberStudent, Apartments.com, …) publish detailed listings here."""
    import json as _j
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = _j.loads(script.string or "")
        except (_j.JSONDecodeError, TypeError, ValueError):
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                yield cur
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def _intish(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _extract_price(node):
    """Pull a price out of any schema.org node: direct `price`, Offer, AggregateOffer."""
    offers = node.get("offers")
    if isinstance(offers, dict):
        offers = [offers]
    if isinstance(offers, list):
        for o in offers:
            if not isinstance(o, dict):
                continue
            for k in ("price", "lowPrice"):
                p = _intish(o.get(k))
                if p:
                    return p
    return _intish(node.get("price"))


def _extract_geo(node):
    g = node.get("geo")
    if isinstance(g, dict):
        try:
            return float(g["latitude"]), float(g["longitude"])
        except (KeyError, TypeError, ValueError):
            pass
    return None, None


def _extract_address(node):
    a = node.get("address")
    if isinstance(a, dict):
        return (a.get("streetAddress") or "").strip(), (a.get("addressLocality") or "").strip()
    return "", ""


def _guess_bedrooms_from_text(title: str, description: str):
    """Last-resort bedroom inference. JSON-LD often omits it; titles say it."""
    txt = f"{title or ''}\n{description or ''}".lower()
    m = re.search(r'(\d+)[\s-]*(?:br\b|bed\b|bedroom\b)', txt)
    if m:
        n = _intish(m.group(1))
        if n is not None and 0 <= n <= 9:
            return n
    if re.search(r'\bstudio\b', txt):
        return 0
    return None


def _fetch_external_listing(url: str, seed: dict | None = None) -> dict:
    """Fetch a non-Craigslist URL and pull as much listing info as we can.

    Combines OpenGraph + schema.org JSON-LD (price, geo, address). Falls back
    to text inference for bedrooms when structured data omits it.

    `seed` may carry og_title/og_description pre-fetched by the Apps Script
    enrichment — used when the live fetch returns no metadata (datacenter-IP
    blocking) or fails entirely (StreetEasy/Cloudflare 403). When both fail,
    a slug-derived title keeps the row visible as a stub card."""
    seed = seed or {}
    title = description = ""
    price = None
    lat = lng = None
    address = ""
    neighborhood = ""

    try:
        time.sleep(REQUEST_DELAY_SEC)
        resp = session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def meta(name: str, attr: str = "property") -> str:
            el = soup.find("meta", attrs={attr: name})
            return (el.get("content") or "").strip() if el and el.get("content") else ""

        title = (meta("og:title")
                 or meta("twitter:title", attr="name")
                 or (soup.find("title").get_text(strip=True) if soup.find("title") else ""))
        description = meta("og:description") or meta("description", attr="name")

        for node in _walk_jsonld(soup):
            if price is None:
                price = _extract_price(node)
            if lat is None:
                lat, lng = _extract_geo(node)
            if not address:
                street, locality = _extract_address(node)
                if street or locality:
                    address = street
                    neighborhood = locality.title() if locality else neighborhood
    except (requests.RequestException, RuntimeError) as e:
        print(f"[external fail] {url}: {e}", file=sys.stderr)

    # Layered fallbacks: live fetch → Apps Script seed → URL slug.
    if not title:
        title = seed.get("og_title") or _title_from_slug(url)
    if not description:
        description = seed.get("og_description", "")

    return {
        "title": title,
        "description": description,
        "price": price,
        "bedrooms": _guess_bedrooms_from_text(title, description),
        "lat": lat,
        "lng": lng,
        "neighborhood": neighborhood,
        "address": address,
    }


def _read_submissions_csv(path: str) -> list[dict]:
    """Read rows from a Google-Sheets-style intake CSV (Timestamp, URL, Submitted by, Note).

    `path` may be:
      - a local file path (e.g. `submissions.csv` in the repo), or
      - an http(s) URL — typically a Google Apps Script web-app endpoint that
        returns the sheet contents as CSV. Authentication, if any, lives in the
        URL itself (e.g. `?key=...`).

    If the Apps Script enrichment is deployed, the CSV may also contain
    `og_title` / `og_description` columns — pre-fetched from Google's IPs so
    sites that strip metadata for datacenter IPs (looking at you, AmberStudent)
    still surface usefully. Columns are forward-compatible: missing = "".

    Rows whose URL cell isn't an http(s) URL are skipped — submitters sometimes
    paste the page title from the browser tab instead of the link."""
    if path.startswith(("http://", "https://")):
        try:
            resp = session.get(path, timeout=SUBMISSIONS_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            lines = resp.text.splitlines()
        except (requests.RequestException, RuntimeError) as e:
            print(f"[warn] could not fetch submissions URL: {e}", file=sys.stderr)
            return []
        reader = csv.DictReader(lines)
    elif os.path.exists(path):
        reader = csv.DictReader(open(path, encoding="utf-8", newline=""))
    else:
        return []

    rows = []
    for row in reader:
        cell = (row.get("URL") or "").strip()
        if not cell:
            continue
        if not (cell.startswith("http://") or cell.startswith("https://")):
            print(f"[skip submission] not a URL: {cell[:60]!r}", file=sys.stderr)
            continue
        rows.append({
            "url": cell,
            "og_title": (row.get("og_title") or "").strip(),
            "og_description": (row.get("og_description") or "").strip(),
        })
    return rows


def _title_from_slug(url: str) -> str:
    """Last-resort title for a URL whose page returned no OpenGraph/JSON-LD.

    Picks the path segment with the most letters, drops trailing numeric IDs
    that sites tack on (e.g. `bernard-brooklyn-home-brooklyn-2207181201880`),
    title-cases the rest. Better than dropping the row entirely."""
    path = urlparse(url).path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    if not segments:
        return ""
    best = max(segments, key=lambda s: sum(1 for c in s if c.isalpha()))
    parts = best.split("-")
    while parts and parts[-1].isdigit():
        parts.pop()
    return " ".join(parts).title()


def print_top(listings: list[Listing], n: int = 10) -> None:
    print(f"\nTop {min(n, len(listings))} of {len(listings)} listings\n" + "-" * 72)
    for l in listings[:n]:
        bed = "Studio" if l.bedrooms == 0 else f"{l.bedrooms}BR"
        dist = f"{l.distance_miles:.2f}mi" if l.distance_miles is not None else "?"
        print(f"[{l.score:3d}] ${l.price}  {bed:6s} {dist:6s} {l.neighborhood[:24]:24s} {l.posted_date}")
        print(f"      {l.title[:90]}")
        print(f"      {l.url}\n")


def main():
    ap = argparse.ArgumentParser(description="Scrape & score Craigslist Brooklyn apartments near NYU Tandon.")
    ap.add_argument("--max-listings", type=int, default=TARGET_LISTINGS,
                    help=f"Max listings to fetch from search (default {TARGET_LISTINGS}).")
    ap.add_argument("--out", default=None, help="Output path stem (default apartments_YYYY-MM-DD); .csv and .html are written.")
    ap.add_argument("--sanity-check", action="store_true",
                    help="Fetch the first search page and exit — verifies network/IP isn't blocked.")
    ap.add_argument("--diagnose", action="store_true",
                    help="Probe multiple Craigslist endpoints to identify what's blocked. Run this when --sanity-check fails.")
    ap.add_argument("--pages-mode", action="store_true",
                    help="Write outputs into docs/ (latest + dated archives) for GitHub Pages hosting.")
    ap.add_argument("--submissions", default="submissions.csv",
                    help="Path or URL to a CSV (Timestamp, URL, Submitted by, Note) of family-submitted "
                         "listings. Default: submissions.csv. Override with env var KHOJ_SUBMISSIONS_URL.")
    args = ap.parse_args()

    # Env var beats the CLI default so the workflow can point at the live Google Sheet
    # without committing the URL to the repo.
    submissions_path = os.environ.get("KHOJ_SUBMISSIONS_URL") or args.submissions

    if args.sanity_check:
        try:
            html = fetch(SEARCH_URL)
            items = BeautifulSoup(html, "html.parser").find_all("li", class_="cl-static-search-result")
            print(f"OK: search returned {len(items)} items from first page.")
        except Exception as e:
            print(f"FAIL: {e}", file=sys.stderr)
            print("→ Run `python scraper.py --diagnose` to find out which endpoints work.", file=sys.stderr)
            sys.exit(1)
        return

    if args.diagnose:
        diagnose()
        return

    print(f"Scraping up to {args.max_listings} listings from {SEARCH_URL} ...")
    results: list[Listing] = []
    seen_urls: set[str] = set()
    for item in iter_search_items(args.max_listings):
        summary = parse_summary(item)
        if not summary or summary["url"] in seen_urls:
            continue
        seen_urls.add(summary["url"])
        try:
            html = fetch(summary["url"])
        except (requests.RequestException, RuntimeError) as e:
            print(f"[skip] {summary['url']}: {e}", file=sys.stderr)
            continue
        listing = parse_detail(html, summary)
        if listing is None:
            continue
        if not passes_hard_filters(listing):
            continue
        listing.score = score(listing)
        if listing.lat is not None and listing.lng is not None:
            listing.enrichment = enrich.enrich_address(listing.lat, listing.lng)
        results.append(listing)

    # Family-submitted URLs (submissions.csv intake from a Google Sheet via Apps Script).
    # These bypass the hard filters — if someone took the time to submit it, surface it
    # regardless of price/distance. Craigslist URLs get the full parse+score pipeline;
    # everything else falls back to OpenGraph metadata (live fetch → Apps Script seed →
    # URL slug) so non-Craigslist submissions always surface, even when the source site
    # strips metadata or returns 403 to the CI runner's datacenter IP.
    extra_items = _read_submissions_csv(submissions_path)
    n_extra_new = n_extra_dup = 0
    for item in extra_items:
        url = item["url"]
        if url in seen_urls:
            n_extra_dup += 1
            continue
        seen_urls.add(url)
        if "craigslist.org" in url:
            try:
                html = fetch(url)
            except (requests.RequestException, RuntimeError) as e:
                print(f"[skip extra] {url}: {e}", file=sys.stderr)
                continue
            listing = parse_detail(html, {"url": url, "title": "", "price": None, "posted": None})
            if listing is None:
                print(f"[skip extra] {url}: could not parse", file=sys.stderr)
                continue
            listing.source = "submission"
            listing.score = score(listing)
            if listing.lat is not None and listing.lng is not None:
                listing.enrichment = enrich.enrich_address(listing.lat, listing.lng)
        else:
            info = _fetch_external_listing(url, seed=item)
            # Title is now always non-empty (slug fallback ensures it) — skip only if
            # the URL itself is so degenerate we can't even slug it.
            if not info.get("title"):
                print(f"[skip external] {url}: unusable URL", file=sys.stderr)
                continue
            lat, lng = info.get("lat"), info.get("lng")
            dist = (geodesic(CAMPUS_COORDS, (lat, lng)).miles
                    if lat is not None and lng is not None else None)
            listing = Listing(
                url=url,
                title=info["title"],
                price=info.get("price"),
                bedrooms=info.get("bedrooms"),
                neighborhood=info.get("neighborhood", "") or "",
                address=info.get("address", "") or "",
                lat=lat, lng=lng,
                posted_date=datetime.now().date().isoformat(),  # submission date — we don't know original
                description=info.get("description", "") or "",
                distance_miles=dist,
                score=0,  # external entries don't get a fit score
                enrichment=(enrich.enrich_address(lat, lng) if lat is not None and lng is not None else None),
                source="submission",
            )
        results.append(listing)
        n_extra_new += 1
    if extra_items:
        print(f"Submitted URLs: {n_extra_new} added, {n_extra_dup} already in scrape results")

    # Web Clipper markdown drops (submissions/*.md). Same idea as the CSV intake
    # but with parsed-from-markdown metadata + a Nominatim geocode, so the report
    # can place them on the map even when the source site (StreetEasy, Amber)
    # would never let us scrape that data.
    # README.md is intake docs, not a clip. Exclude by name; everything else
    # in submissions/*.md is treated as a Web Clipper drop.
    clip_paths = sorted(p for p in glob.glob("submissions/*.md")
                        if os.path.basename(p) != "README.md")
    n_clip_new = n_clip_skip = 0
    for clip_path in clip_paths:
        info = parse_clip(clip_path)
        url = info.get("url") or f"file://{clip_path}"
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if not info.get("title"):
            print(f"[skip clip] {clip_path}: no title in frontmatter", file=sys.stderr)
            n_clip_skip += 1
            continue
        lat = lng = None
        neighborhood = ""
        if info["address"]:
            geo = enrich.geocode(info["address"])
            if geo:
                lat, lng = geo["lat"], geo["lng"]
                neighborhood = geo.get("neighborhood", "")
        dist = (geodesic(CAMPUS_COORDS, (lat, lng)).miles
                if lat is not None and lng is not None else None)
        listing = Listing(
            url=url,
            title=info["title"],
            price=info.get("price"),
            bedrooms=info.get("bedrooms"),
            neighborhood=neighborhood,
            address=info["address"],
            lat=lat, lng=lng,
            posted_date=datetime.now().date().isoformat(),
            description=info.get("description", "") or "",
            distance_miles=dist,
            score=0,
            enrichment=(enrich.enrich_address(lat, lng) if lat is not None and lng is not None else None),
            source="submission",
        )
        results.append(listing)
        n_clip_new += 1
    if clip_paths:
        print(f"Web Clipper drops: {n_clip_new} added"
              + (f", {n_clip_skip} skipped" if n_clip_skip else ""))

    results.sort(key=lambda l: l.score, reverse=True)

    if args.pages_mode:
        os.makedirs("docs", exist_ok=True)
        date = datetime.now().date().isoformat()
        # Latest (fixed name, what GitHub Pages serves) + dated archive
        write_html("docs/index.html", results)
        write_csv("docs/apartments_latest.csv", results)
        write_html(f"docs/apartments_{date}.html", results)
        write_csv(f"docs/apartments_{date}.csv", results)
        print(f"\nWrote {len(results)} listings to docs/index.html (+ dated archive for {date})")
    else:
        stem = args.out or f"apartments_{datetime.now().date().isoformat()}"
        if stem.endswith(".csv"):
            stem = stem[:-4]
        csv_path, html_path = f"{stem}.csv", f"{stem}.html"
        write_csv(csv_path, results)
        write_html(html_path, results)
        print(f"\nWrote {len(results)} listings to {csv_path} and {html_path}")
        print(f"Tip: open {html_path} in a browser, or share it with anyone — it's self-contained.")

    print_top(results, 10)


if __name__ == "__main__":
    main()
