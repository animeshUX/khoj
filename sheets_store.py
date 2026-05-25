"""Google Sheets backing store with the same interface as db.py.

Why Sheets: free, persistent forever, manually inspectable, shareable. Lets the
local scraper, the deployed Streamlit app, and human submitters all read/write
the same store without standing up infrastructure.

Setup:
1. Google Cloud → create project → enable "Google Sheets API"
2. Create a service account → keys → download JSON
3. Create a Google Sheet → share it with the service-account email (Editor role)
4. Set EITHER:
     - env var KHOJ_SHEET_ID = the spreadsheet id from the URL, OR
     - env var KHOJ_SHEET_NAME = the spreadsheet name
5. Make the JSON key reachable via one of:
     - env var GOOGLE_APPLICATION_CREDENTIALS = path to JSON, OR
     - file `service_account.json` in the project root (gitignored), OR
     - Streamlit Cloud Secrets entry `gcp_service_account` (full JSON contents)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache

import gspread
from google.oauth2.service_account import Credentials

STATUSES = ["new", "interesting", "viewed", "not_interesting"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
COLUMNS = ["id", "submitted_at", "submitter", "note", "url", "source", "title",
           "price", "bedrooms", "neighborhood", "distance_miles", "posted_date",
           "description", "score", "status"]
SHEET_TAB = "listings"
INT_COLS = {"id", "price", "bedrooms", "score"}
FLOAT_COLS = {"distance_miles"}


def _load_credentials() -> dict:
    """Resolve service account credentials from Streamlit secrets, env var, or file."""
    try:
        import streamlit as st  # type: ignore
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "service_account.json"
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _sheet():
    """Open the configured sheet's `listings` tab; create header row if missing."""
    creds = Credentials.from_service_account_info(_load_credentials(), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet_id = os.environ.get("KHOJ_SHEET_ID")
    sheet_name = os.environ.get("KHOJ_SHEET_NAME")
    if not (sheet_id or sheet_name):
        # Streamlit secrets fallback
        try:
            import streamlit as st  # type: ignore
            sheet_id = st.secrets.get("KHOJ_SHEET_ID")
            sheet_name = st.secrets.get("KHOJ_SHEET_NAME")
        except Exception:
            pass
    if not (sheet_id or sheet_name):
        raise RuntimeError("Set KHOJ_SHEET_ID or KHOJ_SHEET_NAME to identify the sheet.")
    sh = gc.open_by_key(sheet_id) if sheet_id else gc.open(sheet_name)
    try:
        ws = sh.worksheet(SHEET_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(SHEET_TAB, rows=2, cols=len(COLUMNS))
    if ws.row_values(1) != COLUMNS:
        ws.update("A1", [COLUMNS])
    return ws


def _existing_urls() -> set[str]:
    ws = _sheet()
    col = COLUMNS.index("url") + 1
    return set(v for v in ws.col_values(col)[1:] if v)


def _next_id() -> int:
    ws = _sheet()
    ids = [int(v) for v in ws.col_values(1)[1:] if v.isdigit()]
    return (max(ids) + 1) if ids else 1


def _row(submitted_at: str, submitter: str, note: str, url: str, source: str, listing, id_: int) -> list:
    return [
        id_, submitted_at, submitter or "", note or "", url, source,
        (listing.title or "")[:500],
        listing.price if listing.price is not None else "",
        listing.bedrooms if listing.bedrooms is not None else "",
        listing.neighborhood or "",
        round(listing.distance_miles, 3) if listing.distance_miles is not None else "",
        listing.posted_date or "",
        (listing.description or "")[:2000],
        listing.score or 0,
        "new",
    ]


def add(url: str, submitter: str, note: str, listing, source: str) -> tuple[bool, str]:
    if url in _existing_urls():
        return False, "this URL was already submitted"
    ws = _sheet()
    now = datetime.now().isoformat(timespec="seconds")
    ws.append_row(_row(now, submitter, note, url, source, listing, _next_id()),
                  value_input_option="USER_ENTERED")
    return True, "ok"


def bulk_add(listings, source: str) -> tuple[int, int]:
    if not listings:
        return 0, 0
    existing = _existing_urls()
    new = [l for l in listings if l.url not in existing]
    if not new:
        return 0, len(listings)
    ws = _sheet()
    now = datetime.now().isoformat(timespec="seconds")
    start_id = _next_id()
    rows = [_row(now, "", "", l.url, source, l, start_id + i) for i, l in enumerate(new)]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(new), len(listings) - len(new)


def _coerce(records: list[dict]) -> list[dict]:
    """gspread returns everything as strings unless number-formatted; coerce schema types."""
    for r in records:
        for k in INT_COLS:
            v = r.get(k)
            r[k] = int(v) if isinstance(v, str) and v.lstrip("-").isdigit() else (v if isinstance(v, int) else None)
        for k in FLOAT_COLS:
            v = r.get(k)
            try:
                r[k] = float(v) if v not in ("", None) else None
            except (TypeError, ValueError):
                r[k] = None
    return records


def all_listings(order_by: str = "score DESC, submitted_at DESC") -> list[dict]:
    """Return rows as dicts. order_by supports the same default the SQLite store uses."""
    records = _coerce(_sheet().get_all_records())
    # Stable sort: secondary key first, then primary
    records.sort(key=lambda r: r.get("submitted_at") or "", reverse="submitted_at DESC" in order_by)
    records.sort(key=lambda r: r.get("score") or 0, reverse="score DESC" in order_by)
    return records


def set_status(submission_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    ws = _sheet()
    ids = ws.col_values(1)
    for i, val in enumerate(ids, start=1):
        if val == str(submission_id):
            ws.update_cell(i, COLUMNS.index("status") + 1, status)
            return
