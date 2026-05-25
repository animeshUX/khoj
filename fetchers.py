"""Fetch a single listing URL → Listing dataclass.

Craigslist URLs go through the full scraper pipeline (price, bedrooms, lat/lng,
distance, score). Everything else falls back to OpenGraph meta tags, which give
us title + image + sometimes description; price/bedrooms stay None and the
listing carries a score of 0."""
from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scraper import Listing, parse_detail, score, session as scraper_session, HTTP_TIMEOUT

# Re-use the scraper's headers but without the polite bulk-scrape delay
_session = requests.Session()
_session.headers.update(dict(scraper_session.headers))


def _fetch(url: str) -> str:
    r = _session.get(url, timeout=HTTP_TIMEOUT)
    if r.status_code == 403:
        raise RuntimeError(f"403 blocked by {urlparse(url).netloc}")
    r.raise_for_status()
    return r.text


def is_craigslist(url: str) -> bool:
    return "craigslist.org" in urlparse(url).netloc


def fetch_from_url(url: str) -> tuple[Listing, str]:
    """Return (Listing, source_label). Listing fields we can't extract stay None/empty."""
    if is_craigslist(url):
        html = _fetch(url)
        summary = {"url": url, "title": "", "price": None, "posted": None}
        listing = parse_detail(html, summary)
        if listing is None:
            raise RuntimeError("Could not parse the Craigslist page (layout may have changed).")
        listing.score = score(listing)
        return listing, "craigslist"
    return _from_opengraph(_fetch(url), url), "opengraph"


def _from_opengraph(html: str, url: str) -> Listing:
    soup = BeautifulSoup(html, "html.parser")

    def og(name: str) -> str | None:
        el = soup.find("meta", property=f"og:{name}")
        return el["content"].strip() if el and el.get("content") else None

    title = og("title") or (soup.find("title").text.strip() if soup.find("title") else "") or url
    description = og("description") or ""
    return Listing(
        url=url, title=title, price=None, bedrooms=None,
        neighborhood="", address="", lat=None, lng=None,
        posted_date="", description=description, distance_miles=None, score=0,
    )
