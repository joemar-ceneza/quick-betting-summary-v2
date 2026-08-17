"""
Quick Summary Report — interactive browser app (Streamlit).

Orchestrator only: collects the scrape inputs, runs the Leo scrape + summary
build, and hands the results to the ui.py presentation layer. All rendering
lives in ui.py; all data logic lives in scraper.py / parser.py / summary.py.

Run with:
    streamlit run app.py
"""

import logging
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

import config
import scraper
import summary
import ui

load_dotenv()


def _setup_logging() -> None:
    """Configure logging to logs/automation.log + console once per process."""
    if logging.getLogger().handlers:
        return
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


_setup_logging()


# ======================================================
# INPUT COLLECTION HELPERS
# ======================================================
def _leo_credentials():
    """Return Leo credentials from .env (or Streamlit secrets), else None."""
    user = os.getenv("LEO_USERNAME")
    pwd = os.getenv("LEO_PASSWORD")
    if not (user and pwd):
        try:
            user = user or st.secrets["LEO_USERNAME"]
            pwd = pwd or st.secrets["LEO_PASSWORD"]
        except Exception:  # noqa: BLE001 - secrets file is optional
            pass
    if user and pwd:
        return user, pwd
    return None


def _report_date_label(from_date: date, to_date: date) -> str:
    """Date shown on the report: the from-date for a one-day pull, else the range."""
    if to_date == from_date + timedelta(days=1):
        return from_date.strftime("%m/%d/%Y")
    return f"{from_date:%m/%d/%Y}–{to_date:%m/%d/%Y}"


def _run_scrape(username: str, from_date: date, to_date: date) -> None:
    """Scrape Leo, build the summary, and stash the result in session_state."""
    creds = _leo_credentials()
    if not username:
        st.sidebar.error("Enter a username.")
        return
    if from_date > to_date:
        st.sidebar.error("'Date from' must be on or before 'Date to'.")
        return
    if not creds:
        st.sidebar.error("Missing LEO_USERNAME / LEO_PASSWORD (set them in .env).")
        return

    with st.status(f"Scraping {username} from Leo…", expanded=True) as status:
        try:
            st.write("Logging in and scraping the bet list + account details…")
            # Scrape the union of the selected range and an 8-day window ending on
            # the To date, so the main summary always covers the full selected
            # range AND the day-by-day comparison gets a complete 8-day window.
            scrape_from = min(from_date, to_date - timedelta(days=7))
            players = scraper.run_scraper(
                [username], scrape_from.strftime("%m/%d/%Y"), to_date.strftime("%m/%d/%Y"), *creds
            )
            st.write("Building the player summary…")
            summaries = summary.build_summaries(players, _report_date_label(from_date, to_date), from_date, to_date)
            st.session_state["summaries"] = summaries
            status.update(label=f"Built the quick summary for {username}.", state="complete", expanded=False)
        except Exception as exc:  # noqa: BLE001 - surface scrape errors to the user
            logging.error("Scrape failed: %s", exc)
            status.update(label=f"Scrape failed: {exc}", state="error")


# ======================================================
# PAGE
# ======================================================
st.set_page_config(page_title="Quick Summary Report", layout="wide", page_icon="🎴", initial_sidebar_state="expanded")

# shared theme (font + design tokens) — applied on landing AND report for consistency
ui.inject_theme()

# ---- sidebar: scrape form ----
st.sidebar.header("Scrape from Leo")
with st.sidebar.form("scrape_form"):
    username = st.text_input("Username").strip()
    from_date = st.date_input("Date from", value=date.today() - timedelta(days=1))
    to_date = st.date_input("Date to", value=date.today())
    submitted = st.form_submit_button("Scrape & Summarize", width="stretch")

if submitted:
    _run_scrape(username, from_date, to_date)

# ---- render ----
if "summaries" not in st.session_state:
    ui.render_landing()
    st.stop()

ui.render_summaries(st.session_state["summaries"])
