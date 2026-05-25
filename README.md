# Khoj — NYU Tandon apartment finder

Scrapes Craigslist's Brooklyn apartments feed, drops listings outside a 1.5-mile radius of 370 Jay St (NYU Tandon), filters by price / bedroom / recency, and writes a scored CSV sorted best-fit first. Single-file script, no database, no API keys.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
# verify your network can reach Craigslist (cheap, single request)
python scraper.py --sanity-check

# full run — writes apartments_YYYY-MM-DD.csv and prints top 10
python scraper.py

# tune fetch volume (default 100)
python scraper.py --max-listings 60 --out my_listings.csv
```

Expect ~3–5 minutes for 100 listings at the polite 1.5s delay.

## What it does

- **Source:** Craigslist RSS search feed at `newyork.craigslist.org/search/brk/apa`.
- **Per listing:** fetches the posting page for full description, lat/lng, neighborhood, bedrooms, posting date.
- **Hard filters (drop if fails):** price $1,200–$3,500; studio/1BR/2BR only; posted within 14 days; within 1.5 mi of 370 Jay St.
- **Score (0–100):** 40 pts distance (linear, closer better), 20 pts price (linear, cheaper better), and keyword bonuses — "student/NYU" (+15), "no guarantor / flexible" (+10), "furnished" (+5), "utilities included" (+5), F/A/C/R train mention (+5). 5-pt penalty only if a listing pairs "no pets" with "strict".
- **Output:** `apartments_YYYY-MM-DD.csv` with `score, price, bedrooms, neighborhood, distance_miles, posted_date, title, url, description` (description truncated to 200 chars), sorted by score desc.

## Notes

- Craigslist sometimes blocks data-center / VPN IPs. If `--sanity-check` returns a 403, run from a residential connection.
- Be polite — there's a 1.5s delay between requests baked in. Don't lower it.
- Listings without a usable lat/lng on the detail page are dropped (we can't measure distance).
