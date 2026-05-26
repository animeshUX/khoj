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


_COMPONENTS = (
    ("commute", W_COMMUTE),
    ("safety",  W_SAFETY),
    ("sa",      W_SA),
    ("price",   W_PRICE),
)


def _component_scores(listing: dict) -> dict[str, float | None]:
    enr = listing.get("enrichment") or {}
    return {
        "commute": _commute_score(enr.get("commute")),
        "safety":  _safety_score(enr.get("crime")),
        "sa":      _sa_score(enr.get("food"), enr.get("grocery")),
        "price":   _price_score(listing.get("price")),
    }


def compute_score(listing: dict) -> float:
    parts = _component_scores(listing)
    active = [(w, parts[k]) for k, w in _COMPONENTS if parts[k] is not None]
    if not active: return 0.0
    total_w = sum(w for w, _ in active)
    return sum(w * s for w, s in active) / total_w


def score_breakdown(listing: dict) -> dict:
    """Per-component breakdown for the tooltip.

    Each present component reports its raw 0..1 score, its weight, and the
    contribution (weighted score / sum-of-active-weights × 100). Missing
    components are omitted — they don't penalize, they just drop out of the
    average, which is also why contributions don't always sum to the raw
    weights.
    """
    parts = _component_scores(listing)
    active = {k: parts[k] for k, _ in _COMPONENTS if parts[k] is not None}
    weights = {k: w for k, w in _COMPONENTS if k in active}
    total_w = sum(weights.values()) or 1.0
    components = {
        k: {
            "score":        round(active[k] * 100),
            "weight":       weights[k],
            "contribution": round(weights[k] * active[k] / total_w * 100, 1),
        }
        for k in active
    }
    return {
        "total":   round(compute_score(listing) * 100),
        "components": components,
    }
