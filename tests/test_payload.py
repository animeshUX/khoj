from report.payload import build_payload


def test_payload_top_level_keys():
    p = build_payload([])
    for k in ("generated_at", "campus", "listings", "filter_defaults", "tiles"):
        assert k in p


def test_listing_has_required_shape(sample_listing):
    p = build_payload([sample_listing])
    l = p["listings"][0]
    for k in ("id", "source", "url", "title", "price", "beds",
              "lat", "lng", "address", "neighborhood", "posted_at",
              "score", "enrichment"):
        assert k in l, f"missing key: {k}"


def test_score_attached_when_enriched(sample_listing):
    p = build_payload([sample_listing])
    assert isinstance(p["listings"][0]["score"], float)
    assert 0.0 <= p["listings"][0]["score"] <= 1.0


def test_listing_without_coords_included_in_payload():
    # Coord-less listings (e.g. un-geocodable submissions) must appear in the list
    # rail; map.js guards the pin creation with `if (l.lat == null) return`.
    bad = {"id": "x", "lat": None, "lng": None, "title": "no coords"}
    p = build_payload([bad])
    assert len(p["listings"]) == 1
    assert p["listings"][0]["lat"] is None
    assert p["listings"][0]["lng"] is None


def test_filter_defaults_match_spec():
    p = build_payload([])
    assert p["filter_defaults"]["max_price"] == 1500
    assert p["filter_defaults"]["max_commute"] == 30
    assert p["filter_defaults"]["hide_hidden"] is True
    assert p["filter_defaults"]["only_starred"] is False
