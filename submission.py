"""Parse Obsidian Web Clipper markdown drops in submissions/*.md.

One function: `parse_clip(path) -> dict` returns the same shape as
`_fetch_external_listing()` in scraper.py — title/url/address/price/
bedrooms/description — so the downstream wiring is identical.

The regexes were validated end-to-end in tools/enrich_dryrun.py against three
real Web Clipper outputs (Bernard/Amber, Kingsland/PadMapper, Rogers Ave/
StreetEasy). Don't tune them speculatively; iterate on a clip that fails.
"""
from __future__ import annotations

import re
from pathlib import Path

# House number + Title-Case street name + street type.
#
# Constraints baked in (each fixes a real false-positive seen in the wild):
# - `[ \t]+` not `\s+` — addresses are on one line; no jumping across newlines
#   (Crown 1162 clip used to match "11216\nCrown 1162 ... St").
# - First street-name word allows leading digit so "93rd Street" matches.
# - Subsequent words require capital first letter — rules out body prose like
#   "1 room studio apartment" (lowercase "room studio" can't be a street name).
# - `\b` after street type — prevents `St` matching the `St`-prefix of `Studio`.
# - Max 4 words in street name — additional guardrail against runaway matches.
# - IGNORECASE applied inline to the street-type + unit alternations only, so
#   the Title-Case discipline on the street name itself is preserved.
_ADDR_RE = re.compile(
    r"(\d+,?[ \t]+"
    r"[A-Z0-9][\w'.-]*"
    r"(?:[ \t]+[A-Z][\w'.-]*){0,3}"
    r"[ \t]+"
    r"(?i:St|Street|Ave|Avenue|Pl|Place|Rd|Road|Blvd|Boulevard|"
    r"Dr|Drive|Ct|Court|Pkwy|Parkway|Ln|Lane|Way|Plaza|Sq|Square|Hwy|Highway)"
    r"\b\.?)"
    r"(?:[ \t]+(?i:#\w+|Apt\.?[ \t]+\w+|Unit[ \t]+\w+|Suite[ \t]+\w+))?"
)
# Sanity bounds reject referral bonuses ("$50 off") and obvious typos.
_PRICE_RE = re.compile(r"\$(\d[\d,]{2,})\s*(?:/(?:mo|month|m\b))?", re.I)
_BEDS_RE = re.compile(r"(\d+|studio|one|two|three)[\s-]*(?:bed(?:room)?|br)\b", re.I)

_WORD_TO_BEDS = {"studio": 0, "one": 1, "two": 2, "three": 3}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Tolerant of missing or malformed YAML
    since Web Clipper occasionally inlines a stray field that breaks strict
    parsers — we only need a handful of scalar keys."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5:]
    fm = {}
    for line in fm_block.splitlines():
        m = re.match(r"^(\w+):\s*\"?(.*?)\"?\s*$", line)
        if m and not line.startswith(" "):
            fm[m.group(1)] = m.group(2)
    return fm, body


def parse_clip(path: str | Path) -> dict:
    """Extract listing metadata from a Web Clipper .md file.

    Returns the same keys as scraper._fetch_external_listing — url, title,
    description, price, bedrooms, address — so the caller can hand it
    straight to Listing(). Address may be empty if no street pattern was
    found in title/description/first-8000-chars; the geocoder skips that case.
    """
    text = Path(path).read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    title = fm.get("title", "")
    url = fm.get("source", "")
    description = fm.get("description", "")
    haystack = "\n".join([title, description, body[:8000]])

    address = ""
    m = _ADDR_RE.search(haystack)
    if m:
        address = m.group(1).strip()

    price = None
    m = _PRICE_RE.search(haystack)
    if m:
        v = int(m.group(1).replace(",", ""))
        if 400 <= v <= 20000:
            price = v

    bedrooms = None
    m = _BEDS_RE.search(haystack)
    if m:
        raw = m.group(1).lower()
        bedrooms = _WORD_TO_BEDS.get(raw)
        if bedrooms is None and raw.isdigit():
            bedrooms = int(raw)

    return {
        "url": url,
        "title": title,
        "description": description,
        "address": address,
        "price": price,
        "bedrooms": bedrooms,
    }
