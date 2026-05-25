"""Streamlit submission UI for crowd-sourced apartment hunting.

Run locally:  streamlit run app.py
Deploy:       push to GitHub, then connect the repo at https://share.streamlit.io
"""
from __future__ import annotations

import streamlit as st

import store as db  # dispatcher: Google Sheets if configured, SQLite otherwise
from fetchers import fetch_from_url, is_craigslist

st.set_page_config(page_title="Apartment Hunt · NYU Tandon", page_icon="🏠", layout="wide")

st.title("🏠 Apartment hunt — NYU Tandon")
st.caption(
    "Drop any listing URL you find while browsing. We auto-fetch the details, "
    "score Craigslist listings against fit for an NYU Tandon student, and keep "
    "everything in one place."
)
if db.BACKEND == "sqlite":
    msg = "Using local SQLite store (data won't persist across app redeploys)."
    if db.BACKEND_ERROR:
        msg += f"  _Sheets backend unavailable: {db.BACKEND_ERROR}_"
    st.warning(msg, icon="ℹ️")

# ---------- submit form ----------
with st.form("submit", clear_on_submit=True):
    url = st.text_input("Listing URL", placeholder="https://newyork.craigslist.org/... or any other site")
    c1, c2 = st.columns(2)
    submitter = c1.text_input("Your name", placeholder="optional — so we know who shared this")
    note = c2.text_input("Note", placeholder="optional — anything to flag? e.g. 'has a balcony!'")
    submitted = st.form_submit_button("Submit listing", type="primary")

if submitted:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        st.error("Please paste a full URL starting with http(s)://")
    else:
        with st.spinner("Fetching listing details ..."):
            try:
                listing, source = fetch_from_url(url)
                ok, message = db.add(url, submitter, note, listing, source)
                if ok:
                    st.success(f"Added! · source: **{source}** · {listing.title[:90]}")
                    if source == "craigslist":
                        meta = [
                            f"score **{listing.score}**",
                            f"${listing.price:,}" if listing.price else "no price",
                            f"{'Studio' if listing.bedrooms == 0 else f'{listing.bedrooms}BR'}" if listing.bedrooms is not None else "bedrooms?",
                            f"{listing.distance_miles:.2f} mi from campus" if listing.distance_miles else "no map data",
                            listing.neighborhood or "Brooklyn",
                        ]
                        st.info(" · ".join(meta))
                    else:
                        st.info(
                            "Only the page title and description were captured (full scoring is Craigslist-only for now). "
                            "Open the link to evaluate."
                        )
                else:
                    st.warning(f"Not added — {message}.")
            except Exception as e:
                st.error(f"Couldn't fetch: {e}")

st.divider()

# ---------- listings list ----------
rows = db.all_listings()
left, right = st.columns([3, 1])
left.subheader(f"Submitted listings ({len(rows)})")
hide_dismissed = right.toggle("Hide 'not interesting'", value=True)

if not rows:
    st.info("Nothing submitted yet. Be the first 👆")
else:
    for row in rows:
        if hide_dismissed and row["status"] == "not_interesting":
            continue
        with st.container(border=True):
            cols = st.columns([4, 1])
            with cols[0]:
                tier = "🟢" if row["score"] and row["score"] >= 80 else "🟡" if row["score"] and row["score"] >= 60 else "⚪"
                st.markdown(f"### {tier} {row['title'] or row['url']}")
                meta_parts = []
                if row["score"]:
                    meta_parts.append(f"**score {row['score']}**")
                if row["price"]:
                    meta_parts.append(f"${row['price']:,}")
                if row["bedrooms"] is not None:
                    meta_parts.append("Studio" if row["bedrooms"] == 0 else f"{row['bedrooms']}BR")
                if row["distance_miles"]:
                    meta_parts.append(f"{row['distance_miles']:.2f} mi")
                if row["neighborhood"]:
                    meta_parts.append(row["neighborhood"])
                if row["posted_date"]:
                    meta_parts.append(f"posted {row['posted_date']}")
                meta_parts.append(f"`{row['source']}`")
                st.caption(" · ".join(meta_parts))
                if row["submitter"] or row["note"]:
                    by = row["submitter"] or "anonymous"
                    extra = f" — _{row['note']}_" if row["note"] else ""
                    st.markdown(f"Shared by **{by}**{extra}")
                if row["description"]:
                    st.write(row["description"][:400] + ("…" if len(row["description"]) > 400 else ""))
                st.markdown(f"[Open listing →]({row['url']})")
            with cols[1]:
                current = row["status"]
                idx = db.STATUSES.index(current) if current in db.STATUSES else 0
                new_status = st.selectbox(
                    "status", db.STATUSES, index=idx, key=f"status_{row['id']}", label_visibility="collapsed",
                )
                if new_status != current:
                    db.set_status(row["id"], new_status)
                    st.rerun()
