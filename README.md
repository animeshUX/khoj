# Khoj — Brooklyn apartments near NYU Tandon

A daily-refreshed list of student-affordable Brooklyn apartments, presented as a clean newspaper-style page anyone can open in a browser.

**Read the latest report:** https://animeshux.github.io/khoj/

No login. No app to install. Works on phones. Bookmark the link and check it whenever you want — it updates itself once a day.

## What it shows

The page lists Brooklyn rentals every morning, filtered down to what an NYU Tandon student can actually afford:

- Price between **$800 and $1,500**
- Studio, 1-bedroom, or 2-bedroom
- Posted in the last two weeks
- Within roughly a 30-minute commute of 370 Jay Street

Each entry shows the price, the neighborhood, how far it is, a cleaned-up description (phone-number spam and "TEXT ASAP" noise removed), and a small compass diagram showing where the apartment sits relative to campus. Listings near a subway line or that mention being student-friendly get bumped up the list.

Three views inside the page:

- **Inbox** — everything that matches today's filters
- **Shortlist** — only the listings you've starred
- **Map** — all listings as pins around campus

You can **★ Star** ones you like, **Hide** ones that don't fit, and **✎ Note** anything you want to remember about each. Those marks stay on your device — open the page tomorrow and they'll still be there.

## Sharing a listing you found yourself

There are two ways to get a listing into the report without scraping it:

**You found a Craigslist link.** Open `manual_urls.txt`, paste the link on a new line, save and push. The next run picks it up and treats it like any other listing.

```
# manual_urls.txt
https://newyork.craigslist.org/brk/apa/d/example/1234567890.html | Aunt Priya — nice kitchen
```

**Aunt or uncle submits via a Google Sheet.** They fill in a row in a shared Sheet (template provided in `submissions_template.csv`), you export it as `submissions.csv` and push. The scraper reads that file too. Rows whose URL cell isn't actually a link are skipped with a warning — common when someone pastes the page title by accident.

In either case, you can trigger an immediate refresh instead of waiting for tomorrow's run: go to the **Actions** tab in GitHub, click **"Scrape Craigslist"**, then **"Run workflow"**. About 5 minutes later, the live page updates.

## One-time setup (for a fresh clone of this repo)

1. **Settings → Pages** → Source: "Deploy from a branch" → Branch: `main`, Folder: `/docs` → Save
2. **Settings → Actions → General** → Workflow permissions → "Read and write permissions" → Save
3. **Actions tab → "Scrape Craigslist" → Run workflow** to kick off the first run

After about five minutes you'll have a live URL at `https://<your-github-handle>.github.io/khoj/`.

## How it actually runs

A GitHub Action fires once a day (around 9 AM Eastern), scrapes Craigslist, generates the report into the `docs/` folder, and commits it. GitHub Pages serves that folder. The whole stack is one Python script (`scraper.py`), one renderer (`report.py`), and a YAML workflow file. No database, no hosting bill, no API keys.

## Running it on your own machine (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scraper.py --sanity-check     # quick check that Craigslist is reachable
python scraper.py                    # writes apartments_YYYY-MM-DD.{csv,html}
python scraper.py --pages-mode       # writes into docs/ the same way the Action does
```

If the sanity check fails with a 403, run `python scraper.py --diagnose` to see which Craigslist endpoints are blocked from your network. Usually means you're on a VPN or corporate Wi-Fi.

## How a listing gets scored

The score is just a heuristic to put likely-good options near the top. It's not gospel — read the entry, look at the photos, decide yourself.

Out of 100:

- **40 points** for distance — closer to campus is better, linear
- **20 points** for price — cheaper inside the band is better, linear
- **+15** if the listing mentions students, NYU, or grad students
- **+10** if it mentions "no guarantor" or flexible lease terms
- **+5** for furnished
- **+5** for "utilities included"
- **+5** for an F, A, C, or R train mention
- **−5** if it pairs "no pets" with "strict"

If you want different weights, edit `KEYWORD_RULES` and the price/distance constants near the top of `scraper.py`.

## Things to know

- **Craigslist blocks the RSS endpoint** from most networks. We parse the static HTML search page instead — works fine from GitHub's runners.
- **There's a 1.5-second pause** between requests so we don't hammer their servers. ~100 listings takes about 5 minutes.
- **A listing without coordinates** gets dropped — we can't measure distance, can't draw it on the map.
- **Manual URLs in `manual_urls.txt`** are Craigslist-only right now. Other sites would need their own parsers; for one-offs from StreetEasy etc., open the link directly.

## Other places worth checking by hand

The report covers Craigslist only. These are listed at the bottom of every page too:

- **[AmberStudent](https://amberstudent.com/places/search/new-york-university-1811221663188)** — purpose-built student housing (per-room, booking-style)
- **[StreetEasy](https://streeteasy.com/for-rent/brooklyn/price:800-1500%7Cbeds%3C=2)** — NYC's biggest rental marketplace
- **[PadMapper](https://www.padmapper.com/apartments/brooklyn-ny?maxRent=1500)** — aggregator with map view
