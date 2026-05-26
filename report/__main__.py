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

from .payload import build_payload
from .template import render


# New format: window.KHOJ = {...};
_KHOJ_RX = re.compile(r'window\.KHOJ\s*=\s*(\{.*?\});\s*</script>', re.S)
# Legacy format: <script id="payload" type="application/json">...</script>
_LEGACY_PAYLOAD_RX = re.compile(
    r'<script id="payload" type="application/json">(.*?)</script>',
    re.S,
)


def _extract(html: str) -> dict:
    # Try new format first.
    m = _KHOJ_RX.search(html)
    if m:
        return json.loads(m.group(1).replace('<\\/', '</'))

    # Fall back to legacy format: rebuild payload from extracted listings.
    m = _LEGACY_PAYLOAD_RX.search(html)
    if not m:
        sys.exit("could not find inline payload in " + repr(html[:120]))
    listings = json.loads(m.group(1).replace('<\\/', '</'))
    # Legacy listings are already dicts; pass them through build_payload.
    # They use old field names (bedrooms, posted, etc.) — build_payload's shim handles them.
    return build_payload(listings)


def main():
    p = argparse.ArgumentParser(description="Re-render docs/index.html from its inline payload.")
    p.add_argument("--in",  dest="src", default="docs/index.html")
    p.add_argument("--out", dest="dst", default="docs/index.html")
    args = p.parse_args()

    html = Path(args.src).read_text(encoding="utf-8")
    payload = _extract(html)
    listings = payload.get("listings", [])
    Path(args.dst).write_text(render(payload), encoding="utf-8")
    print(f"re-rendered {len(listings)} listings → {args.dst}")


if __name__ == "__main__":
    main()
