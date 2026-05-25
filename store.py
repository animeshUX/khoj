"""Backend dispatcher: Google Sheets if configured, SQLite otherwise.

Both backends expose the same surface — `add`, `bulk_add`, `all_listings`,
`set_status`, `STATUSES` — so callers don't care which one is active. The
choice is made once, at import time:

- Try to initialize sheets_store. If the gspread import, credentials, sheet
  id, or first API call fails for any reason, fall back to SQLite.
- `BACKEND` ("sheets" | "sqlite") tells the UI which is active.
- `BACKEND_ERROR` carries the fallback reason so the app can surface it.
"""
from __future__ import annotations

BACKEND: str
BACKEND_ERROR: str = ""

try:
    from sheets_store import (  # noqa: F401
        add, bulk_add, all_listings, set_status, STATUSES, _sheet,
    )
    _sheet()  # eager auth — raises if creds/sheet-id missing or unreachable
    BACKEND = "sheets"
except Exception as e:  # pragma: no cover — env-dependent
    BACKEND_ERROR = f"{type(e).__name__}: {e}"
    from db import add, bulk_add, all_listings, set_status, STATUSES  # noqa: F401
    BACKEND = "sqlite"
