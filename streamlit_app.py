"""
Streamlit front-end for the UPSC Daily News Digest.

Shows the most recent auto-generated digest (from digests/latest.md), and
also lets the user fetch fresh headlines on demand directly from the RSS
feeds defined in fetch_news.py.
"""

import datetime
import os

import streamlit as st

from fetch_news import FEEDS, fetch_category

st.set_page_config(page_title="UPSC Daily News Digest", page_icon="U0001F4F0", layout="wide")

st.title("UPSC Daily News Digest")
st.caption("Curated daily headlines for Civil Services aspirants, grouped by subject.")

DIGEST_DIR = "digests"
LATEST_PATH = os.path.join(DIGEST_DIR, "latest.md")


@st.cache_data(ttl=3600)
def load_saved_digest():
    if os.path.exists(LATEST_PATH):
        with open(LATEST_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return None


@st.cache_data(ttl=3600)
def build_live_digest():
    return {category: fetch_category(sources) for category, sources in FEEDS.items()}


with st.sidebar:
    st.header("Options")
    mode = st.radio("Source", ["Saved daily digest", "Fetch live now"], index=0)
    if st.button("Refresh live news"):
        build_live_digest.clear()
    st.markdown("---")
    st.caption(
        "The saved digest updates automatically once a day via a GitHub "
        "Actions workflow. Use 'Fetch live now' to pull the newest "
        "headlines on demand."
    )

if mode == "Saved daily digest":
    content = load_saved_digest()
    if content:
        st.markdown(content)
    else:
        st.warning(
            "No saved digest found yet. Try 'Fetch live now' from the "
            "sidebar, or wait for the next scheduled run."
        )
else:
    with st.spinner("Fetching latest headlines..."):
        all_items = build_live_digest()
    today = datetime.date.today().isoformat()
    st.subheader(f"Live headlines - {today}")
    any_items = False
    for category, items in all_items.items():
        if not items:
            continue
        any_items = True
        with st.expander(category, expanded=True):
            for item in items:
                st.markdown(f"- [{item['title']}]({item['link']})  \n  _{item['source']}_")
    if not any_items:
        st.info("Could not fetch any headlines right now. Please try again shortly.")

st.divider()
st.caption(
    "Automated aggregation of publicly available headlines. Always verify "
    "facts against the original source before quoting them in Mains answers."
)
