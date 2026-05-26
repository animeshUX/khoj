from score import compute_score

def test_perfect_listing_scores_near_one(sample_listing):
    l = {**sample_listing}
    l["enrichment"] = {**l["enrichment"]}
    l["enrichment"]["commute"] = {**l["enrichment"]["commute"], "total_min": 10}
    l["enrichment"]["crime"]   = {**l["enrichment"]["crime"], "felonies": 10, "total_12mo": 40}
    l["price"] = 1100
    assert compute_score(l) > 0.85

def test_bad_commute_drops_score(sample_listing):
    l = {**sample_listing}
    l["enrichment"] = {**l["enrichment"]}
    l["enrichment"]["commute"] = {**l["enrichment"]["commute"], "total_min": 60}
    assert compute_score(l) < compute_score(sample_listing)

def test_missing_enrichment_does_not_crash(sample_listing):
    l = {**sample_listing, "enrichment": {}}
    s = compute_score(l)
    assert 0.0 <= s <= 1.0

def test_returns_in_unit_interval(sample_listing):
    s = compute_score(sample_listing)
    assert 0.0 <= s <= 1.0
