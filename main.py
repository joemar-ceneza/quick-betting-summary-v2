import getpass
import logging
import os
import sys
import urllib.request
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(os.path.dirname(sys.executable)) / ".env" if getattr(sys, "frozen", False) else None)

import config
import scraper
import summary

if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(os.path.dirname(sys.executable)).parent.parent / "ms-playwright")

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

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


def _load_usernames(path: str) -> list[str]:
    """Reads and returns the list of usernames from the given file, exiting if missing or empty."""
    if not os.path.exists(path):
        logging.error("Usernames file not found: %s", path)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        usernames = [line.strip() for line in f if line.strip()]
    if not usernames:
        logging.warning("No usernames found in file. Exiting.")
        sys.exit(1)
    return usernames


def _collect_credentials() -> tuple[str, str]:
    """Loads LEO credentials from .env, falling back to interactive prompts."""
    leo_username = os.getenv("LEO_USERNAME") or input("Enter LEO Username: ")
    leo_password = os.getenv("LEO_PASSWORD") or getpass.getpass("Enter LEO Password: ")
    if not leo_username or not leo_password:
        raise ValueError("LEO username and password are required.")
    return leo_username, leo_password


def _resolve_date_range() -> tuple[str, str, str]:
    """
    Resolve the report date from the optional CLI argument (MM/DD/YYYY),
    defaulting to yesterday. Returns (report_date, from_date, to_date) —
    to_date is the following day, matching the Leo bet-list date filter.
    """
    if len(sys.argv) > 1:
        try:
            report_date = datetime.strptime(sys.argv[1], "%m/%d/%Y").date()
        except ValueError:
            logging.error("Invalid date '%s'. Usage: python main.py [MM/DD/YYYY]", sys.argv[1])
            sys.exit(1)
    else:
        report_date = datetime.today().date() - timedelta(days=1)

    from_date = report_date.strftime("%m/%d/%Y")
    to_date = (report_date + timedelta(days=1)).strftime("%m/%d/%Y")
    return from_date, from_date, to_date


def main() -> None:
    """Run the full workflow: scrape LEO → build player summaries (logged to console + log file)."""

    # Step 1: Load usernames
    logging.info("=" * 70)
    logging.info("STEP 1 — Loading usernames")
    logging.info("=" * 70)
    usernames = _load_usernames(config.USERNAME_FILE)
    logging.info("Loaded %d usernames.", len(usernames))

    # Step 2: Collect credentials
    logging.info("=" * 70)
    logging.info("STEP 2 — Collecting credentials")
    logging.info("=" * 70)
    leo_username, leo_password = _collect_credentials()

    # Step 3: Resolve report date range
    logging.info("=" * 70)
    logging.info("STEP 3 — Resolving report date range")
    logging.info("=" * 70)
    report_date, from_date, to_date = _resolve_date_range()
    logging.info("Report date: %s (bet list %s to %s)", report_date, from_date, to_date)

    # Step 4: Run LEO quick-summary scraper
    logging.info("=" * 70)
    logging.info("STEP 4 — Running LEO scraper (%d users)", len(usernames))
    logging.info("=" * 70)
    players = scraper.run_scraper(usernames, from_date, to_date, leo_username, leo_password)
    if not players:
        logging.warning("No player data scraped. Exiting.")
        sys.exit()

    # Step 5: Build player summaries (results are written to the log)
    logging.info("=" * 70)
    logging.info("STEP 5 — Building player summaries (%d players)", len(players))
    logging.info("=" * 70)
    summary.build_summaries(players, report_date)

    logging.info("=" * 70)
    logging.info("All done. Full results are shown above and in %s", config.LOG_FILE)
    logging.info("For the browser report, run: streamlit run app.py")
    logging.info("=" * 70)


if __name__ == "__main__":
    main()
