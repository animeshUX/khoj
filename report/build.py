"""Orchestrator: payload + template → HTML on disk."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .payload import build_payload
from .template import render

if TYPE_CHECKING:
    from scraper import Listing


def write_html(path: str, listings: "list[Listing]") -> None:
    payload = build_payload(listings)
    html = render(payload)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
