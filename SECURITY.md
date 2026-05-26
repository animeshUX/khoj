# Security policy

This repo is a personal apartment-research tool. The published site at
https://animeshux.github.io/khoj/ is a static report regenerated daily by
GitHub Actions; the only inputs are public Craigslist HTML and a maintainer-
curated Google Sheet.

## Reporting a vulnerability

Open a **private security advisory** via GitHub's "Report a vulnerability"
button on the [Security tab](https://github.com/animeshUX/khoj/security/advisories),
or email the maintainer at `animeshux@gmail.com`. Please don't open a public
issue for security findings.

Useful info to include:

- What the bug lets an attacker do (XSS, SSRF, secret leak, etc.).
- The smallest input that reproduces it.
- The file / line where the issue lives, if you know.

I'll usually respond within a few days. There's no bounty — this is a
hobby project — but I'll credit you in the fix commit if you'd like.

## Scope

In scope:
- The scraper, scoring, and report-rendering code (`scraper.py`,
  `score.py`, `report/`, `enrich.py`, `submission.py`).
- The browser modules under `docs/khoj/`.
- The Apps Script Web App in `apps_script.gs`.
- The GitHub Actions workflows in `.github/workflows/`.

Out of scope:
- Bugs in upstream data (Craigslist HTML, NYC Open Data, OSM/Nominatim,
  Overpass). Report those upstream.
- Theoretical timing attacks on the Apps Script key check (round-trip
  jitter dominates).
- DNS rebinding against the SSRF guard in `_fetch_external_listing` —
  the guard catches literal RFC1918 hosts; full mitigation isn't worth
  the complexity for this threat model.
