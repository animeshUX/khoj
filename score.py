# score.py
"""Fit-score per listing (0..1). Higher = better fit.

Weighted blend of commute, safety, south-asian access, price. Missing
enrichment skips that weight rather than penalizing — a listing without
crime data isn't worse than one with low crime, it's just unknown.
"""
from __future__ import annotations

W_COMMUTE = 0.35
W_SAFETY  = 0.25
W_SA      = 0.20
W_PRICE   = 0.20

PRICE_FLOOR = 800
PRICE_CEIL  = 2000


def _commute_score(c: dict | None) -> float | None:
    if not c or c.get("total_min") is None: return None
    t = c["total_min"]
    if t <= 15: return 1.0
    if t >= 45: return 0.0
    return 1.0 - (t - 15) / 30.0


def _safety_score(c: dict | None) -> float | None:
    if not c: return None
    fel = c.get("felonies")
    if fel is None: return None
    if fel <= 20:  return 1.0
    if fel >= 200: return 0.0
    return 1.0 - (fel - 20) / 180.0


def _sa_score(food: list | None, grocery: list | None) -> float | None:
    if food is None and grocery is None: return None
    sa_grocery = sum(1 for g in (grocery or []) if g.get("south_asian"))
    food_close = sum(1 for f in (food or []) if (f.get("dist_mi") or 99) <= 1.0)
    if sa_grocery >= 1 and food_close >= 3: return 1.0
    if sa_grocery >= 1 or food_close >= 3:  return 0.7
    if food_close >= 1: return 0.4
    return 0.0


def _price_score(price: int | None) -> float | None:
    if price is None: return None
    if price <= PRICE_FLOOR: return 1.0
    if price >= PRICE_CEIL:  return 0.0
    return 1.0 - (price - PRICE_FLOOR) / (PRICE_CEIL - PRICE_FLOOR)


def compute_score(listing: dict) -> float:
    enr = listing.get("enrichment") or {}
    parts = [
        (W_COMMUTE, _commute_score(enr.get("commute"))),
        (W_SAFETY,  _safety_score(enr.get("crime"))),
        (W_SA,      _sa_score(enr.get("food"), enr.get("grocery"))),
        (W_PRICE,   _price_score(listing.get("price"))),
    ]
    active = [(w, s) for w, s in parts if s is not None]
    if not active: return 0.0
    total_w = sum(w for w, _ in active)
    return sum(w * s for w, s in active) / total_w
