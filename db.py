"""SQLite store for crowd-sourced apartment submissions.

Single-file DB at submissions.db in the working directory. On Streamlit Cloud's
free tier this persists across reruns within a container but can be wiped on
redeploy — for long-term durability, swap to a hosted DB (Turso, Supabase) or
write submissions to a Google Sheet via gspread."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("submissions.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at TEXT NOT NULL,
    submitter TEXT,
    note TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT,
    title TEXT,
    price INTEGER,
    bedrooms INTEGER,
    neighborhood TEXT,
    distance_miles REAL,
    posted_date TEXT,
    description TEXT,
    score INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new'
);
"""

STATUSES = ["new", "interesting", "viewed", "not_interesting"]


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def add(url: str, submitter: str, note: str, listing, source: str) -> tuple[bool, str]:
    """Insert a submission. Returns (ok, message). ok=False if URL already submitted."""
    with _conn() as c:
        try:
            c.execute(
                """INSERT INTO submissions
                   (submitted_at, submitter, note, url, source, title, price, bedrooms,
                    neighborhood, distance_miles, posted_date, description, score)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now().isoformat(timespec="seconds"),
                 (submitter or "").strip(), (note or "").strip(), url, source,
                 (listing.title or "")[:500], listing.price, listing.bedrooms,
                 listing.neighborhood or "", listing.distance_miles,
                 listing.posted_date or "", (listing.description or "")[:2000], listing.score),
            )
            return True, "ok"
        except sqlite3.IntegrityError:
            return False, "this URL was already submitted"


def all_listings(order_by: str = "score DESC, submitted_at DESC") -> list[sqlite3.Row]:
    with _conn() as c:
        return list(c.execute(f"SELECT * FROM submissions ORDER BY {order_by}"))


def set_status(submission_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    with _conn() as c:
        c.execute("UPDATE submissions SET status=? WHERE id=?", (status, submission_id))
