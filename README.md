# Khoj — NYU Tandon apartment finder

A daily-updated Craigslist apartment report for the NYU Tandon area. Runs on GitHub Actions, publishes to GitHub Pages. No deployment to maintain, no databases, no API keys.

**Live report:** https://animeshux.github.io/khoj/ _(once GitHub Pages is enabled in repo settings)_

## How it works

1. **GitHub Actions** runs the scraper daily on a cron schedule (`13:00 UTC` ≈ 9am ET).
2. The scraper pulls Brooklyn apartments from Craigslist within 1.5 mi of 370 Jay St, applies price/bedroom/recency filters, scores each listing for fit (distance, price, student-friendly keywords).
3. Results are written to `docs/index.html` (latest, color-coded card layout) and `docs/apartments_latest.csv` (for opening in Sheets/Excel). Dated archives accumulate alongside.
4. The Action commits `docs/` back to `main` and **GitHub Pages** serves it at the URL above.

## One-time setup

1. **Enable GitHub Pages**: repo Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, Folder: `/docs` → Save.
2. **Allow Actions to push to main**: Settings → Actions → General → Workflow permissions → check "Read and write permissions" → Save.
3. **First run**: Actions tab → "Scrape Craigslist" → "Run workflow" → Run.
4. After the run completes, your live URL is `https://<your-github-handle>.github.io/khoj/`.

## When aunt/uncle send you a URL

Open `manual_urls.txt`, paste the URL on a new line, commit & push. Next scheduled run picks it up; the listing appears in the report alongside scraped ones (skipping the price/distance filters but still scored).

```
# manual_urls.txt
https://newyork.craigslist.org/brk/apa/d/example/1234567890.html | Aunt Priya — nice kitchen
```

To process it immediately rather than waiting for the cron: Actions tab → "Scrape Craigslist" → "Run workflow."

## Running locally (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scraper.py --sanity-check    # verify Craigslist is reachable
python scraper.py                   # writes apartments_YYYY-MM-DD.{csv,html}
python scraper.py --pages-mode      # writes into docs/ like the Action does
```

If `--sanity-check` returns 403, run `python scraper.py --diagnose` to see which endpoints are blocked.

## Filtering & scoring

**Hard filters (drop if fails):**
- Price $1,200–$3,500
- Studio / 1BR / 2BR only
- Posted within 14 days
- Within 1.5 mi of 370 Jay St (NYU Tandon, Brooklyn)

**Score (0–100):**
- Distance: 40 pts (linear, closer better)
- Price: 20 pts (linear, cheaper better)
- Keyword bonuses: "student/NYU" (+15), "no guarantor / flexible" (+10), "furnished" (+5), "utilities included" (+5), F/A/C/R train mention (+5)
- Penalty: −5 if "no pets" appears with "strict"

Tune in `scraper.py` (the constants at the top).

## Notes

- Craigslist serves a static SEO HTML block of search results (~300 per fetch) — no JS, no RSS, no API key. We parse `<li class="cl-static-search-result">` and follow each posting URL for details (price, bedrooms, lat/lng, description).
- The 1.5s delay between requests is intentional — be polite. ~100 listings = ~5 min total runtime.
- Manual URLs in `manual_urls.txt` are Craigslist-only for now. Other sites can be added later if needed; for one-off non-Craigslist links, just open them directly.
