import pytest


@pytest.fixture
def sample_listing():
    return {
        "id": "test-1",
        "source": "submission",
        "url": "https://example.com/x",
        "title": "Test 1BR",
        "price": 1400,
        "beds": 1,
        "lat": 40.6807, "lng": -73.9443,
        "address": "50 MacDonough St, Brooklyn, NY",
        "neighborhood": "Bedford-Stuyvesant",
        "posted_at": "2026-05-24",
        "enrichment": {
            "commute": {"total_min": 14, "walk_min": 3, "rail_min": 11,
                        "station": {"name": "Kingston-Throop", "lines": ["C"],
                                    "lat": 40.68, "lng": -73.94}},
            "noise":   {"count_12mo": 289, "top_category": "Loud Music/Party"},
            "crime":   {"total_12mo": 236, "felonies": 70, "misd": 134, "viol": 32},
            "food":    [{"name": "India House", "lat": 40.68, "lng": -73.94, "dist_mi": 0.32}],
            "grocery": [{"name": "Nouri Halal Meat", "lat": 40.68, "lng": -73.94,
                         "dist_mi": 0.46, "south_asian": True}],
        },
    }
