"""HTML report renderer — turns a list of Listings into a self-contained .html file
that anyone can open in a browser without installing anything."""
from __future__ import annotations

import html as _html
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scraper import Listing

HTML_STYLES = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       color: #1a1a1a; background: #fafaf8; }
header { padding: 40px 24px 24px; max-width: 1100px; margin: 0 auto; border-bottom: 1px solid #e5e3dd; }
header h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: -0.01em; }
header .meta { margin: 0; color: #6b6b6b; font-size: 14px; }
main { max-width: 1100px; margin: 0 auto; padding: 24px; display: grid;
       grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.card { background: #fff; border: 1px solid #e5e3dd; border-radius: 6px; padding: 18px 20px;
        display: flex; flex-direction: column; gap: 10px; }
.card .row1 { display: flex; align-items: baseline; gap: 12px; }
.score { font-weight: 600; font-size: 13px; padding: 4px 10px; border-radius: 99px; letter-spacing: 0.02em; }
.score.high { background: #e7f3eb; color: #155724; }
.score.mid  { background: #fff4d6; color: #7a5400; }
.score.low  { background: #efeeea; color: #555; }
.price { font-size: 22px; font-weight: 600; }
.bed { color: #6b6b6b; font-size: 14px; font-weight: 400; margin-left: 4px; }
.card h2 { margin: 0; font-size: 16px; line-height: 1.4; font-weight: 500; }
.meta { color: #6b6b6b; font-size: 13px; margin: 0; }
.desc { color: #333; font-size: 14px; margin: 4px 0 0; }
.btn { align-self: flex-start; margin-top: 6px; display: inline-block; padding: 7px 14px;
       background: #111; color: #fff; text-decoration: none; border-radius: 4px; font-size: 13px; }
.btn:hover { background: #333; }
@media (max-width: 540px) { main { padding: 12px; } header { padding: 24px 16px 16px; } }
"""


def _tier(score: int) -> str:
    return "high" if score >= 80 else "mid" if score >= 60 else "low"


def write_html(path: str, listings: "list[Listing]") -> None:
    """Write a self-contained HTML report. No external assets — share the file as-is."""
    e = _html.escape
    date_str = datetime.now().date().isoformat()
    cards = []
    for l in listings:
        bed = "Studio" if l.bedrooms == 0 else f"{l.bedrooms}BR"
        dist = f"{l.distance_miles:.2f} mi" if l.distance_miles is not None else "?"
        desc = (l.description or "")[:280]
        if l.description and len(l.description) > 280:
            desc += "…"
        cards.append(
            f'<article class="card">'
            f'<div class="row1"><span class="score {_tier(l.score)}">Score {l.score}</span>'
            f'<span class="price">${l.price:,}<span class="bed">· {e(bed)}</span></span></div>'
            f'<h2>{e(l.title)}</h2>'
            f'<p class="meta">{e(l.neighborhood or "Brooklyn")} · {e(dist)} from NYU Tandon · posted {e(l.posted_date)}</p>'
            f'<p class="desc">{e(desc)}</p>'
            f'<a class="btn" href="{e(l.url)}" target="_blank" rel="noopener">View on Craigslist →</a>'
            f'</article>'
        )
    body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Apartments near NYU Tandon · {date_str}</title>'
        f'<style>{HTML_STYLES}</style></head><body>'
        '<header><h1>Apartments near NYU Tandon</h1>'
        f'<p class="meta">{len(listings)} listings · within 1.5 mi of 370 Jay St · '
        f'sorted by fit score · generated {date_str}</p></header>'
        f'<main>{"".join(cards) or "<p>No listings matched the filters.</p>"}</main>'
        '</body></html>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
