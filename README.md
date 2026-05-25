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

# full run — writes apartments_YYYY-MM-DD.{csv,html} and prints top 10
python scraper.py

# tune fetch volume (default 100)
python scraper.py --max-listings 60 --out my_listings
```

Expect ~3–5 minutes for 100 listings at the polite 1.5s delay.

## Sharing with a non-coder

Each run produces two files:

- **`apartments_YYYY-MM-DD.html`** — a single self-contained webpage (cards, color-coded match scores, clickable "View on Craigslist" buttons). Email it, drop it in iMessage, or share via Google Drive — they open it in any browser, no setup. The report also includes a footer with links to AmberStudent / StreetEasy / PadMapper for manual browsing of inventory Craigslist misses.
- **`apartments_YYYY-MM-DD.csv`** — same data, for spreadsheets.

## Crowd-sourced submission app (Streamlit)

For when uncle, aunt, friends, or your brother himself find listings on sites we don't scrape — they paste the URL into a shared web page and it gets fetched, scored, and stored.

```bash
# locally
streamlit run app.py
# opens http://localhost:8501 — paste a Craigslist or any listing URL
```

Craigslist URLs get the full pipeline (price, bedrooms, distance, fit score). Any other URL falls back to OpenGraph metadata (title + description + image only — no scoring). Submissions are stored in `submissions.db` (SQLite, gitignored). You can mark each submission as `new / interesting / viewed / not_interesting`.

### Deploy free on Streamlit Cloud

1. Push this repo to GitHub (already done).
2. Go to <https://share.streamlit.io>, sign in with GitHub, click **New app**.
3. Pick this repo, branch `main`, main file `app.py`. Deploy.
4. You'll get a public URL like `khoj.streamlit.app`. Share it with your aunt and uncle.

**Persistence caveat:** Streamlit Cloud's filesystem persists between reruns inside the same container but can be wiped on redeploy. For long-term durability, swap `db.py` to write to Google Sheets (via `gspread`) or a hosted SQLite like Turso. The schema is small — easy to migrate.

## What this doesn't cover

Craigslist alone, by design. Considered scraping AmberStudent and StreetEasy too: Amber's data lives in a JavaScript object literal (not valid JSON) and its listings are mostly per-room PBSA — different product, awkward to mix into the same table. StreetEasy is Cloudflare-protected and needs a paid scraper. The HTML report links out to both so a human can browse them in a tab when the Craigslist set feels thin.

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
