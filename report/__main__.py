"""CLI: re-render docs/index.html from the inline payload of the existing one.

Useful for iterating on the template/CSS/JS without re-running the scraper.
For a fresh scrape + render, use `python scraper.py --pages-mode`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .payload import OTHER_SOURCES, read_curated
from .template import render


_PAYLOAD_RX = re.compile(
    r'<script id="payload" type="application/json">(.*?)</script>',
    re.S,
)
_MEDIANS_RX = re.compile(r'window\.MEDIANS\s*=\s*(\{[^}]*\});')
# Back-compat: old reports used `const MEDIANS = {...}`.
_MEDIANS_LEGACY_RX = re.compile(r'const\s+MEDIANS\s*=\s*(\{[^}]*\});')


def _extract(html: str):
    m = _PAYLOAD_RX.search(html)
    if not m:
        sys.exit("could not find inline payload in " + repr(html[:120]))
    listings = json.loads(m.group(1).replace('<\\/', '</'))
    medians_match = _MEDIANS_RX.search(html) or _MEDIANS_LEGACY_RX.search(html)
    medians = json.loads(medians_match.group(1)) if medians_match else {}
    return listings, medians


def main():
    p = argparse.ArgumentParser(description="Re-render docs/index.html from its inline payload.")
    p.add_argument("--in",  dest="src", default="docs/index.html")
    p.add_argument("--out", dest="dst", default="docs/index.html")
    args = p.parse_args()

    html = Path(args.src).read_text(encoding="utf-8")
    listings, medians = _extract(html)
    payload = {
        "listings": listings,
        "medians": medians,
        "curated": read_curated(),
        "other_sources": OTHER_SOURCES,
    }
    Path(args.dst).write_text(render(payload), encoding="utf-8")
    print(f"re-rendered {len(listings)} listings → {args.dst}")


if __name__ == "__main__":
    main()
