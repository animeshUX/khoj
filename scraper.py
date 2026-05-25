#!/usr/bin/env python3
"""Scrape Craigslist Brooklyn apartments and score them for an NYU Tandon student.

Run: `python scraper.py`  (see README for options)
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic

from report import write_html

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


def _read_manual_urls(path: str) -> list[str]:
    """Read URLs from a text file (one per line, blank/# comment lines ignored). Missing file = empty list."""
    if not os.path.exists(path):
        return []
    urls = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Allow "URL | optional note" — we just take the URL for now
        urls.append(line.split("|", 1)[0].strip())
    return urls


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
    ap.add_argument("--manual-urls", default="manual_urls.txt",
                    help="Path to a file of extra URLs to include (one per line, # comments allowed). Default: manual_urls.txt")
    args = ap.parse_args()

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
        results.append(listing)

    # Manually-submitted URLs (e.g., from aunt/uncle texting Animesh a link). These bypass
    # the hard filters — if someone took the time to submit it, surface it regardless of
    # price/distance. Score still applies so it ranks alongside scraped listings.
    manual_urls = _read_manual_urls(args.manual_urls)
    n_manual_new = n_manual_dup = 0
    for url in manual_urls:
        if url in seen_urls:
            n_manual_dup += 1
            continue
        seen_urls.add(url)
        try:
            html = fetch(url)
        except (requests.RequestException, RuntimeError) as e:
            print(f"[skip manual] {url}: {e}", file=sys.stderr)
            continue
        listing = parse_detail(html, {"url": url, "title": "", "price": None, "posted": None})
        if listing is None:
            print(f"[skip manual] {url}: could not parse", file=sys.stderr)
            continue
        listing.score = score(listing)
        results.append(listing)
        n_manual_new += 1
    if manual_urls:
        print(f"Manual URLs: {n_manual_new} added, {n_manual_dup} already in scrape results ({args.manual_urls})")

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
